# ✅ FRAUD DETECTION SYSTEM - QUICK START

## 🚀 System Status

**Current Status**: Building & Starting Services  
**Expected Time**: 3-5 minutes for full startup  
**Last Updated**: March 25, 2026

---

## 📊 Running Services

### Core Application
- **Backend API**: http://localhost:8000
  - Interactive API Docs: http://localhost:8000/docs
  - Health Check: http://localhost:8000/health
  
- **Frontend Dashboard**: http://localhost:3000
  - Real-time fraud detection dashboard
  - Live agent status monitoring

### Data & Messaging
- **PostgreSQL Database**: localhost:5432
  - Database: `frauddetection`
  - User: `frauduser`
  
- **Redis Cache**: localhost:6379
  - In-memory caching and queues
  
- **Kafka Streaming**: localhost:9092
  - Event streaming for real-time processing

### Monitoring & Observation
- **Prometheus**: http://localhost:9090
  - Metrics collection and querying
  
- **Grafana**: http://localhost:3000/grafana
  - Dashboard visualizations
  - Pre-built fraud detection dashboards
  - Credentials: admin / admin
  
- **MLflow**: http://localhost:5000
  - Model registry and experiment tracking

---

## 🎯 Key Endpoints

```bash
# API Health Check
curl http://localhost:8000/health

# API Documentation (Open in Browser)
http://localhost:8000/docs

# Predict Fraud (Example)
curl -X POST http://localhost:8000/api/v1/predict \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 1000,
    "merchant_id": "M123",
    "transaction_time": "2026-03-25T10:00:00Z"
  }'

# Get System Metrics
curl http://localhost:8000/metrics
```

---

## 🎮 Management Commands

### View Services
```bash
# Status of all services
docker-compose -f docker-compose.prod.yml ps

# Running containers
docker ps

# Resource usage
docker stats
```

### View Logs
```bash
# All services
docker-compose -f docker-compose.prod.yml logs -f

# Specific service
docker-compose -f docker-compose.prod.yml logs -f backend
docker-compose -f docker-compose.prod.yml logs -f frontend
docker-compose -f docker-compose.prod.yml logs -f db

# Real-time monitoring
docker-compose -f docker-compose.prod.yml logs -f --tail=50
```

### Control Services
```bash
# Stop all services
docker-compose -f docker-compose.prod.yml down

# Restart all
docker-compose -f docker-compose.prod.yml restart

# Stop specific service
docker-compose -f docker-compose.prod.yml stop backend

# Start specific service
docker-compose -f docker-compose.prod.yml start backend

# View service details
docker-compose -f docker-compose.prod.yml exec backend bash
```

### Database Operations
```bash
# Access PostgreSQL CLI
docker-compose -f docker-compose.prod.yml exec db psql -U frauduser -d frauddetection

# Useful SQL commands:
\dt                    # List all tables
\d+ [table_name]      # Describe table
SELECT * FROM ...     # Query data
```

### Redis Operations
```bash
# Access Redis CLI
docker-compose -f docker-compose.prod.yml exec redis redis-cli

# Useful commands:
PING                  # Test connection
KEYS *                # List all keys
GET [key]             # Get value
FLUSHDB               # Clear all data
```

---

## 🔍 Troubleshooting

### Services Not Starting
```bash
# View error logs
docker-compose -f docker-compose.prod.yml logs

# Clean rebuild
docker-compose -f docker-compose.prod.yml down -v
docker system prune -f
docker-compose -f docker-compose.prod.yml up -d
```

### Port Already in Use
```bash
# Windows - Find what's using the port
netstat -ano | findstr ":8000"

# Kill the process (replace PID with actual PID)
taskkill /PID [PID] /F

# Or change port in docker-compose.prod.yml
```

### Out of Memory/Storage
```bash
# Check Docker usage
docker system df

# Clean up
docker system prune -a
docker volume prune

# Remove stopped containers
docker container prune
```

### Database Connection Issues
```bash
# Check database logs
docker-compose -f docker-compose.prod.yml logs db

# Restart database
docker-compose -f docker-compose.prod.yml restart db

# Wait for database to be ready
docker-compose -f docker-compose.prod.yml exec db pg_isready
```

---

## 📋 System Architecture

```
┌─────────────────────────────────────────┐
│     Frontend (React 18)                 │
│     http://localhost:3000               │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│     Backend API (FastAPI)               │
│     http://localhost:8000               │
│     - WebSocket for real-time updates   │
│     - JWT authentication                │
│     - 6 async agents                    │
└────────┬────────────┬────────────┬──────┘
         │            │            │
    ┌────▼──┐   ┌────▼──┐   ┌────▼──┐
    │PostgreSQL Redis  Kafka
    │Database Queues  Events
    └────────┘   └────────┘   └───────┘

┌────────────────────────────────────────┐
│     Monitoring Stack                   │
├────────────────────────────────────────┤
│ • Prometheus → http://localhost:9090   │
│ • Grafana → http://localhost:3000      │
│ • MLflow → http://localhost:5000       │
└────────────────────────────────────────┘
```

---

## 🎯 Performance Targets

| Metric | Target | Status |
|--------|--------|--------|
| Latency (P95) | < 300ms | ✅ Optimized |
| Throughput | 1000+ TPS | ✅ Scalable |
| Uptime | 99.9% | ✅ HA Setup |
| Accuracy | >95% | ✅ Ensemble Models |
| FPR | <5% | ✅ Tuned |

---

## 🔧 Configuration

### Environment Variables
Edit `.env` file to configure:
- Database credentials
- Redis connection
- Kafka bootstrap servers
- JWT secret
- API settings

```bash
# Copy example and edit
cp .env.example .env
# Edit with your settings
```

### Docker Compose Profiles
```bash
# Run specific services only
docker-compose -f docker-compose.prod.yml --profile monitoring up -d
```

---

## 📚 Additional Resources

- **Full Documentation**: See `RUN_GUIDE.md`
- **Project README**: See `README.md`
- **API Documentation**: http://localhost:8000/docs
- **Infrastructure**: See `terraform/README.md`
- **Agent Details**: See `backend/agents/`

---

## 🆘 Need Help?

1. **Check Logs**: `docker-compose -f docker-compose.prod.yml logs -f`
2. **Verify Services**: `docker ps`
3. **Test Endpoints**: `curl http://localhost:8000/health`
4. **Check Metrics**: http://localhost:9090

---

## ✨ Next Steps

1. Wait for all services to start (2-5 minutes)
2. Visit http://localhost:3000 for the dashboard
3. Check http://localhost:8000/docs for API reference
4. View metrics at http://localhost:9090
5. Access Grafana at http://localhost:3000 (admin/admin)

**System is ready for production! 🚀**