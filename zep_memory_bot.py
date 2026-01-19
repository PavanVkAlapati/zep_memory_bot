# zep_memory_bot.py
import os
import asyncio
from dotenv import load_dotenv
from openai import OpenAI
from zep_cloud.client import AsyncZep
from zep_cloud.types import Message

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ZEP_API_KEY = os.getenv("ZEP_API_KEY")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

USER_ID = os.getenv("ZEP_USER_ID", "user123")
SESSION_ID = os.getenv("ZEP_SESSION_ID", "session123")

if not OPENAI_API_KEY or not ZEP_API_KEY:
    raise RuntimeError("Missing OPENAI_API_KEY or ZEP_API_KEY in .env")

openai_client = OpenAI(api_key=OPENAI_API_KEY)
zep_client = AsyncZep(api_key=ZEP_API_KEY)

SYSTEM_PROMPT = """You are a helpful assistant.
Use the Zep memory context to stay consistent with the user over time.
If memory conflicts with the user's latest instruction, follow the latest instruction.
"""

async def add_turn_to_zep(user_text: str, assistant_text: str):
    # Add both in order, per best practice
    msgs = [
        Message(role=USER_ID, role_type="user", content=user_text),
        Message(role="assistant", role_type="assistant", content=assistant_text),
    ]
    await zep_client.memory.add(session_id=SESSION_ID, user_id=USER_ID, messages=msgs)

async def get_zep_context() -> str:
    mem = await zep_client.memory.get(session_id=SESSION_ID, user_id=USER_ID)
    return mem.context or ""

def call_openai(user_text: str, zep_context: str, short_history: list):
    # short_history = last few turns as {"role": "...", "content": "..."}
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if zep_context.strip():
        messages.append({"role": "system", "content": f"ZEP MEMORY CONTEXT:\n{zep_context}"})
    messages.extend(short_history)
    messages.append({"role": "user", "content": user_text})

    resp = openai_client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.2,
    )
    return resp.choices[0].message.content

async def main():
    short_history = []  # raw recent context (not long-term)
    print("Zep Memory Bot. Type 'exit' to stop.\n")

    while True:
        user_text = input("you> ").strip()
        if user_text.lower() in {"exit", "quit"}:
            break
        if not user_text:
            continue

        zep_context = await get_zep_context()
        assistant_text = call_openai(user_text, zep_context, short_history)
        print(f"bot> {assistant_text}\n")

        # update short history (keep last 6 msgs total)
        short_history.append({"role": "user", "content": user_text})
        short_history.append({"role": "assistant", "content": assistant_text})
        short_history = short_history[-6:]

        await add_turn_to_zep(user_text, assistant_text)

if __name__ == "__main__":
    asyncio.run(main())
