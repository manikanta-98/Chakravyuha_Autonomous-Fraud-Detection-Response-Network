# Autonomous Fraud Detection & Response Network (Chakravyuha Pipeline)

A production-grade multi-agent AI system for real-time fraud detection with <300ms latency, 1000+ TPS, and 99.9% uptime guarantees.

## 🚀 Features

- **Multi-Agent Architecture**: 6 async agents (monitoring, pattern detection, risk assessment, alert blocking, compliance, learning)
- **Ensemble ML Models**: TabPFN + XGBoost + PyTorch Geometric GNN + Meta-learner
- **Real-time Processing**: Async processing with Redis streams and Kafka
- **Explainable AI**: SHAP and LIME explanations for model decisions
- **Production Infrastructure**: Kubernetes, Prometheus, Grafana, Terraform
- **DevOps Pipeline**: GitHub Actions CI/CD with security scanning

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Transaction   │───▶│   API Gateway   │───▶│   Agent Hub     │
│   Stream        │    │  (FastAPI)      │    │  (Asyncio)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │                        │
                              ▼                        ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Ensemble      │    │   Feature       │    │   Alert &       │
│   Models        │    │   Store         │    │   Response      │
│                 │    │   (Feast)       │    │   Engine        │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 📊 Performance Targets

- **Latency**: <300ms (95th percentile)
- **Throughput**: 1000+ TPS
- **Uptime**: 99.9%
- **Accuracy**: >95% fraud detection
- **False Positive Rate**: <5%

## 🛠️ Tech Stack

### Backend
- **Python 3.12** with FastAPI
- **Redis** for caching and queues
- **Kafka** for event streaming
- **PostgreSQL** for persistence
- **MLflow** for model management

### ML/AI
- **TabPFN** for tabular prediction
- **XGBoost** for gradient boosting
- **PyTorch Geometric** for graph neural networks
- **SHAP/LIME** for explainability
- **LangChain** for LLM reasoning

### Infrastructure
- **Kubernetes** with HPA autoscaling
- **Terraform** for AWS EKS
- **Prometheus/Grafana** for monitoring
- **Docker** multi-stage builds

### Frontend
- **React 18** with hooks
- **WebSocket** for real-time updates
- **Dark theme** UI

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- kubectl
- Terraform
- AWS CLI configured

### 1. Local Development
```bash
# Start all services
docker-compose up -d

# Run the application
cd backend
python main.py
```

### 2. Production Deployment

#### Setup Infrastructure
```bash
# Initialize Terraform backend
cd terraform/backend
terraform init && terraform apply

# Deploy AWS infrastructure
cd ..
terraform init && terraform apply

# Configure kubectl
aws eks update-kubeconfig --region us-east-1 --name fraud-detection-eks
```

#### Deploy Application
```bash
# Deploy to Kubernetes
kubectl apply -f k8s/

# Deploy monitoring
kubectl apply -f monitoring/
```

## 📁 Project Structure

```
fraud-detection-system/
├── backend/                 # FastAPI application
│   ├── core/               # Core ML models and utilities
│   ├── agents/             # Agent implementations
│   ├── main.py             # FastAPI server
│   └── requirements.txt    # Python dependencies
├── frontend/               # React application
│   ├── src/
│   ├── Dockerfile
│   └── package.json
├── k8s/                   # Kubernetes manifests
├── monitoring/            # Prometheus & Grafana configs
├── terraform/             # Infrastructure as Code
├── docker-compose.yml     # Local development
└── .github/workflows/     # CI/CD pipelines
```

## 🔧 Configuration

### Environment Variables
```bash
# Database
DATABASE_URL=postgresql://user:pass@host:5432/db

# Redis
REDIS_URL=redis://host:6379

# Kafka
KAFKA_BOOTSTRAP_SERVERS=host:9092

# MLflow
MLFLOW_TRACKING_URI=http://mlflow:5000

# JWT
JWT_SECRET_KEY=your-secret-key
```

### Model Training
```bash
# Train ensemble model
cd backend
python -m core.ensemble_model

# Start MLflow UI
mlflow ui --backend-store-uri postgresql://user:pass@host:5432/mlflow
```

## 📈 Monitoring

### Dashboards
- **System Health**: Service status and resource usage
- **API Performance**: Latency, throughput, error rates
- **Agent Performance**: Queue lengths, processing rates
- **Model Metrics**: Accuracy, false positive rates

### Alerts
- High latency (>300ms)
- Error rate spikes
- Agent queue backlogs
- Model accuracy drops
- Resource exhaustion

## 🔒 Security

- **Authentication**: JWT-based auth with role-based access
- **Authorization**: Fine-grained permissions
- **Encryption**: TLS everywhere, encrypted storage
- **Secrets Management**: HashiCorp Vault integration
- **Security Scanning**: Automated vulnerability scans in CI/CD

## 🧪 Testing

```bash
# Run unit tests
pytest backend/tests/

# Run integration tests
docker-compose -f docker-compose.test.yml up

# Load testing
locust -f tests/load_test.py
```

## 📚 API Documentation

Once running, visit:
-**Dashboard**:http://http://localhost:3002
- **API Docs**: http://localhost:8000/docs
- **Grafana**: http://localhost:3000
- **MLflow**: http://localhost:5000


## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:
- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions
- **Documentation**: Wiki

## 🎯 Roadmap

- [ ] GPU acceleration for GNN models
- [ ] Federated learning across regions
- [ ] Advanced adversarial attack detection
- [ ] Real-time model updates
- [ ] Multi-cloud deployment support
