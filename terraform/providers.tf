# ============================================================
# Terraform Root — AIOps Project Infrastructure
# ============================================================
# Provisions: VPC, EKS, ECR on AWS (ap-south-1)
# ============================================================

terraform {
  required_version = ">= 1.15.8"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket         = "aiops-project-tf-state"
    key            = "infrastructure/terraform.tfstate"
    region         = "ap-south-1"
    dynamodb_table = "aiops-project-tf-locks"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "aiops-project"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
