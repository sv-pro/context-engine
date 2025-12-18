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
