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
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.13"
    }
    http = {
      source  = "hashicorp/http"
      version = "~> 3.4"
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

data "aws_eks_cluster" "main" {
  name = "${var.project_name}-${var.environment}-cluster"
}

data "aws_eks_cluster_auth" "main" {
  name = "${var.project_name}-${var.environment}-cluster"
}

provider "helm" {
  kubernetes {
    host                   = data.aws_eks_cluster.main.endpoint
    cluster_ca_certificate = base64decode(data.aws_eks_cluster.main.certificate_authority[0].data)
    token                  = data.aws_eks_cluster_auth.main.token
  }
}
