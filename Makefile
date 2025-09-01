# Cylvy Digital Landscape Analyzer - Makefile

.PHONY: help setup check-env init-db start stop logs clean test

help: ## Show this help message
	@echo "Cylvy Digital Landscape Analyzer Commands"
	@echo "========================================"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup: check-env init-db ## Complete setup (check environment + initialize database)
	@echo "✅ Setup completed! Run 'make start' to launch the application"

check-env: ## Check environment configuration
	@echo "🔍 Checking environment configuration..."
	@python scripts/setup.py check

init-db: ## Initialize database schema and create admin user
	@echo "🗄️  Initializing database..."
	@python scripts/setup.py init

start: ## Start all services
	@echo "🚀 Starting Cylvy Digital Landscape Analyzer..."
	@docker-compose up -d
	@echo "✅ Services started!"
	@echo "   Frontend: http://localhost:3000"
	@echo "   Backend:  http://localhost:8000"
	@echo "   API Docs: http://localhost:8000/docs"

stop: ## Stop all services
	@echo "🛑 Stopping services..."
	@docker-compose down

restart: stop start ## Restart all services

logs: ## Show application logs
	@docker-compose logs -f

logs-backend: ## Show backend logs only
	@docker-compose logs -f backend

logs-frontend: ## Show frontend logs only
	@docker-compose logs -f frontend

logs-db: ## Show database logs only
	@docker-compose logs -f db

health: ## Check database health
	@python scripts/setup.py health

clean: ## Clean up containers and volumes
	@echo "🧹 Cleaning up..."
	@docker-compose down -v
	@docker system prune -f

build: ## Rebuild all containers
	@echo "🔨 Building containers..."
	@docker-compose build --no-cache

test: ## Run tests
	@echo "🧪 Running tests..."
	@docker-compose exec backend python -m pytest tests/ -v

shell-backend: ## Open shell in backend container
	@docker-compose exec backend /bin/bash

shell-db: ## Open PostgreSQL shell
	@docker-compose exec db psql -U cylvy cylvy_analyzer

backup-db: ## Backup database
	@echo "💾 Creating database backup..."
	@docker-compose exec db pg_dump -U cylvy cylvy_analyzer > backup_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "✅ Backup created"

restore-db: ## Restore database from backup (usage: make restore-db BACKUP=backup_file.sql)
	@echo "📥 Restoring database from $(BACKUP)..."
	@docker-compose exec -T db psql -U cylvy cylvy_analyzer < $(BACKUP)
	@echo "✅ Database restored"

dev: ## Start in development mode with hot reloading
	@echo "🔧 Starting in development mode..."
	@docker-compose -f docker-compose.dev.yml up -d

# Deployment commands
deploy-prod: ## Deploy to production
	@echo "🚀 Deploying to production..."
	@docker-compose -f docker-compose.prod.yml up -d

update: ## Update application (pull latest, rebuild, restart)
	@echo "📦 Updating application..."
	@git pull origin master
	@docker-compose build
	@docker-compose up -d
	@echo "✅ Update completed"

# Development helpers
install-deps: ## Install development dependencies
	@echo "📦 Installing dependencies..."
	@cd backend && pip install -r requirements.txt
	@cd frontend && npm install

format: ## Format code
	@echo "🎨 Formatting code..."
	@cd backend && black app/ --line-length 100
	@cd frontend && npm run format

lint: ## Lint code
	@echo "🔍 Linting code..."
	@cd backend && flake8 app/ --max-line-length 100
	@cd frontend && npm run lint

# Default target
all: setup start
