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

# Quickstart: Stop, Rebuild, Start
quickstart:
	@echo "Restarting system..."
	docker-compose down
	docker-compose up -d --build
	@echo "System restarted!"

# Start services
start:
	docker-compose up -d

# Stop services
stop:
	docker-compose stop

# Show status
status:
	docker-compose ps
