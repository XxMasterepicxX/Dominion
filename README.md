# Dominion Real Estate Intelligence

> Autonomous multi-agent due diligence for institutional real estate teams.

Dominion is an AI-native intelligence layer for real estate acquisition teams. It blends multi-agent reasoning on Amazon Bedrock with rich property, ordinance, and entity data to surface actionable buy/hold/pass recommendations backed by verifiable evidence.

## Submission for AWS AI Agent Global Hackathon

This project is a submission for the AWS AI Agent Global Hackathon.
* **Team:** Cesar Valentin, Colgan Miller, and Vasco Hinostroza.

## Demo

[Link to 3-minute Demo Video]

## The Problem

Real estate developers and acquisition teams face overwhelming due diligence workloads: synthesizing parcel data, zoning ordinances, historical permits, market trends, and competitor activity often takes weeks. Decisions made with stale or incomplete intelligence translate into missed opportunities and costly mistakes, especially in fast-moving secondary markets like Gainesville, FL.

## Our Solution

Dominion delivers an autonomous, multi-agent analyst that reasons over institutional-grade data using Amazon Bedrock. A Bedrock AgentCore supervisor (Nova Premier) orchestrates four specialist agents (Nova Lite) that each command Lambda-hosted tools. Those tools query an Aurora PostgreSQL + pgvector knowledge store, run ordinance RAG lookups using a custom-trained embedding model (replacing Titan due to poor performance), and trigger enrichment workflows. The result is a defensible recommendation (buy / hold / pass) complete with confidence scores, supporting evidence, and next actions that the web dashboard can surface to deal teams in minutes instead of weeks.

## Architecture

`[Architecture Diagram image]`

The frontend (React + TypeScript + Vite) collects analyst prompts and streams progress updates. A Bedrock AgentCore app hosted on Lambda Function URLs orchestrates the workflow: the supervisor agent decomposes the task, specialists call Lambda tools for property search, ordinance RAG, and enrichment, and the custom-embedded Aurora pgvector store returns ground-truth evidence. Infrastructure is provisioned via AWS CDK: Aurora Serverless v2 (RDS Data API + Secrets Manager), dedicated tool Lambdas, and the AgentCore multi-agent runtime. Logs, health pings, and long-running sessions are handled inside AgentCore so the agents stay responsive throughout 10–20 minute analyses.

## Tech Stack & AWS Services

### AWS Services Used
* **Amazon Bedrock (Nova):** Powers core reasoning (Nova Premier + Nova Lite). We use our own custom embedding model for ordinance vector search instead of Titan (`infrastructure/lambda/rag/handler.py`).
* **Amazon Bedrock AgentCore:** Hosts the supervisor + specialist agents and exposes `/invocations` endpoints via `BedrockAgentCoreApp` (`infrastructure/agentcore_agent/dominion_multiagent.py`).
* **AWS Lambda:** Runs 12 tool endpoints—Intelligence, RAG, and Enrichment handlers that the agents invoke through the AWS SDK (`infrastructure/lambda/**/handler.py`).
* **Amazon Aurora PostgreSQL Serverless v2 (pgvector):** Stores 108K properties, 89K entities, and vectorized ordinance chunks using our custom embedding model for low-latency retrieval (`infrastructure/app.py`, `infrastructure/lambda/rag/handler.py`).
* **Amazon RDS Data API:** Enables serverless SQL access from Lambda without VPC cold starts (`infrastructure/lambda/intelligence/handler.py`).
* **AWS Secrets Manager:** Supplies the `SECRET_ARN` used by Lambdas to fetch Aurora credentials at runtime.
* **AWS CDK:** Defines the full stack (Aurora, Lambdas, AgentCore) in code for reproducible deployments (`infrastructure/app.py`).

