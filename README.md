# Renewal Reminders & Retention Outreach System

An AI-driven system for automating customer communication related to policy renewals, improving retention, and assisting customers with renewal-related actions.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (Next.js)                        │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │  Admin Dashboard │  │  Customer Chat  │  │    Analytics    │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Backend (FastAPI)                           │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────────┐ │
│  │ Policy API│  │Reminder   │  │Communication│ │  Tool Schemas │ │
│  │           │  │Scheduler  │  │  Gateway    │ │  (AI Tools)   │ │
│  └───────────┘  └───────────┘  └───────────────┘ └─────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AI Layer (Agent Framework)                    │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────────────┐│
│  │ Renewal Agent │  │ Query Handler │  │ Retention Specialist  ││
│  └───────────────┘  └───────────────┘  └───────────────────────┘│
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────────────┐│
│  │  RAG Module   │  │  Guardrails   │  │   Vector Memory       ││
│  └───────────────┘  └───────────────┘  └───────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Database (PostgreSQL + pgvector)                │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────────┐ │
│  │ Policies  │  │ Customers │  │ Reminders │  │  Embeddings   │ │
│  └───────────┘  └───────────┘  └───────────┘  └───────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## 📁 Project Structure

```
renewal-reminders/
├── frontend/                 # Next.js application
│   ├── app/                  # App router pages
│   ├── components/           # React components
│   └── lib/                  # Utilities and API clients
├── backend/                  # FastAPI application
│   ├── app/
│   │   ├── api/              # API routes
│   │   ├── models/           # SQLAlchemy models
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── services/         # Business logic
│   │   └── tools/            # AI agent tools
│   └── alembic/              # Database migrations
├── ai_agents/                # AI agent definitions
│   ├── agents/               # Agent implementations
│   ├── rag/                  # RAG pipeline
│   └── guardrails/           # Safety and validation
├── docker/                   # Docker configurations
└── docs/                     # Documentation
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- PostgreSQL with pgvector extension
- GitHub PAT (for AI models)

### 1. Clone and Setup

```bash
# Clone the repository
cd renewal-reminders

# Copy environment files
cp .env.example .env

# Start infrastructure
docker-compose up -d postgres redis

# Setup backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head

# Setup frontend
cd ../frontend
npm install
```

### 2. Configure Environment

Edit `.env` with your credentials:

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/renewals

# AI Model (GitHub Models - Free tier)
GITHUB_TOKEN=your_github_pat
AI_MODEL_ID=openai/gpt-4.1-mini

# Communication
SENDGRID_API_KEY=your_key
TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_token
```

### 3. Run Services

```bash
# Terminal 1: Backend
cd backend
uvicorn app.main:app --reload

# Terminal 2: Frontend
cd frontend
npm run dev

# Terminal 3: AI Agent Worker
cd ai_agents
python -m agents.worker
```

## 🔧 Technology Stack

| Component | Technology |
|-----------|------------|
| Frontend | Next.js 14, TypeScript, Tailwind CSS |
| Backend | FastAPI, SQLAlchemy, Pydantic |
| Database | PostgreSQL + pgvector |
| AI Framework | Microsoft Agent Framework |
| LLM | GitHub Models (gpt-4.1-mini) |
| Embeddings | SentenceTransformers |
| Scheduler | APScheduler |
| Deployment | Docker, Docker Compose |

## 📊 Features

### Core Capabilities

- ✅ Automated renewal reminders (30/15/7/1 days)
- ✅ Multi-channel delivery (Email, SMS, WhatsApp)
- ✅ RAG-powered customer query handling
- ✅ Personalized retention outreach
- ✅ Policy adjustment recommendations
- ✅ Real-time analytics dashboard

### AI Agent Tools

| Tool | Description |
|------|-------------|
| `get_policy_details` | Fetch policy information |
| `calculate_renewal_amount` | Compute renewal premium |
| `update_policy_status` | Process renewals |
| `search_policy_documents` | RAG document search |
| `send_reminder` | Trigger reminder delivery |
| `log_interaction` | Track conversations |

## 📖 Documentation

- [API Documentation](./docs/api.md)
- [Agent Configuration](./docs/agents.md)
- [Deployment Guide](./docs/deployment.md)
- [RAG Pipeline](./docs/rag.md)

## 🛡️ Guardrails & Safety

- Output schema enforcement
- Hallucination prevention
- Compliance filters for sensitive operations
- Rate limiting and abuse prevention

## 📈 Monitoring

- Reminder delivery statistics
- Customer engagement tracking
- Renewal conversion rate
- Agent latency and accuracy metrics

## 📄 License

MIT License
