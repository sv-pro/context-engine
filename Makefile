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
	fi
	@echo ""

# Quickstart: Stop, Rebuild, Start
quickstart: check_env
	@echo "Restarting system..."
	docker-compose down
	@if [ -z "$(PROFILE)" ]; then \
		docker-compose up -d --build; \
	else \
		docker-compose --profile $(PROFILE) up -d --build; \
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
