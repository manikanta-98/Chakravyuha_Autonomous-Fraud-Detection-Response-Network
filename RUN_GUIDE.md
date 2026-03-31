# 🚀 Fraud Detection System - Complete Run Guide

## Quick Start (Recommended)

### 1. **Start Everything in One Command**

```bash
cd fraud-detection-system
docker-compose -f docker-compose.prod.yml up -d
```

Wait 2-3 minutes for all services to fully start and initialize.

### 2. **Verify All Services Are Running**

```bash
docker-compose -f docker-compose.prod.yml ps
```

You should see 11 services running:
- backend
- frontend
- db (PostgreSQL)
- redis
- zookeeper
- kafka
- mlflow
- prometheus
- grafana
- (and their support services)

### 3. **Access the Applications**

| Service | URL | Credentials |
|---------|-----|-------------|
| **Frontend Dashboard** | http://localhost:3000 | No auth required |
| **API Documentation** | http://localhost:8000/docs | Interactive Swagger UI |
| **Grafana Dashboards** | http://localhost:3000 | admin / admin |
| **MLflow Dashboard** | http://localhost:5000 | No auth required |
| **Prometheus Metrics** | http://localhost:9090 | No auth required |

## Individual Component Control

### Start Development Environment (with hot reload)
```bash
docker-compose up -d
```

### Stop All Services
```bash
docker-compose -f docker-compose.prod.yml down
```

### Remove All Data and Start Fresh
```bash
docker-compose -f docker-compose.prod.yml down -v
docker-compose -f docker-compose.prod.yml up -d
```

### View Logs
```bash
# All services
docker-compose -f docker-compose.prod.yml logs -f

# Specific service
docker-compose -f docker-compose.prod.yml logs -f backend
docker-compose -f docker-compose.prod.yml logs -f frontend
docker-compose -f docker-compose.prod.yml logs -f db
```

## Available Make Commands (If Make is installed)

```bash
# Show all available commands
make help

# Install dependencies
make install

# Development environment
make dev

# Production environment
make prod

# Run tests
make test

# Check health
make health

# View logs
make logs

# Monitor dashboards
make monitor

# Cleanup
make clean
```

## System Architecture

```
┌────────────────────────────────────────────────────────┐
│         Frontend Dashboard (React 18)                    │
│         Port: 3000                                       │
└────────────────────────────────────────────────────────┘
                         ↓
┌────────────────────────────────────────────────────────┐
│         FastAPI Backend                                  │
│         Port: 8000 (/docs for API explorer)            │
│         Features:                                        │
│         - WebSocket real-time updates                   │
│         - JWT authentication                            │
│         - Rate limiting                                 │
│         - Prometheus metrics                            │
└────────────────────────────────────────────────────────┘
         ↓           ↓           ↓
┌──────────────┬──────────────┬──────────────┐
│   Redis      │  PostgreSQL  │    Kafka     │
│   Port: 6379 │  Port: 5432  │  Port: 9092  │
│   Caching    │  Database    │  Streaming   │
└──────────────┴──────────────┴──────────────┘
         
┌────────────────────────────────────────────┐
│  Monitoring & Observability                │
├────────────────────────────────────────────┤
│  Prometheus (Port: 9090) - Metrics         │
│  Grafana (Port: 3000) - Dashboards         │
│  MLflow (Port: 5000) - Model Registry      │
└────────────────────────────────────────────┘
```

## Key Features

### 🤖 **6 Async Agents**
- Monitoring Agent
- Pattern Detection Agent
- Risk Assessment Agent
- Alert Blocking Agent
- Compliance Agent
- Learning Agent

### 🧠 **Ensemble ML Models**
- XGBoost
- LightGBM
- CatBoost
- Scikit-learn
- SHAP/LIME Explainability

### 📊 **Performance Targets**
- **Latency**: <300ms (95th percentile)
- **Throughput**: 1000+ TPS
- **Uptime**: 99.9%
- **Accuracy**: >95%

