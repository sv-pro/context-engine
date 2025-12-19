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
	@echo "  rebuild     Rebuild all images from scratch"
	@echo "  rebuild-driver Rebuild only the context-driver"
	@echo "  flush       Stop system and delete all volumes (factory reset)"
	@echo "  presentation Show the project intro presentation path"

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
	@echo "Waiting for Open WebUI (port 3000)..."
	@timeout=60; \
	while ! curl -s -f -o /dev/null http://localhost:3000/health; do \
		if [ $$timeout -le 0 ]; then echo "Open WebUI timed out"; exit 1; fi; \
		printf "."; sleep 2; timeout=$$((timeout-2)); \
	done
	@echo "Waiting for Context Driver (port 8000)..."
	@timeout=30; \
	while ! curl -s -f -o /dev/null http://localhost:8000/health; do \
		if [ $$timeout -le 0 ]; then echo "Context Driver timed out"; exit 1; fi; \
		printf "."; sleep 1; timeout=$$((timeout-1)); \
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

# Rebuild all
rebuild: stop
	docker-compose build --no-cache
	docker-compose up -d --force-recreate
	@$(MAKE) quickstart

# Rebuild only driver
rebuild-driver:
	docker-compose build --no-cache context-driver
	docker-compose up -d --force-recreate context-driver

# Factory Reset
flush:
	docker-compose down -v
	@echo "All volumes deleted. System is clean."

# Show presentation path
presentation:
	@echo "Project Presentation (Reveal.js) is available at:"
	@echo "file://$(realpath volumes/brain/presentation/index.html)"
	@echo ""
	@echo "Open this file in your browser to view the walkthrough."
