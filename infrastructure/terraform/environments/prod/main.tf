terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }

  # Configure remote state for your account:
  # backend "s3" {
  #   bucket = "plate-terraform-state"
  #   key    = "prod/terraform.tfstate"
  #   region = "us-east-1"
  # }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = "plate"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "environment" {
  type    = string
  default = "prod"
}

variable "name" {
  type    = string
  default = "plate"
}

variable "budget_limit_usd" {
  type        = number
  default     = 100
  description = "Monthly AWS spend ($USD) that triggers emergency compute cutoff"
}

variable "budget_alert_emails" {
  type        = list(string)
  default     = []
  description = "Emails for budget warning + cutoff notifications"
}

variable "alert_threshold" {
  type    = number
  default = 50
}

variable "scale_threshold" {
  type    = number
  default = 70
}

variable "shutoff_threshold" {
  type    = number
  default = 80
}

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  azs = slice(data.aws_availability_zones.available.names, 0, 2)
}

module "network" {
  source = "../../modules/network"
  name   = var.name
  azs    = local.azs
}

module "eks" {
  source     = "../../modules/eks"
  name       = var.name
  subnet_ids = concat(module.network.private_subnet_ids, module.network.public_subnet_ids)
}

module "rds" {
  source             = "../../modules/rds"
  name               = var.name
  subnet_ids         = module.network.private_subnet_ids
  security_group_ids = [module.network.rds_sg_id]
}

module "s3" {
  source = "../../modules/s3"
  name   = var.name
}

module "cdn" {
  source                = "../../modules/cdn"
  name                  = var.name
  recipes_bucket_id     = module.s3.recipes_bucket
  recipes_bucket_domain = module.s3.recipes_bucket_regional_domain
}

module "sqs" {
  source = "../../modules/sqs"
  name   = var.name
}

module "cognito" {
  source = "../../modules/cognito"
  name   = var.name
}

module "ecr" {
  source = "../../modules/ecr"
  name   = var.name
}

module "iam" {
  source             = "../../modules/iam"
  name               = var.name
  oidc_issuer        = module.eks.oidc_issuer
  raw_bucket_arn     = module.s3.raw_bucket_arn
  recipes_bucket_arn = module.s3.recipes_bucket_arn
  sqs_queue_arn      = module.sqs.queue_arn
  db_secret_arn      = module.rds.secret_arn
}

module "elasticache" {
  source             = "../../modules/elasticache"
  name               = var.name
  subnet_ids         = module.network.private_subnet_ids
  security_group_ids = [module.network.redis_sg_id]
}

module "cost_guardrails" {
  source            = "../../modules/cost_guardrails"
  name              = var.name
  budget_limit_usd  = var.budget_limit_usd
  alert_emails      = var.budget_alert_emails
  eks_cluster_name  = module.eks.cluster_name
  rds_instance_id   = module.rds.instance_id
  redis_cluster_id  = module.elasticache.cluster_id
  aws_region        = var.aws_region
  alert_threshold   = var.alert_threshold
  scale_threshold   = var.scale_threshold
  shutoff_threshold = var.shutoff_threshold
}

output "cluster_name" { value = module.eks.cluster_name }
output "rds_endpoint" { value = module.rds.endpoint }
output "cognito_user_pool_id" { value = module.cognito.user_pool_id }
output "cognito_client_id" { value = module.cognito.client_id }
output "cognito_issuer" { value = module.cognito.issuer }
output "sqs_moderation_url" { value = module.sqs.queue_url }
output "s3_raw_bucket" { value = module.s3.raw_bucket }
output "s3_recipes_bucket" { value = module.s3.recipes_bucket }
output "cloudfront_domain" { value = module.cdn.domain_name }
output "ecr_urls" { value = module.ecr.repository_urls }
output "api_irsa_role_arn" { value = module.iam.api_role_arn }
output "worker_irsa_role_arn" { value = module.iam.worker_role_arn }
output "redis_endpoint" { value = module.elasticache.endpoint }
output "budget_limit_usd" { value = module.cost_guardrails.budget_limit_usd }
output "budget_sns_topic_arn" { value = module.cost_guardrails.sns_topic_arn }
output "cost_cutoff_lambda_arn" { value = module.cost_guardrails.cutoff_lambda_arn }
output "deny_spend_policy_arn" { value = module.cost_guardrails.deny_spend_policy_arn }
output "database_url" {
  value     = module.rds.database_url
  sensitive = true
}
