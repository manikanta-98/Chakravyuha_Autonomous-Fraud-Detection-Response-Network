output "cluster_endpoint" {
  description = "Endpoint for EKS control plane"
  value       = module.eks.cluster_endpoint
}

output "cluster_security_group_id" {
  description = "Security group ID attached to the EKS cluster"
  value       = module.eks.cluster_security_group_id
}

output "cluster_name" {
  description = "Kubernetes Cluster Name"
  value       = local.cluster_name
}

output "region" {
  description = "AWS region"
  value       = var.aws_region
}

output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "private_subnets" {
  description = "Private subnet IDs"
  value       = module.vpc.private_subnets
}

output "public_subnets" {
  description = "Public subnet IDs"
  value       = module.vpc.public_subnets
}

output "db_endpoint" {
  description = "PostgreSQL database endpoint"
  value       = module.db.db_instance_endpoint
}

output "db_port" {
  description = "PostgreSQL database port"
  value       = module.db.db_instance_port
}

output "redis_endpoint" {
  description = "Redis cluster endpoint"
  value       = module.redis.cluster_address
}

output "redis_port" {
  description = "Redis cluster port"
  value       = module.redis.cluster_port
}

output "kafka_bootstrap_brokers" {
  description = "MSK Kafka bootstrap brokers"
  value       = module.kafka.bootstrap_brokers_tls
}

output "kafka_bootstrap_brokers_sasl_scram" {
  description = "MSK Kafka bootstrap brokers with SASL/SCRAM"
  value       = module.kafka.bootstrap_brokers_sasl_scram
}

output "mlflow_bucket" {
  description = "S3 bucket for MLflow artifacts"
  value       = module.s3_bucket_mlflow.s3_bucket_id
}

output "mlflow_bucket_arn" {
  description = "S3 bucket ARN for MLflow artifacts"
  value       = module.s3_bucket_mlflow.s3_bucket_arn
}

output "cluster_autoscaler_role_arn" {
  description = "IAM role ARN for cluster autoscaler"
  value       = aws_iam_role.cluster_autoscaler.arn
}

output "kubeconfig_command" {
  description = "Command to update kubeconfig"
  value       = "aws eks update-kubeconfig --region ${var.aws_region} --name ${local.cluster_name}"
}

output "grafana_endpoint" {
  description = "Grafana service endpoint"
  value       = "kubectl get svc grafana -n fraud-detection -o jsonpath='{.spec.clusterIP}:{.spec.ports[0].port}'"
}

output "prometheus_endpoint" {
  description = "Prometheus service endpoint"
  value       = "kubectl get svc prometheus -n monitoring -o jsonpath='{.spec.clusterIP}:{.spec.ports[0].port}'"
}