# RentOut RAG Chatbot

Deployment-focused async RAG chatbot for RentOut, a furniture rental company.

The project is intentionally built to explain production readiness concepts without Kubernetes:

- FastAPI async endpoints
- OpenAI chat and embedding calls
- local prompt registry
- detailed RentOut `.docx` policy corpus
- semantic-style chunking with metadata
- local JSON vector store
- local JSONL audit logging
- Docker and Docker Compose
- GitHub Actions CI
- Docker image versioning with Git SHA and release tags

## What This Project Teaches

This is a small RAG chatbot, but it is structured like a production service:

1. Configuration comes from `.env`, not hardcoded secrets.
2. Documents are treated as source data and ingested into a vector store.
3. API requests are validated with Pydantic schemas.
4. Independent I/O tasks run concurrently with `asyncio`.
5. Answers are generated only after relevant context is retrieved.
6. Citations are returned from retrieval metadata, not invented by the LLM.
7. Audit logs are written for every success and failure.
8. Docker and GitHub Actions show how the app would move through CI and image builds.

## Step-By-Step Flow

1. `scripts/generate_rentout_docs.py`

   Creates realistic RentOut Word documents in `app/data/source_docs`. These are the knowledge base for the chatbot. They include rental agreements, delivery rules, deposit policies, repair rules, subscription billing, support escalation, and privacy policies.

2. `scripts/ingest_docs.py` or `POST /ingest`

   Reads every `.docx` file, extracts paragraphs, pulls metadata from the document header, chunks the text, calls the OpenAI embedding model, and saves a local JSON vector store at `app/data/vector_store/rentout_vectors.json`.

3. `POST /chat`

   Accepts a user question like “Can I cancel after delivery?” and validates it with `ChatRequest`.

4. Async prompt and retrieval work

   The route starts two tasks at the same time:

   - `load_prompt("customer_chat")` reads the system prompt.
   - `retrieve_context(...)` embeds the question and finds the most relevant chunks.

   These tasks are independent, so the API does not make one wait behind the other.

5. GPT answer generation

   `generate_answer(...)` combines the prompt, user question, customer type, and retrieved chunks. The answer is grounded because the model receives policy text as context.

6. Citation attachment

   The API returns document names, sections, versions, source paths, and similarity scores from the retrieved chunks.

7. Audit logging

   `write_audit_event(...)` writes one JSONL row with latency, status, question, and retrieved documents. This gives a simple local example of production observability.

## Important Parameters

`OPENAI_API_KEY`

Your private OpenAI key. Keep it in `.env`. Do not commit it.

`OPENAI_CHAT_MODEL`

The model used to generate final answers.

`OPENAI_EMBEDDING_MODEL`

The model used to convert policy chunks and user questions into vectors. The same embedding model must be used for ingestion and retrieval.

`TOP_K`

How many retrieved chunks are sent to the LLM. Higher values give more context but increase latency and token usage.

`CHUNK_SIZE`

Approximate character size for each chunk. Smaller chunks are more precise; larger chunks preserve more surrounding context.

`CHUNK_OVERLAP`

How many trailing characters from one chunk are repeated in the next chunk. This protects meaning near chunk boundaries.

`VECTOR_STORE_PATH`

Where the local JSON vector store is written. In a real deployment this boundary could become Chroma, pgvector, Pinecone, or another vector database.

`AUDIT_LOG_DIR`

Where request audit logs are written. In production this boundary could become CloudWatch, Datadog, ELK, or a warehouse ingestion pipeline.

## Run Locally

```bash
python -m pip install -r requirements.txt
python scripts/generate_rentout_docs.py
python scripts/ingest_docs.py
python -m uvicorn app.main:app --reload
```

API docs:

```text
http://127.0.0.1:8000/docs
```

## Run With Docker

```bash
docker compose up --build
```

## Test

```bash
python -m pytest -q
```

## Key Endpoints

```text
GET  /health
GET  /version
POST /chat
POST /ingest
```

## Async Design

The `/chat` endpoint starts prompt loading and retrieval at the same time with `asyncio.create_task`, then waits for both using `asyncio.gather`.

That means the API does not block one I/O step behind another. Today those calls read local prompt/vector files and OpenAI APIs. Later, the same async boundaries can point to LangSmith, external prompt registries, remote vector databases, or cloud audit sinks without rewriting the route shape.

## Project Shape

```text
app/
  main.py
  api/
    routes_chat.py
    routes_health.py
  core/
    config.py
  rag/
    audit.py
    chunking.py
    embeddings.py
    generator.py
    prompt_loader.py
    retriever.py
    schemas.py
  data/
    prompts/
    source_docs/
    audit_logs/
    vector_store/
scripts/
  generate_rentout_docs.py
  ingest_docs.py
  smoke_test.py
tests/
.github/workflows/
Dockerfile
docker-compose.yml
```