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
	@echo "Important Endpoints:"
	@echo "--------------------"
	@echo "  Open WebUI: http://localhost:3000"
	@echo "  LiteLLM:    http://localhost:4000"
	@echo ""

# Quickstart: Stop, Rebuild, Start
quickstart: check_env
	@echo "Restarting system..."
	docker-compose down
	docker-compose up -d --build
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
