.PHONY: help quickstart status stop start

# Default target: show help
help:
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  quickstart  Stop current system, rebuild, and start anew"
	@echo "  start       Start services (detached mode)"
	@echo "  stop        Stop services"
	@echo "  status      Show status of services"

# Check requirements
check_env:
	@if [ ! -f .env ]; then \
		echo "Error: .env file not found. Please create one from .env.example or manually."; \
		exit 1; \
	fi

# Show endpoints
endpoints:
	@echo ""
	@echo "Available Endpoints:"
	@echo "--------------------"
	@RUNNING=$$(docker-compose ps --services --filter "status=running"); \
	if echo "$$RUNNING" | grep -q "open-webui"; then \
		echo "  Open WebUI: http://localhost:3000"; \
	fi; \
	if echo "$$RUNNING" | grep -q "litellm"; then \
		echo "  LiteLLM:    http://localhost:4000"; \
	fi; \
	if echo "$$RUNNING" | grep -q "context-driver"; then \
		echo "  Dashboard:  http://localhost:8000/cost-dashboard"; \
	fi
	@echo ""

# Quickstart: Stop, Rebuild, Start
quickstart: check_env
	@echo "Restarting system..."
	@if [ -z "$(PROFILE)" ]; then \
		docker-compose up -d --build; \
	else \
		OLLAMA_API_BASE=http://ollama:11434 docker-compose --profile $(PROFILE) up -d --build; \
		echo "Checking for Ollama models..."; \
		if ! docker-compose exec ollama ollama list | grep -q "llama3.2"; then \
			echo "Pulling llama3.2 model (this may take a while)..."; \
			docker-compose exec ollama ollama pull llama3.2; \
		fi; \
		if ! docker-compose exec ollama ollama list | grep -q "nomic-embed-text"; then \
			echo "Pulling nomic-embed-text model..."; \
			docker-compose exec ollama ollama pull nomic-embed-text; \
		fi; \
	fi
	@echo "Waiting for services to be ready..."
	@timeout=60; \
	while ! curl -s -f -o /dev/null http://localhost:3000/health; do \
		if [ $$timeout -le 0 ]; then \
			echo "Timed out waiting for Open WebUI"; \
			exit 1; \
		fi; \
		printf "."; \
		sleep 2; \
		timeout=$$((timeout-2)); \
	done
	@echo ""
	@echo "System restarted!"
	@$(MAKE) endpoints

# Start services
start: check_env
	docker-compose up -d
	@$(MAKE) endpoints

# Stop services
stop:
	docker-compose stop

# Show status
status:
	docker-compose ps
	@$(MAKE) endpoints
