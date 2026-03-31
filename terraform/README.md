# Fraud Detection System - Infrastructure as Code

This Terraform configuration creates a complete AWS infrastructure for the Fraud Detection System, including:

- EKS Kubernetes cluster with autoscaling
- RDS PostgreSQL database
- ElastiCache Redis cluster
- MSK Kafka cluster
- S3 bucket for MLflow artifacts
- VPC with public/private subnets
- Security groups and IAM roles
- CloudWatch monitoring

## Prerequisites

- AWS CLI configured with appropriate permissions
- Terraform >= 1.0
- kubectl installed

## Quick Start

1. **Initialize Terraform:**
   ```bash
   terraform init
   ```

2. **Plan the deployment:**
   ```bash
   terraform plan
   ```

3. **Apply the configuration:**
   ```bash
   terraform apply
   ```

4. **Configure kubectl:**
   ```bash
   aws eks update-kubeconfig --region us-east-1 --name fraud-detection-eks
   ```

5. **Deploy the application:**
   ```bash
   kubectl apply -f ../k8s/
   kubectl apply -f ../monitoring/
   ```

## Architecture

The infrastructure consists of:

- **EKS Cluster**: Managed Kubernetes control plane with worker nodes
- **RDS PostgreSQL**: Primary database for application data
- **ElastiCache Redis**: In-memory data store for caching and queues
- **MSK Kafka**: Event streaming platform for real-time data processing
- **S3**: Object storage for MLflow model artifacts and logs

## Configuration

### Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `aws_region` | AWS region for deployment | `us-east-1` |
| `environment` | Environment name | `production` |
| `eks_cluster_version` | Kubernetes version | `1.28` |
| `node_instance_types` | EC2 instance types for worker nodes | `["t3.large"]` |
| `node_min_size` | Minimum worker nodes | `3` |
| `node_max_size` | Maximum worker nodes | `10` |
| `db_instance_class` | RDS instance class | `db.r6g.large` |

### Outputs

After deployment, the following outputs are available:

- `cluster_endpoint`: EKS API server endpoint
- `db_endpoint`: PostgreSQL connection string
- `redis_endpoint`: Redis cluster endpoint
- `kafka_bootstrap_brokers`: Kafka broker endpoints
- `mlflow_bucket`: S3 bucket for ML artifacts

## Security

- All resources are deployed in private subnets
- Security groups restrict access to necessary ports only
- IAM roles follow least-privilege principle
- Database and Redis encryption enabled
- Kafka with TLS encryption

## Monitoring

The infrastructure includes:

- CloudWatch logs for all services
- EKS cluster metrics
- RDS performance insights
- ElastiCache metrics
- MSK monitoring

## Cost Optimization

- EKS cluster autoscaling based on CPU/memory usage
- RDS with auto-scaling storage
- Reserved instances recommended for production
- Spot instances can be configured for non-critical workloads

## Troubleshooting

### Common Issues

1. **EKS cluster creation fails:**
   - Check AWS service limits
   - Verify IAM permissions
   - Ensure VPC/subnet configuration

2. **Worker nodes not joining cluster:**
   - Check security group rules
   - Verify IAM roles and policies
   - Check CloudWatch logs for node errors

3. **Database connection issues:**
   - Verify security group allows traffic from EKS nodes
   - Check VPC routing and NACLs
   - Ensure correct connection string format

### Logs and Monitoring

- EKS control plane logs: CloudWatch `/aws/eks/fraud-detection-eks/cluster`
- Application logs: CloudWatch `/aws/eks/fraud-detection-eks/application`
- Infrastructure metrics: CloudWatch dashboards

## Cleanup

To destroy all resources:

```bash
terraform destroy
```

**Warning:** This will permanently delete all data and resources. Ensure backups are taken if needed.