# Fraud Detection System - Makefile

.PHONY: help install test lint format clean build deploy dev prod logs monitor

# Default target
help: ## Show this help message
	@echo "Fraud Detection System - Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

# Development setup
install: ## Install all dependencies
	@echo "Installing Python dependencies..."
	cd backend && pip install -r requirements.txt
	@echo "Installing Node.js dependencies..."
	cd frontend && npm install

dev: ## Start development environment
	@echo "Starting development environment..."
	docker-compose up -d
	cd backend && python main.py &
	cd frontend && npm start &

prod: ## Start production environment
	@echo "Starting production environment..."
	docker-compose -f docker-compose.prod.yml up -d

# Testing
test: ## Run all tests
	@echo "Running tests..."
	cd backend && python -m pytest tests/ -v --cov=.
	cd frontend && npm test -- --coverage

test-backend: ## Run backend tests only
	cd backend && python -m pytest tests/ -v --cov=.

test-frontend: ## Run frontend tests only
	cd frontend && npm test -- --coverage

# Code quality
lint: ## Run linting
	@echo "Running linters..."
	cd backend && flake8 . && black --check . && isort --check-only .
	cd frontend && npm run lint

format: ## Format code
	@echo "Formatting code..."
	cd backend && black . && isort .
	cd frontend && npm run format

security-scan: ## Run security scanning
	@echo "Running security scans..."
	cd backend && bandit -r . && safety check
	cd frontend && npm audit

# Building
build: ## Build all services
	@echo "Building services..."
	docker-compose build

build-backend: ## Build backend service
	docker build -t fraud-detection-backend backend/

build-frontend: ## Build frontend service
	docker build -t fraud-detection-frontend frontend/

# Deployment
deploy-dev: ## Deploy to development environment
	@echo "Deploying to development..."
	kubectl apply -f k8s/dev/

deploy-prod: ## Deploy to production environment
	@echo "Deploying to production..."
	kubectl apply -f k8s/prod/

terraform-init: ## Initialize Terraform
	cd terraform && terraform init

terraform-plan: ## Plan Terraform changes
	cd terraform && terraform plan

terraform-apply: ## Apply Terraform changes
	cd terraform && terraform apply

terraform-destroy: ## Destroy Terraform resources
	cd terraform && terraform destroy

# Monitoring and logs
logs: ## Show logs from all services
	docker-compose logs -f

logs-backend: ## Show backend logs
	docker-compose logs -f backend

logs-frontend: ## Show frontend logs
	docker-compose logs -f frontend

monitor: ## Open monitoring dashboards
	@echo "Opening Grafana dashboard..."
	open http://localhost:3000
	@echo "Opening API documentation..."
	open http://localhost:8000/docs

# Database operations
db-migrate: ## Run database migrations
	cd backend && alembic upgrade head

db-reset: ## Reset database (WARNING: destroys data)
	@echo "WARNING: This will destroy all data!"
	read -p "Are you sure? [y/N] " -n 1 -r; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker-compose down -v; \
		docker-compose up -d db; \
		sleep 10; \
		make db-migrate; \
	fi

# ML operations
train-models: ## Train ML models
	cd backend && python -c "from core.ensemble_model import EnsembleModel; model = EnsembleModel(); model.train()"

evaluate-models: ## Evaluate ML models
	cd backend && python -c "from core.ensemble_model import EnsembleModel; model = EnsembleModel(); model.evaluate()"

# Cleanup
clean: ## Clean up development environment
	@echo "Cleaning up..."
	docker-compose down -v
	docker system prune -f
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name node_modules -exec rm -rf {} +

clean-all: clean ## Clean up everything including Terraform state
	@echo "Cleaning everything..."
	cd terraform && terraform destroy -auto-approve
	rm -rf terraform/.terraform
	rm -rf backend/models/
	rm -rf mlflow/

# Utility
shell-backend: ## Open shell in backend container
	docker-compose exec backend bash

shell-db: ## Open shell in database container
	docker-compose exec db psql -U frauduser -d frauddetection

shell-redis: ## Open shell in Redis container
	docker-compose exec redis redis-cli

# Health checks
health: ## Check health of all services
	@echo "Checking service health..."
	@curl -s http://localhost:8000/health || echo "Backend unhealthy"
	@curl -s http://localhost:3000/api/health || echo "Grafana unhealthy"
	@docker-compose ps

# CI/CD simulation
ci: lint test security-scan build ## Run full CI pipeline locally

# Production operations
backup: ## Create database backup
	@echo "Creating database backup..."
	docker-compose exec db pg_dump -U frauduser frauddetection > backup_$(date +%Y%m%d_%H%M%S).sql

restore: ## Restore database from backup (specify file)
	@echo "Usage: make restore FILE=backup_file.sql"
	@if [ -z "$(FILE)" ]; then echo "Please specify FILE=backup_file.sql"; exit 1; fi
	docker-compose exec -T db psql -U frauduser frauddetection < $(FILE)

# Documentation
docs: ## Generate documentation
	@echo "Generating API documentation..."
	cd backend && python -c "from main import app; print('API docs at http://localhost:8000/docs')"
	@echo "Generating model documentation..."
	cd backend && python -c "from core.ensemble_model import EnsembleModel; help(EnsembleModel)"

# Performance testing
load-test: ## Run load testing
	@echo "Running load tests..."
	locust -f tests/load_test.py --host=http://localhost:8000

benchmark: ## Run performance benchmarks
	@echo "Running benchmarks..."
	cd backend && python -m pytest tests/ -k benchmark -v

# Emergency operations
emergency-stop: ## Emergency stop all services
	@echo "Emergency stop!"
	docker-compose down --remove-orphans
	kubectl delete pods --all --force --grace-period=0

emergency-restart: ## Emergency restart all services
	@echo "Emergency restart..."
	make emergency-stop
	sleep 5
	make prod