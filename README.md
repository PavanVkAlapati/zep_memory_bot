# Zep Memory Chatbot with Graph Visualization (Streamlit)

A Streamlit-based chatbot that integrates **Zep** for long-term conversational memory and visualizes the underlying **knowledge graph** using `st_link_analysis`.

This project demonstrates:
- Persistent chat memory using Zep
- Context-aware responses from stored conversation history
- Exporting Zep graph data into JSON
- Interactive graph visualization inside a Streamlit app

---

## Features

- 💬 Chatbot with long-term memory (Zep)
- 🧠 Context retrieval for improved LLM responses
- 🕸️ Zep graph (nodes & edges) export
- 📊 Graph visualization using `st_link_analysis`
- 🖥️ Single Streamlit application

---

## Project Structure

```
.
├── streamlit_app.py         # Main Streamlit app (chat + graph visualization)
├── zep_graph.py             # Optional graph export/debug utility
├── zep_memory_bot.py        # Optional CLI-based chatbot
├── requirements.txt
├── docker-compose.yml       # Optional (remove secrets before committing)
├── data/                    # Optional local data (not required)
├── zep_thread_id.txt        # Runtime file (do not commit)
└── .env                     # Secrets file (do not commit)
```

---

## Prerequisites

- Python 3.10 or higher
- Zep account (Zep Cloud API key or Zep OSS)
- OpenAI API key (or compatible LLM provider)

---

## Installation

### 1. Clone the repository

```bash
git clone <your-github-repo-url>
cd <repo-folder>
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

## Environment Configuration

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=your_openai_api_key
ZEP_API_KEY=your_zep_api_key
OPENAI_MODEL=gpt-4o-mini
ZEP_USER_ID=vk_user
```

⚠️ **Never commit `.env` or API keys to GitHub.**

---

## Running the Application

```bash
streamlit run streamlit_app.py
```

Once running:
- Start chatting with the bot
- Memory is stored and retrieved from Zep
- Use the UI control to refresh and visualize the Zep knowledge graph

---

## Graph Data Format

The Zep graph is converted into the format required by `st_link_analysis`:

```json
{
  "nodes": [
    { "data": { "id": "node_1", "label": "User" } }
  ],
  "edges": [
    {
      "data": {
        "id": "edge_1",
        "source": "node_1",
        "target": "node_2",
        "label": "related_to"
      }
    }
  ]
}
```

---

## GitHub Safety Notes

- Do **not** commit `.env`
- Do **not** commit `zep_thread_id.txt`
- Remove API keys from `docker-compose.yml` before pushing
- Use environment variables for all secrets

---

## License

Add a license (MIT recommended) if you plan to make this repository public or reusable.
