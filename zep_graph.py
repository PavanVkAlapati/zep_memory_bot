# export_zep_graph_to_stlink_json.py  (FULL FIXED for your older Zep Cloud SDK)

import os
import json
import asyncio
import hashlib
from dotenv import load_dotenv
from zep_cloud.client import AsyncZep

# ----------------------------
# Load env
# ----------------------------
load_dotenv()
ZEP_API_KEY = os.getenv("ZEP_API_KEY")
USER_ID = os.getenv("ZEP_USER_ID", "vk_user")

if not ZEP_API_KEY:
    raise RuntimeError("Missing ZEP_API_KEY in .env")

zep_client = AsyncZep(api_key=ZEP_API_KEY)

MAX_LIMIT = 50  # Zep Cloud hard limit for search/list APIs


# ----------------------------
# Helpers
# ----------------------------
def _hash(prefix: str, value: str) -> str:
    """Stable deterministic id."""
    h = hashlib.md5(value.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{h}"


def _get_data(obj):
    """Support SDK objects or dicts."""
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj.get("data", obj)
    return getattr(obj, "data", {}) or {}


# ----------------------------
# Convert to st-link-analysis JSON
# ----------------------------
def to_stlink_json(zep_nodes, zep_edges):
    """
    st-link-analysis expects:
    {
      "nodes":[{"data":{"id":"n1","label":"Alice"}}, ...],
      "edges":[{"data":{"id":"e1","source":"n1","target":"n2","label":"likes"}}, ...]
    }

    Your Zep Cloud SDK outputs:
      node.data.id == "None"
      edge.data.id == "None"
      edge.data.source/target are real UUIDs

    FIX:
      - Create UNIQUE node IDs even if labels repeat
      - Map original UUID -> stable ID if Zep ever provides one
      - Remap edges to stable IDs
      - Create UNIQUE edge IDs
    """
    nodes_out = []
    uuid_to_stable = {}

    # --- NODES ---
    for i, n in enumerate(zep_nodes or []):
        data = _get_data(n)
        old_id = str(data.get("id"))
        label = data.get("label") or data.get("name") or "unknown"

        # If Zep provides a real id, use it; else unique id from label+index
        if old_id and old_id != "None":
            stable_id = old_id
        else:
            stable_id = _hash("n", f"{label}|{i}")

        nodes_out.append({
            "data": {
                "id": stable_id,
                "label": str(label)
            }
        })

        if old_id and old_id != "None":
            uuid_to_stable[old_id] = stable_id

    # --- EDGES ---
    edges_out = []
    for j, e in enumerate(zep_edges or []):
        data = _get_data(e)

        source_uuid = str(data.get("source"))
        target_uuid = str(data.get("target"))
        rel = data.get("label") or data.get("relationship") or "related_to"

        if not source_uuid or source_uuid == "None" or not target_uuid or target_uuid == "None":
            continue

        # remap endpoints to stable node IDs
        source_id = uuid_to_stable.get(source_uuid) or _hash("n", source_uuid)
        target_id = uuid_to_stable.get(target_uuid) or _hash("n", target_uuid)

        old_edge_id = str(data.get("id"))

        # If Zep provides real edge id, use it; else unique per edge
        if old_edge_id and old_edge_id != "None":
            edge_id = old_edge_id
        else:
            edge_id = _hash("e", f"{source_id}|{rel}|{target_id}|{j}")

        edges_out.append({
            "data": {
                "id": edge_id,
                "source": source_id,
                "target": target_id,
                "label": str(rel)
            }
        })

    # de-duplicate ONLY by exact id
    nodes_out = list({n["data"]["id"]: n for n in nodes_out}.values())
    edges_out = list({e["data"]["id"]: e for e in edges_out}.values())

    return {"nodes": nodes_out, "edges": edges_out}


# ----------------------------
# Export full graph
# ----------------------------
async def main(out_path="graph.json"):
    """
    Prefer full-graph endpoints if present, else fall back to search.
    """
    zep_nodes, zep_edges = [], []

    # ---- 1) Try full graph endpoints ----
    try:
        node_res = await zep_client.graph.node.get_by_user_id(user_id=USER_ID)
        edge_res = await zep_client.graph.edge.get_by_user_id(user_id=USER_ID)
        zep_nodes = getattr(node_res, "nodes", node_res) or []
        zep_edges = getattr(edge_res, "edges", edge_res) or []
    except Exception:
        # ---- 2) Fallback to semantic search (query required) ----
        safe_limit = MAX_LIMIT
        nodes_res = await zep_client.graph.search(
            user_id=USER_ID, query="*", limit=safe_limit, scope="nodes"
        )
        edges_res = await zep_client.graph.search(
            user_id=USER_ID, query="*", limit=safe_limit, scope="edges"
        )
        zep_nodes = getattr(nodes_res, "nodes", []) or []
        zep_edges = getattr(edges_res, "edges", []) or []

    stlink = to_stlink_json(zep_nodes, zep_edges)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(stlink, f, indent=2)

    print(f"Saved st-link-analysis graph JSON -> {out_path}")
    print(f"nodes: {len(stlink['nodes'])}, edges: {len(stlink['edges'])}")


if __name__ == "__main__":
    asyncio.run(main())
