variable "name" {
  type = string
}

variable "aws_region" {
  type = string
}

variable "eks_cluster_name" {
  type = string
}

variable "eks_node_group_name" {
  type = string
}

variable "rds_instance_id" {
  type = string
}

variable "redis_cluster_id" {
  type = string
}

variable "sqs_queue_name" {
  type = string
}

variable "sqs_dlq_name" {
  type = string
}

variable "s3_raw_bucket" {
  type = string
}

variable "s3_recipes_bucket" {
  type = string
}

variable "cloudfront_distribution_id" {
  type = string
}

variable "cognito_user_pool_id" {
  type = string
}

variable "cognito_client_id" {
  type = string
}

variable "nat_gateway_id" {
  type = string
}

variable "cutoff_lambda_name" {
  type = string
}

variable "cost_guardrails_dashboard_name" {
  type        = string
  description = "Link to the dedicated cost-guardrails dashboard"
}

locals {
  dashboard_name = "${var.name}-platform"
}

resource "aws_cloudwatch_dashboard" "platform" {
  dashboard_name = local.dashboard_name

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "text"
        x      = 0
        y      = 0
        width  = 24
        height = 2
        properties = {
          markdown = <<-EOT
            # ${var.name} platform overview
            EKS · RDS · Redis · SQS · S3 · CloudFront · Cognito · NAT · cost cutoff
            Cost detail: CloudWatch → Dashboards → `${var.cost_guardrails_dashboard_name}`
          EOT
        }
      },

      # --- Compute / data plane ---
      {
        type   = "metric"
        x      = 0
        y      = 2
        width  = 8
        height = 6
        properties = {
          title   = "EKS ${var.eks_cluster_name} / ${var.eks_node_group_name}"
          region  = var.aws_region
          view    = "timeSeries"
          stacked = false
          metrics = [
            ["AWS/EKS", "cluster_failed_node_count", "ClusterName", var.eks_cluster_name, { label = "Failed nodes", stat = "Maximum" }],
            [".", "cluster_node_count", ".", ".", { label = "Nodes", stat = "Average" }],
          ]
          period = 60
          yAxis = {
            left = { min = 0 }
          }
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 2
        width  = 8
        height = 6
        properties = {
          title  = "RDS ${var.rds_instance_id}"
          region = var.aws_region
          metrics = [
            ["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", var.rds_instance_id, { label = "CPU %", stat = "Average" }],
            [".", "DatabaseConnections", ".", ".", { label = "Connections", stat = "Average", yAxis = "right" }],
            [".", "FreeStorageSpace", ".", ".", { label = "Free storage", stat = "Average", yAxis = "right" }],
          ]
          period = 60
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 2
        width  = 8
        height = 6
        properties = {
          title  = "Redis ${var.redis_cluster_id}"
          region = var.aws_region
          metrics = [
            ["AWS/ElastiCache", "CPUUtilization", "CacheClusterId", var.redis_cluster_id, { label = "CPU %", stat = "Average" }],
            [".", "CurrConnections", ".", ".", { label = "Connections", stat = "Average", yAxis = "right" }],
            [".", "Evictions", ".", ".", { label = "Evictions", stat = "Sum", yAxis = "right" }],
          ]
          period = 60
        }
      },

      # --- Moderation queue ---
      {
        type   = "metric"
        x      = 0
        y      = 8
        width  = 12
        height = 6
        properties = {
          title  = "SQS ${var.sqs_queue_name}"
          region = var.aws_region
          metrics = [
            ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", var.sqs_queue_name, { label = "Visible", stat = "Average" }],
            [".", "NumberOfMessagesSent", ".", ".", { label = "Sent", stat = "Sum" }],
            [".", "NumberOfMessagesReceived", ".", ".", { label = "Received", stat = "Sum" }],
            [".", "ApproximateAgeOfOldestMessage", ".", ".", { label = "Oldest age (s)", stat = "Maximum", yAxis = "right" }],
          ]
          period = 60
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 8
        width  = 12
        height = 6
        properties = {
          title  = "SQS DLQ ${var.sqs_dlq_name}"
          region = var.aws_region
          metrics = [
            ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", var.sqs_dlq_name, { label = "Visible", stat = "Average" }],
            [".", "NumberOfMessagesSent", ".", ".", { label = "Sent", stat = "Sum" }],
          ]
          period = 60
        }
      },

      # --- Storage / CDN ---
      {
        type   = "metric"
        x      = 0
        y      = 14
        width  = 8
        height = 6
        properties = {
          title  = "S3 ${var.s3_raw_bucket}"
          region = var.aws_region
          metrics = [
            ["AWS/S3", "BucketSizeBytes", "BucketName", var.s3_raw_bucket, "StorageType", "StandardStorage", { label = "Size", stat = "Average" }],
            [".", "NumberOfObjects", ".", ".", ".", "AllStorageTypes", { label = "Objects", stat = "Average", yAxis = "right" }],
          ]
          period = 86400
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 14
        width  = 8
        height = 6
        properties = {
          title  = "S3 ${var.s3_recipes_bucket}"
          region = var.aws_region
          metrics = [
            ["AWS/S3", "BucketSizeBytes", "BucketName", var.s3_recipes_bucket, "StorageType", "StandardStorage", { label = "Size", stat = "Average" }],
            [".", "NumberOfObjects", ".", ".", ".", "AllStorageTypes", { label = "Objects", stat = "Average", yAxis = "right" }],
          ]
          period = 86400
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 14
        width  = 8
        height = 6
        properties = {
          title  = "CloudFront ${var.cloudfront_distribution_id}"
          region = "us-east-1"
          metrics = [
            ["AWS/CloudFront", "Requests", "Region", "Global", "DistributionId", var.cloudfront_distribution_id, { label = "Requests", stat = "Sum" }],
            [".", "BytesDownloaded", ".", ".", ".", ".", { label = "Bytes down", stat = "Sum", yAxis = "right" }],
            [".", "4xxErrorRate", ".", ".", ".", ".", { label = "4xx %", stat = "Average" }],
            [".", "5xxErrorRate", ".", ".", ".", ".", { label = "5xx %", stat = "Average" }],
          ]
          period = 60
        }
      },

      # --- Auth / network / cost ---
      {
        type   = "metric"
        x      = 0
        y      = 20
        width  = 8
        height = 6
        properties = {
          title  = "Cognito ${var.cognito_user_pool_id}"
          region = var.aws_region
          metrics = [
            ["AWS/Cognito", "SignInSuccesses", "UserPool", var.cognito_user_pool_id, "UserPoolClient", var.cognito_client_id, { label = "Sign-in OK", stat = "Sum" }],
            [".", "SignInThrottles", ".", ".", ".", ".", { label = "Sign-in throttle", stat = "Sum" }],
            [".", "TokenRefreshSuccesses", ".", ".", ".", ".", { label = "Token refresh", stat = "Sum" }],
            [".", "SignUpSuccesses", ".", ".", ".", ".", { label = "Sign-up OK", stat = "Sum" }],
          ]
          period = 60
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 20
        width  = 8
        height = 6
        properties = {
          title  = "NAT ${var.nat_gateway_id}"
          region = var.aws_region
          metrics = [
            ["AWS/NATGateway", "BytesOutToDestination", "NatGatewayId", var.nat_gateway_id, { label = "Out to dest", stat = "Sum" }],
            [".", "BytesInFromSource", ".", ".", { label = "In from source", stat = "Sum" }],
            [".", "ErrorPortAllocation", ".", ".", { label = "Port alloc errors", stat = "Sum", yAxis = "right" }],
          ]
          period = 60
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 20
        width  = 8
        height = 6
        properties = {
          title  = "Cost cutoff ${var.cutoff_lambda_name}"
          region = var.aws_region
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", var.cutoff_lambda_name, { label = "Invocations", stat = "Sum" }],
            [".", "Errors", ".", ".", { label = "Errors", stat = "Sum" }],
            [".", "Duration", ".", ".", { label = "Duration", stat = "Average", yAxis = "right" }],
          ]
          period = 60
        }
      },

      {
        type   = "text"
        x      = 0
        y      = 26
        width  = 24
        height = 3
        properties = {
          markdown = <<-EOT
            ### Notes
            - **EKS node/pod detail** needs Container Insights (not enabled by default); this board uses `AWS/EKS` cluster node counts when available.
            - **S3 size/object** metrics update about once per day.
            - **CloudFront** metrics are global (`us-east-1` namespace).
            - For budget phases and shutoff logs, open **`${var.cost_guardrails_dashboard_name}`**.
          EOT
        }
      }
    ]
  })
}

output "platform_dashboard_name" {
  value = aws_cloudwatch_dashboard.platform.dashboard_name
}

output "platform_dashboard_url" {
  value = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.platform.dashboard_name}"
}
