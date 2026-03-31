terraform {
  backend "s3" {
    bucket = "fraud-detection-terraform-state"
    key    = "fraud-detection-eks.tfstate"
    region = "us-east-1"
    encrypt = true
    dynamodb_table = "fraud-detection-terraform-locks"
  }
}