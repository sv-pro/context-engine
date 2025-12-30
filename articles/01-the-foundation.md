# Part 1: The Foundation

> *Docker, Open WebUI, and the Makefile that started it all*

**Commits:** `2c08137` → `6021270`

---

## The Vision

Every complex system starts with a simple idea. Mine was: **"I want a local AI assistant with a nice chat interface."**

Not a CLI tool. Not another API wrapper. A proper, persistent, chat-based interface that could work with any LLM — local or hosted.

## The Initial Stack

Two Docker containers brought the vision to life:

### Open WebUI
The chat interface. Clean, modern, supports markdown, conversation history, and user management. Most importantly: it speaks **OpenAI-compatible API**.

### LiteLLM
The universal translator. Point Open WebUI at LiteLLM, and suddenly you can use:
- Local Ollama models
- OpenAI GPT-4
- Anthropic Claude
- Google Gemini
- Any OpenAI-compatible endpoint

One interface, all models.

## The Docker Compose File

```yaml
version: '3.8'
services:
  open-webui:
    image: ghcr.io/open-webui/open-webui:main
    ports:
      - "3000:8080"
    environment:
      - OPENAI_API_BASE=http://litellm:4000/v1
      
  litellm:
    image: ghcr.io/berriai/litellm:main-latest
    ports:
      - "4000:4000"
    volumes:
      - ./config/litellm:/app/config
```

Simple. Two services. One network.

## The Makefile Revolution

Nobody wants to type `docker-compose up -d` repeatedly. So a Makefile appeared:

```makefile
start:
	docker-compose up -d

stop:
	docker-compose down

status:
	@docker-compose ps

logs:
	docker-compose logs -f
```

Then refinements:
- **Environment checks** — fail fast if `.env` is missing
- **Endpoint display** — show URLs after startup
- **Smart status** — only show what's actually running

```makefile
status:
	@echo "=== Running Services ==="
	@docker-compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
	@echo ""
	@echo "=== Endpoints ==="
	@[ "$$(docker-compose ps -q open-webui)" ] && echo "Open WebUI: http://localhost:3000" || true
	@[ "$$(docker-compose ps -q litellm)" ] && echo "LiteLLM:    http://localhost:4000" || true
```

## Lessons Learned

1. **Docker Compose is infrastructure-as-code for local dev** — version control your docker-compose.yml
2. **Makefiles are underrated** — they're a universal task runner with zero dependencies
3. **Show endpoints on startup** — developers shouldn't hunt for URLs
4. **Fail fast** — check for required files/env vars before proceeding

## What's Next

At this point, the system could chat. But it had no memory beyond conversation history. It couldn't search documents. It was just a pretty wrapper around LLMs.

That changes in Part 2, where we add **PostgreSQL, pgvector, and the Context Driver**.

---

[← Back to Index](./README.md) | [Next: Memory & Intelligence →](./02-memory-and-intelligence.md)
