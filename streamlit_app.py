# streamlit_app.py  — FULL FIXED VERSION FOR YOUR ZEP CLOUD SDK

import os
import uuid
import hashlib
from typing import Dict, Any, List
from dotenv import load_dotenv

import streamlit as st
from openai import OpenAI

# Zep Cloud SDK (your working older version)
from zep_cloud.client import Zep
from zep_cloud import Message
from zep_cloud.core.api_error import ApiError

from st_link_analysis import st_link_analysis

# ----------------------------
# Load env
# ----------------------------
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ZEP_API_KEY = os.getenv("ZEP_API_KEY")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

USER_ID = os.getenv("ZEP_USER_ID", "vk_user")
ENV_THREAD_ID = os.getenv("ZEP_THREAD_ID") or os.getenv("ZEP_SESSION_ID")

if not OPENAI_API_KEY or not ZEP_API_KEY:
    raise RuntimeError("Missing OPENAI_API_KEY or ZEP_API_KEY in .env")

openai_client = OpenAI(api_key=OPENAI_API_KEY)
zep = Zep(api_key=ZEP_API_KEY)

SYSTEM_PROMPT = """You are a helpful assistant.
Use long-term memory from Zep when relevant.
If memory conflicts with the user's latest instruction, follow the latest instruction.
"""

THREAD_FILE = "zep_thread_id.txt"

# Zep message limit in your SDK is 2500.
MAX_ZEP_CHARS = 2400


# ----------------------------
# Zep user utilities (adaptive)
# ----------------------------
def ensure_user_exists(user_id: str):
    user_client = getattr(zep, "user", None) or getattr(zep, "users", None)
    if user_client is None:
        return

    get_fn = getattr(user_client, "get", None)
    if callable(get_fn):
        try:
            get_fn(user_id=user_id)
            return
        except Exception:
            pass

    for name in ["create", "add", "upsert", "ensure", "create_user", "upsert_user"]:
        fn = getattr(user_client, name, None)
        if callable(fn):
            try:
                fn(user_id=user_id)
                return
            except Exception:
                continue


def thread_exists(thread_id: str) -> bool:
    try:
        zep.thread.get(thread_id=thread_id, limit=1)
        return True
    except Exception:
        return False


def load_or_create_thread_id() -> str:
    ensure_user_exists(USER_ID)

    if ENV_THREAD_ID and thread_exists(ENV_THREAD_ID):
        return ENV_THREAD_ID

    if os.path.exists(THREAD_FILE):
        tid = open(THREAD_FILE, "r", encoding="utf-8").read().strip()
        if tid and thread_exists(tid):
            return tid

    new_tid = str(uuid.uuid4())
    try:
        zep.thread.create(thread_id=new_tid, user_id=USER_ID)
    except ApiError as e:
        if "user not found" in str(e).lower():
            ensure_user_exists(USER_ID)
            zep.thread.create(thread_id=new_tid, user_id=USER_ID)
        else:
            raise

    with open(THREAD_FILE, "w", encoding="utf-8") as f:
        f.write(new_tid)

    return new_tid


def zep_get_context(thread_id: str) -> str:
    try:
        ctx = zep.thread.get_user_context(thread_id=thread_id)
        return ctx.context or ""
    except Exception:
        return ""


# ----------------------------
# Chunking to satisfy Zep limit
# ----------------------------
def chunk_text(text: str, max_len: int = MAX_ZEP_CHARS) -> List[str]:
    if not text:
        return [""]

    if len(text) <= max_len:
        return [text]

    parts = []
    paras = text.split("\n\n")
    current = ""

    for p in paras:
        if not p.strip():
            continue
        candidate = (current + "\n\n" + p).strip() if current else p

        if len(candidate) <= max_len:
            current = candidate
        else:
            if current:
                parts.append(current)
                current = ""

            while len(p) > max_len:
                parts.append(p[:max_len])
                p = p[max_len:]
            if p:
                current = p

    if current:
        parts.append(current)

    return parts


def zep_add_turn(thread_id: str, user_text: str, assistant_text: str):
    user_chunks = chunk_text(user_text)
    assistant_chunks = chunk_text(assistant_text)

    msgs = []
    for uc in user_chunks:
        msgs.append(Message(role="user", content=uc))
    for ac in assistant_chunks:
        msgs.append(Message(role="assistant", content=ac))

    zep.thread.add_messages(thread_id=thread_id, messages=msgs)


