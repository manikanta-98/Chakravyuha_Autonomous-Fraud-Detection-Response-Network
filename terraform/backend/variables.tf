variable "aws_region" {
  description = "AWS region for backend resources"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "fraud-detection"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
}