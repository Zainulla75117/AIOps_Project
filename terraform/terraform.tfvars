# ============================================================
# Default variable values for dev environment
# ============================================================

aws_region          = "ap-south-1"
environment         = "dev"
project_name        = "aiops-project"
vpc_cidr            = "10.0.0.0/16"
eks_cluster_version = "1.36"

eks_node_instance_types = ["c7i-flex.large"]
eks_node_desired_size   = 2
eks_node_min_size       = 1
eks_node_max_size       = 5
