# VeriRag Core

VeriRag Core is a lightweight, containerized RAG (Retrieval-Augmented Generation) engine designed for internal use. It allows you to ingest documents and query them using Google Gemini.

## Features

- **Pure Gemini Stack**: Uses Google Gemini for both specific Embeddings (768-dim) and LLM Answer Generation.
- **RAG Engine**: Vector similarity search using PostgreSQL + pgvector.
- **Web Dashboard**: Simple UI for managing tenants and uploading files.
- **JSON API**: Programmatic access for external system integration.

## Setup

1.  **Environment Variables**:
    Copy `.env.example` to `.env` and set your keys:

    ```bash
    cp .env.example .env
    ```

    Required variables:
    - `GOOGLE_API_KEY`: A valid API key from Google AI Studio.
    - `GEMINI_MODEL`: e.g., `gemini-1.5-flash` or `gemini-2.0-flash`.

2.  **Run with Docker**:
    ```bash
    docker compose up -d --build
    ```

## Usage

### Web Dashboard

Open [http://localhost:8000](http://localhost:8000).

- **Default User**: `admin`
- **Default Password**: `admin`

### API Integration (External Callers)

#### 1. RAG Query (`/api/rag`)

Query your documents using vector search.

**Endpoint:** `POST /api/rag`
**Authentication:** Bearer Token (default: `vd`).

**Request (JSON):**

```json
{
	"tenant_id": 1,
	"message": "Your question here"
}
```

**Example (cURL):**

```bash
curl -X POST http://localhost:4017/api/rag \
  -H "Authorization: Bearer vd" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": 1,
    "message": "Hello world"
  }'
```

#### 2. Direct LLM (`/api/llm`)

Query Gemini directly without document context.

**Endpoint:** `POST /api/llm`
**Authentication:** Bearer Token (default: `vd`).

**Request (JSON):**

```json
{
	"message": "What is the capital of France?"
}
```

**Example (cURL):**

```bash
curl -X POST http://localhost:4017/api/llm \
  -H "Authorization: Bearer vd" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is the capital of France?"
  }'
```
