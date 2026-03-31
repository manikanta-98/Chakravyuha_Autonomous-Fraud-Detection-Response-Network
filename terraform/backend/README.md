# Terraform Backend Setup

This directory contains the Terraform configuration to set up the remote backend for the Fraud Detection System infrastructure.

## Setup

1. **Initialize and apply the backend:**
   ```bash
   cd terraform/backend
   terraform init
   terraform apply
   ```

2. **Return to main directory:**
   ```bash
   cd ..
   terraform init
   ```

This will create:
- S3 bucket for Terraform state storage
- DynamoDB table for state locking

## Security

- S3 bucket has public access blocked
- Server-side encryption enabled
- Versioning enabled for state history