# ParcelPilot AI Support System

An AI-powered support agent for ParcelPilot's B2B logistics platform.

## Features

- **Multi-tenant Support**: Customer and internal roles with proper access control
- **Intelligent Routing**: Extracts intent and entities before LLM calls
- **Authority Hierarchy**: Contracts (Level 1) > SOPs (Level 2) > Policies (Level 3)
- **Human-in-the-Loop**: State-changing actions require confirmation
- **Proactive Detection**: SLA breaches, ticket clustering, cross-account analytics

## Architecture
User → Streamlit UI → FastAPI → Agent Router → SQLite/ChromaDB → Groq LLM


## Quick Start

### Prerequisites

- Python 3.10+
- Groq API Key ([Get it here](https://console.groq.com))

### Local Development

1. **Clone the repository**
```bash
git clone https://github.com/tanich04/parcelpilot-ai.git
cd parcelpilot-ai
```

2. **Create Virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Set up environment variables**
```bash
cp .env.example .env
# Edit .env and add your GROQ_API_KEY
```

5. **Ingest data**
```bash
python -c "from src.ingestion.data_loader import DataLoader; DataLoader().load_excel('data/excel/ParcelPilot_Assessment_Data.xlsx'); DataLoader().load_pdfs('data/pdfs')"
```

6. **Run the API**
```bash
python src/api/endpoints.py
```

7. **Run the UI (in another terminal)**
```bash
streamlit run src/ui/streamlit_app.py
```

## Tech Stack
| Component | Technology |
| :--- | :--- |
| Agent Framework | LangGraph |
| LLM | Groq |
| Vector Store | ChromaDB |
| Database | SQLite |
| Backend | FastAPI |
| Frontend | Streamlit |
---