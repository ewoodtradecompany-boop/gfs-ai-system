# GFS AI System — Stage 0

Global AI Business Management System for Green Fuel's EPM commercialisation.  
**Current stage:** Zero-Budget Bootstrap — Meeting Scribe agent, local Ollama, $0/month.

> Master architecture: `docs/GFS-PM-002-ESA-v2.1-FINAL.docx`

---

## Quick Start

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [Ollama](https://ollama.com/download) — or use the Docker service below
- Python 3.11+

### 1. Start the stack

```bash
docker compose up -d
```

Starts: **PostgreSQL 16** (port 5432) · **Redis 7** (6379) · **Qdrant** (6333) · **Ollama** (11434)  
CRM schema is applied automatically on first start.

### 2. Pull the LLM

```bash
# Requires ~4 GB download
ollama pull mistral:7b
```

> `mistral:7b` runs on CPU with 8 GB RAM. For better quality on a GPU server, use `llama3.3:70b` — update `OLLAMA_MODEL` in `.env`.

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment

```bash
cp .env.example .env
# Edit .env if your DB password or Ollama host differs from defaults
```

### 5. Seed demo data

```bash
python scripts/seed_demo_data.py
```

Creates 3 demo CRM contacts (UAE, Nigeria, India).

### 6. Process a transcript

```bash
python agents/meeting_scribe/agent.py --transcript tests/fixtures/demo_transcript.txt
```

Optional — link to a CRM contact:
```bash
python agents/meeting_scribe/agent.py --transcript path/to/meeting.txt --contact-id 2
```

### 7. Check the result

```bash
# Requires psql client or any PostgreSQL GUI (DBeaver, TablePlus)
psql postgresql://gfs:gfs@localhost:5432/gfsdb \
  -c "SELECT id, sentiment, summary, next_step FROM meetings ORDER BY created_at DESC LIMIT 3;"
```

### 8. Run tests

```bash
# Integration test — requires docker stack + ollama running
pytest tests/test_meeting_scribe.py -v
```

---

## Project structure

```
gfs-ai-system/
├── agents/meeting_scribe/   # Meeting Scribe agent (Stage 0)
├── crm/schema.sql           # PostgreSQL schema
├── docs/                    # GFS-PM-002-ESA-v2.1-FINAL.docx (add manually)
├── prompts/                 # Versioned agent system prompts
├── scripts/                 # Utility scripts (seed, migration)
└── tests/                   # Integration tests + fixtures
```

---

## Deployment roadmap

| Stage | Hosting | Notes |
|---|---|---|
| **Stage 0** *(now)* | Local Docker Compose | $0, offline, dev only |
| **Beta** | Oracle Cloud Always Free (24 GB ARM) | $0, remote access, same Docker Compose |
| **Phase 0** | Hetzner CAX21 (~€7/mo) | VPS, all services, mistral:7b |
| **Phase 1+** | Own KEZAD server (GPU) | llama3.3:70b, K3s, full architecture per GFS-PM-002 |

Docker Compose throughout — no code rewrite when migrating between stages.

**To deploy on a remote server:**
```bash
# On the server (Ubuntu 22.04+)
git clone https://github.com/<org>/gfs-ai-system.git
cd gfs-ai-system
cp .env.example .env  # fill in production values
docker compose up -d
ollama pull mistral:7b
```

---

## What's NOT built yet (future phases)

Kong API Gateway · Keycloak SSO · K3s/Kubernetes · LangGraph multi-agent · MCP servers · Fireflies API integration · FastAPI microservices · n8n automation

See `docs/GFS-PM-002-ESA-v2.1-FINAL.docx` for the full phased roadmap.