### Core Technologies
* **Backend:** Python 3.12, Strands Agents on Bedrock AgentCore, asynchronous data services with `asyncpg`, `SQLAlchemy`, `structlog`, and Lambda tool wrappers (`infrastructure/agentcore_agent/dominion_agent.py`, `src/database/connection.py`).
* **Frontend:** React 18 + TypeScript (Vite), with `framer-motion`, `react-globe.gl`, `leaflet`, `tailwind-merge`, and `clsx` for immersive data storytelling (`frontend/package.json`, `frontend/src/components/*`).
* **Database:** Aurora PostgreSQL + pgvector (with local Postgres/Redis via Docker Compose) seeded from `src/database/schema_v2_multimarket.sql`.
* **Libraries:** `bedrock-agentcore`, `strands-agents`, `boto3`, `patchright`, `beautifulsoup4`, `pandas`, `torch`, plus frontend tooling (`react-router-dom`, `vitest`, `@testing-library/react`).

## How to Run it Locally

### Prerequisites
* AWS CLI configured with credentials that can invoke Bedrock and provision infrastructure.
* AWS CDK v2 (`npm install -g aws-cdk`) bootstrapped for your target account/region.
* Python 3.12 (for AgentCore runtime and Lambda tooling).
* Node.js v18+ and npm.
* Docker & Docker Compose (for local Postgres + Redis mirrors).
* (Optional) Tesseract OCR and system packages if you plan to exercise document ingestion locally.

### Backend Setup
```bash
# Clone the repository
git clone [Your Repo URL]
cd Dominion

# Launch local data stores (Postgres + Redis) for development
docker-compose up -d

# Python virtual environment
python -m venv .venv
# Windows
.\.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

# Install core API / tooling dependencies
pip install -r requirements.txt
pip install -r src/requirements.txt

# Copy and edit environment variables
cp .env.example .env
# Populate Aurora connection strings, Redis URL, and Bedrock model IDs as needed

# (Optional) Seed local Postgres with the provided schema
psql -h localhost -U postgres -d dominion -f src/database/schema_v2_multimarket.sql
```

To run the Bedrock AgentCore app locally (served on port 8080 by default):

```bash
cd infrastructure/agentcore_agent
pip install -r requirements.txt
python dominion_agent.py               # single-agent supervisor
# or
python dominion_multiagent.py          # supervisor + 4 specialists
```

This exposes the AgentCore `/invocations` endpoint at `http://localhost:8080/invocations`, mirroring the production Lambda Function URL.

If you need to deploy AWS infrastructure (Aurora, Lambdas, AgentCore) from scratch:

```bash
cd infrastructure
pip install -r requirements.txt
cdk bootstrap
cdk deploy
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Provide environment config (create .env.local or edit .env)
echo "VITE_AGENT_URL=http://localhost:8080/invocations" > .env.local
echo "REACT_APP_API_BASE_URL=http://localhost:8000" >> .env.local

# Start the development server
npm run dev
```

Point your browser to the printed Vite URL (typically `http://localhost:5173`). Submit prompts from the dashboard; the app will call the locally running AgentCore endpoint or fall back to mock data if services are unavailable.

## Challenges We Faced & What We Learned

Coordinating multi-minute, multi-agent workflows required aggressive use of Bedrock AgentCore health pings to avoid Lambda timeouts, and tuning Titan embeddings against pgvector highlighted the importance of dimensionality checks and normalization (`infrastructure/lambda/rag/handler.py`). We found that Titan embeddings yielded only ~60% retrieval accuracy, so we built our own embedding model optimized for ordinance data, achieving higher recall and semantic alignment. We also learned that declarative infrastructure with CDK made iterating on Aurora/Lambda contracts far faster than manual CloudFormation templating.

## What's Next?

  * Extend the tool belt with live scrapers (QPublic, SunBiz) running in containers behind asynchronous queues.
  * Harden the reasoning layer with evaluator loops and scenario simulations for ambiguous markets.
  * Package Dominion as a managed AgentCore blueprint and publish to AWS Marketplace for partner deployments.