## Troubleshooting

### Services Won't Start
```bash
# Clean up and retry
docker-compose -f docker-compose.prod.yml down
docker system prune -f
docker-compose -f docker-compose.prod.yml up -d
```

### Database Connection Issues
```bash
# Check PostgreSQL logs
docker-compose -f docker-compose.prod.yml logs db

# Reset database
docker-compose -f docker-compose.prod.yml down -v
docker-compose -f docker-compose.prod.yml up -d db
```

### Port Already in Use
```bash
# Find which service is using the port
netstat -ano | findstr ":8000"  # For Windows

# Either stop that service or change the port in docker-compose.prod.yml
```

### Memory Issues
```bash
# Check Docker resources
docker stats

# Reduce services: edit docker-compose.prod.yml and remove unnecessary services
```

## Testing the System

### 1. **Check API Health**
```bash
curl http://localhost:8000/health
```

### 2. **Test WebSocket Connection**
Access http://localhost:3000 and check browser console for WebSocket messages

### 3. **View Fraud Predictions**
```bash
curl -X POST http://localhost:8000/api/v1/predict \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 1000,
    "merchant_id": "M123",
    "transaction_time": "2026-03-25T10:00:00Z"
  }'
```

### 4. **Check Metrics**
- Visit http://localhost:9090 for raw metrics
- Visit http://localhost:3000 for Grafana dashboards

## Deployment to Kubernetes

### Prerequisites
```bash
# Configure kubectl
aws eks update-kubeconfig --region us-east-1 --name fraud-detection-eks

# Apply Kubernetes manifests
kubectl apply -f k8s/
kubectl apply -f monitoring/
```

### Verify Deployment
```bash
kubectl get pods -n fraud-detection
kubectl get svc -n fraud-detection
```

## Useful Commands

```bash
# Database operations
docker-compose -f docker-compose.prod.yml exec db psql -U frauduser -d frauddetection

# Redis operations
docker-compose -f docker-compose.prod.yml exec redis redis-cli

# View all environment variables
docker-compose -f docker-compose.prod.yml config

# Restart a specific service
docker-compose -f docker-compose.prod.yml restart backend

# Scale a service (not available in prod.yml, use dev compose instead)
docker-compose up --scale worker=3
```

## Performance Monitoring

### Real-time Metrics
- **Grafana** (http://localhost:3000): Pre-built dashboards for system health, API performance, model metrics

### Advanced Monitoring
- **Prometheus** (http://localhost:9090): Query raw metrics with PromQL
- **API Metrics** (http://localhost:8000/metrics): Prometheus format metrics

### Model Performance
- **MLflow** (http://localhost:5000): Track model versions, parameters, metrics, and artifacts

## Documentation

- **API Docs**: http://localhost:8000/docs (Interactive Swagger UI)
- **Project README**: See `README.md` in project root
- **Architecture**: See `terraform/README.md` for infrastructure details
- **Agent Details**: See `backend/agents/` directory

## Emergency Operations

### Restart Everything
```bash
docker-compose -f docker-compose.prod.yml restart
```

### Emergency Stop (Force quit all)
```bash
docker-compose -f docker-compose.prod.yml kill
docker container prune -f
```

### Full System Reset
```bash
docker-compose -f docker-compose.prod.yml down -v
rm -rf postgres_data redis_data
docker-compose -f docker-compose.prod.yml up -d
```

## Support & Debugging

1. **Check Logs**: `docker-compose -f docker-compose.prod.yml logs -f [service]`
2. **Inspect Containers**: `docker inspect [container-id]`
3. **Check Resource Usage**: `docker stats`
4. **Network Diagnostics**: `docker network inspect fraud-detection-system_default`

---

**Version**: 1.0.0  
**Last Updated**: March 25, 2026  
**Status**: Production Ready ✅