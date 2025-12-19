# Troubleshooting Guide

This document lists common issues encountered during setup and their resolutions.

## Model Visibility Issues (Open WebUI)

### 1. No Models in Dropdown
If you open `http://localhost:3000` and see "No results found" in the model selector, check the following:

#### A. LiteLLM Authentication
Open WebUI requires the `LITELLM_MASTER_KEY` to discover models through the gateway.
- **Symptom**: LiteLLM logs show `401 Unauthorized` for `GET /models`.
- **Fix**: Ensure `OPENAI_API_KEY` is set to `${LITELLM_MASTER_KEY}` in the `open-webui` service environment in `docker-compose.yml`.

#### B. API Path Suffix
The OpenAI-compatible proxy in LiteLLM often requires the `/v1` suffix to route requests correctly.
- **Symptom**: Connectivity is established (200 OK) but no models are returned, or 404 errors appear.
- **Fix**: Ensure `OPENAI_API_BASE_URL` ends with `/v1` (e.g., `http://litellm:4000/v1`).

#### C. Containerized Ollama Connectivity
If using the `ollama` profile, LiteLLM must point to the internal container network.
- **Fix**: The `Makefile`'s `quickstart` target automatically sets `OLLAMA_API_BASE=http://ollama:11434` when the profile is active. If running manually, ensure this variable is set.

#### D. Missing Models in Ollama
If the connection is fine but the list is empty, the models may not have been pulled yet.
- **Fix**: Run `docker-compose exec ollama ollama list` to check. Use `ollama pull llama3.2` inside the container if it's empty.

## Service Connectivity

### 1. LiteLLM cannot reach Ollama
- **Symptom**: `Ollama connection error` in LiteLLM logs.
- **Fix**: If Ollama is on the **Host**, use `http://host.docker.internal:11434`. If Ollama is in **Docker**, use `http://ollama:11434`.

## RAG & Context Driver Issues

### 1. "Relation 'notes' does not exist" or Vanishing Data
This occurs when the `context-driver` shares the `public` schema with LiteLLM or Open WebUI. Their migrations may drop tables they don't recognize.
- **Schema Collisions**: Custom tables (`notes`, `edges`) were being dropped during other service migrations. (Resolved by using a dedicated `brain` schema and separate databases for each service).
- **LiteLLM Environment Variables**: Accidental deletion of `OLLAMA_API_BASE` and `LITELLM_MASTER_KEY` from `litellm` service caused `OllamaException - Cannot connect to host localhost:11434` errors. (Resolved by restoring these variables in `docker-compose.yml`).

 Ensure `db.py` uses `brain.notes` and `brain.edges`.

### 2. "Expecting value: line 1 column 1 (char 0)" Error
Open WebUI defaults to streaming chat responses. If the RAG proxy doesn't support streaming, the UI will fail to decode the response.
- **Symptom**: `Internal Server Error` in UI; `Error forwarding to LiteLLM` in `context-driver` logs.
- **Fix**: The `context-driver` must implement `StreamingResponse` from FastAPI to handle `stream=True` requests.

### 3. "No connected db" in LiteLLM
LiteLLM sometimes requires a database connection even for simple proxying of custom models (to store state/logs).
- **Symptom**: 400 Bad Request with message `No connected db`.
- **Fix**: Ensure `DATABASE_URL` is set in the `litellm` environment in `docker-compose.yml`.

### 4. JSON Serialization Errors (Metadata)
Ingesting files with YAML frontmatter containing dates (e.g., `date: 2023-10-27`) can break the PostgreSQL JSONB insert.
- **Symptom**: `TypeError: Object of type date is not JSON serializable`.
- **Fix**: The `context-driver` now automatically converts `date`/`datetime` objects to ISO strings before storage.

### 5. LiteLLM First-Run Delay
On the very first run with a database connected, LiteLLM applies ~50 migrations.
- **Symptom**: `curl` or UI requests return `Connection Refused` or time out for the first 2-3 minutes.
- **Fix**: Monitor `docker-compose logs -f litellm`. Wait for the `Uvicorn running on http://0.0.0.0:4000` message before testing RAG.