# ----------------------------
# Graph Export (FIXED for your SDK output)
# ----------------------------
def _stable_hash_id(prefix: str, value: str) -> str:
    h = hashlib.md5(value.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{h}"


def zep_export_graph(user_id: str, limit: int = 50) -> Dict[str, Any]:
    """
    Your SDK rules:
      - query is required (cannot be empty)
      - limit <= 50
    We use query="*" and cap limit.
    
    Your Zep Cloud returns nodes/edges where:
      node.data.id == "None"
      edge.data.id == "None"
      edge.data.source/target are real UUIDs
    So we:
      1) build stable node ids from labels
      2) map old UUID -> new stable id
      3) rebuild edges to point to stable ids
    """
    ensure_user_exists(user_id)
    safe_limit = min(int(limit), 50)

    nodes_res = zep.graph.search(
        user_id=user_id,
        query="*",
        limit=safe_limit,
        scope="nodes"
    )
    edges_res = zep.graph.search(
        user_id=user_id,
        query="*",
        limit=safe_limit,
        scope="edges"
    )

    zep_nodes = getattr(nodes_res, "nodes", []) or []
    zep_edges = getattr(edges_res, "edges", []) or []

    # --- Build stable nodes + UUID->stable map ---
    nodes_out = []
    uuid_to_stable = {}

    for n in zep_nodes:
        # your node is already dict-like from SDK
        data = getattr(n, "data", None) or n.get("data", {}) if isinstance(n, dict) else {}

        old_id = data.get("id")
        label = data.get("label") or "unknown"

        stable_id = _stable_hash_id("n", str(label))

        nodes_out.append({
            "data": {
                "id": stable_id,
                "label": str(label)
            }
        })

        # if Zep ever sends real UUID later, keep mapping
        if old_id and old_id != "None":
            uuid_to_stable[str(old_id)] = stable_id

    # --- Build edges with stable ids ---
    edges_out = []
    for e in zep_edges:
        data = getattr(e, "data", None) or e.get("data", {}) if isinstance(e, dict) else {}

        source_uuid = str(data.get("source"))
        target_uuid = str(data.get("target"))
        rel = data.get("label") or "related_to"

        # If those UUIDs are not in map (because current nodes had None),
        # we still create stable ids from UUID so graph remains connected.
        source_id = uuid_to_stable.get(source_uuid) or _stable_hash_id("n", source_uuid)
        target_id = uuid_to_stable.get(target_uuid) or _stable_hash_id("n", target_uuid)

        edge_id = _stable_hash_id("e", f"{source_id}|{rel}|{target_id}")

        edges_out.append({
            "data": {
                "id": edge_id,
                "source": source_id,
                "target": target_id,
                "label": str(rel)
            }
        })

    # remove any duplicates
    seen_nodes = {}
    for n in nodes_out:
        seen_nodes[n["data"]["id"]] = n
    nodes_out = list(seen_nodes.values())

    seen_edges = {}
    for e in edges_out:
        seen_edges[e["data"]["id"]] = e
    edges_out = list(seen_edges.values())

    return {"nodes": nodes_out, "edges": edges_out}


# ----------------------------
# OpenAI
# ----------------------------
def openai_answer(user_text: str, zep_context: str, short_history: List[Dict[str, str]]) -> str:
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
    if zep_context.strip():
        msgs.append({"role": "system", "content": f"ZEP MEMORY CONTEXT:\n{zep_context}"})
    msgs.extend(short_history)
    msgs.append({"role": "user", "content": user_text})

    resp = openai_client.chat.completions.create(
        model=MODEL,
        messages=msgs,
        temperature=0.2,
    )
    return resp.choices[0].message.content


# ----------------------------
# Streamlit UI
# ----------------------------
st.set_page_config(page_title="Zep Memory + Graph", layout="wide")

try:
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = load_or_create_thread_id()
except Exception as e:
    st.error(
        "Zep setup failed.\n\n"
        f"Exact error: {e}"
    )
    st.stop()

st.session_state.setdefault("short_history", [])
st.session_state.setdefault("messages", [])
st.session_state.setdefault("graph_json", {"nodes": [], "edges": []})

left, right = st.columns([1.2, 1])

with left:
    st.title("Chatbot (Zep long-term memory)")

    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    user_text = st.chat_input("Ask something...")
    if user_text:
        thread_id = st.session_state.thread_id

        st.session_state.messages.append({"role": "user", "content": user_text})
        with st.chat_message("user"):
            st.markdown(user_text)

        zep_context = zep_get_context(thread_id)
        assistant_text = openai_answer(user_text, zep_context, st.session_state.short_history)

        st.session_state.messages.append({"role": "assistant", "content": assistant_text})
        with st.chat_message("assistant"):
            st.markdown(assistant_text)

        st.session_state.short_history.append({"role": "user", "content": user_text})
        st.session_state.short_history.append({"role": "assistant", "content": assistant_text})
        st.session_state.short_history = st.session_state.short_history[-6:]

        zep_add_turn(thread_id, user_text, assistant_text)

with right:
    st.title("Temporal Knowledge Graph")

    if st.button("Refresh graph from Zep"):
        st.session_state.graph_json = zep_export_graph(USER_ID, limit=50)

    graph_data = st.session_state.graph_json

    st.subheader("Graph View")
    if graph_data["nodes"]:
        st_link_analysis(graph_data, height=650, key="zep_graph")
        st.caption(
            f"nodes: {len(graph_data['nodes'])} | edges: {len(graph_data['edges'])}"
        )
    else:
        st.info("No graph yet. Chat a few turns, then click refresh.")

    with st.expander("Raw JSON"):
        st.json(graph_data)
