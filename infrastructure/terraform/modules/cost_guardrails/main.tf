variable "name" {
  type = string
}

variable "budget_limit_usd" {
  type        = number
  default     = 100
  description = "Monthly AWS spend budget in USD"
}

variable "alert_emails" {
  type        = list(string)
  default     = []
  description = "Emails subscribed to budget SNS alerts (must confirm subscription)"
}

variable "eks_cluster_name" {
  type = string
}

variable "rds_instance_id" {
  type = string
}

variable "redis_cluster_id" {
  type = string
}

variable "aws_region" {
  type = string
}

# Phase thresholds (% of budget_limit_usd)
variable "alert_threshold" {
  type        = number
  default     = 50
  description = "Phase 1/2: email alert only"
}

variable "scale_threshold" {
  type        = number
  default     = 70
  description = "Phase 2: scale EKS down to minimal nodes"
}

variable "shutoff_threshold" {
  type        = number
  default     = 80
  description = "Phase 1/2: full compute shutoff"
}

data "aws_caller_identity" "current" {}

resource "aws_sns_topic" "budget" {
  name = "${var.name}-budget-alerts"
}

resource "aws_sns_topic_subscription" "email" {
  for_each  = toset(var.alert_emails)
  topic_arn = aws_sns_topic.budget.arn
  protocol  = "email"
  endpoint  = each.value
}

data "archive_file" "cutoff" {
  type        = "zip"
  source_file = "${path.module}/lambda/cutoff.py"
  output_path = "${path.module}/lambda/cutoff.zip"
}

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "cutoff" {
  name               = "${var.name}-cost-cutoff"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

data "aws_iam_policy_document" "cutoff" {
  statement {
    sid = "Logs"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["arn:aws:logs:*:*:*"]
  }

  statement {
    sid = "EksScale"
    actions = [
      "eks:ListNodegroups",
      "eks:DescribeNodegroup",
      "eks:UpdateNodegroupConfig",
      "eks:DescribeCluster",
    ]
    resources = ["*"]
  }

  statement {
    sid = "RdsStop"
    actions = [
      "rds:DescribeDBInstances",
      "rds:StopDBInstance",
      "rds:AddTagsToResource",
      "rds:ListTagsForResource",
    ]
    resources = ["*"]
  }

  statement {
    sid = "RedisDelete"
    actions = [
      "elasticache:DeleteCacheCluster",
      "elasticache:DescribeCacheClusters",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "cutoff" {
  name   = "${var.name}-cost-cutoff"
  role   = aws_iam_role.cutoff.id
  policy = data.aws_iam_policy_document.cutoff.json
}

resource "aws_lambda_function" "cutoff" {
  function_name    = "${var.name}-cost-cutoff"
  role             = aws_iam_role.cutoff.arn
  handler          = "cutoff.handler"
  runtime          = "python3.12"
  filename         = data.archive_file.cutoff.output_path
  source_code_hash = data.archive_file.cutoff.output_base64sha256
  timeout          = 120

  environment {
    variables = {
      EKS_CLUSTER_NAME   = var.eks_cluster_name
      RDS_INSTANCE_ID    = var.rds_instance_id
      REDIS_CLUSTER_ID   = var.redis_cluster_id
      AWS_REGION         = var.aws_region
      ALERT_THRESHOLD    = tostring(var.alert_threshold)
      SCALE_THRESHOLD    = tostring(var.scale_threshold)
      SHUTOFF_THRESHOLD  = tostring(var.shutoff_threshold)
    }
  }
}

resource "aws_sns_topic_subscription" "lambda" {
  topic_arn = aws_sns_topic.budget.arn
  protocol  = "lambda"
  endpoint  = aws_lambda_function.cutoff.arn
}

resource "aws_lambda_permission" "sns" {
  statement_id  = "AllowSNSInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.cutoff.function_name
  principal     = "sns.amazonaws.com"
  source_arn    = aws_sns_topic.budget.arn
}

resource "aws_budgets_budget" "monthly" {
  name              = "${var.name}-monthly"
  budget_type       = "COST"
  limit_amount      = tostring(var.budget_limit_usd)
  limit_unit        = "USD"
  time_unit         = "MONTHLY"
  time_period_start = "2026-01-01_00:00"

  cost_types {
    include_credit             = false
    include_discount           = true
    include_other_subscription = true
    include_recurring          = true
    include_refund             = false
    include_subscription       = true
    include_support            = true
    include_tax                = true
    include_upfront            = true
    use_amortized              = false
    use_blended                = false
  }

  # Phase 1/2 — 50% alert
  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = var.alert_threshold
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_sns_topic_arns = [aws_sns_topic.budget.arn]
  }

  # Phase 2 — 70% scale-down
  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = var.scale_threshold
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_sns_topic_arns = [aws_sns_topic.budget.arn]
  }

  # Phase 1/2 — 80% shutoff (actual)
  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = var.shutoff_threshold
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_sns_topic_arns = [aws_sns_topic.budget.arn]
  }

  # Phase 1/2 — 80% shutoff (forecasted early warning → same shutoff path)
  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = var.shutoff_threshold
    threshold_type            = "PERCENTAGE"
    notification_type         = "FORECASTED"
    subscriber_sns_topic_arns = [aws_sns_topic.budget.arn]
  }
}

resource "aws_iam_policy" "deny_spend" {
  name = "${var.name}-deny-further-spend"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DenyExpensiveCreates"
        Effect = "Deny"
        Action = [
          "ec2:RunInstances",
          "ec2:StartInstances",
          "eks:CreateNodegroup",
          "eks:UpdateNodegroupConfig",
          "rds:CreateDBInstance",
          "rds:StartDBInstance",
          "elasticache:CreateCacheCluster",
          "sagemaker:*",
          "bedrock:*",
        ]
        Resource = "*"
        Condition = {
          StringNotEquals = {
            "aws:PrincipalArn" = aws_iam_role.cutoff.arn
          }
        }
      }
    ]
  })
}

output "budget_name" { value = aws_budgets_budget.monthly.name }
output "sns_topic_arn" { value = aws_sns_topic.budget.arn }
output "cutoff_lambda_arn" { value = aws_lambda_function.cutoff.arn }
output "deny_spend_policy_arn" { value = aws_iam_policy.deny_spend.arn }
output "budget_limit_usd" { value = var.budget_limit_usd }
output "alert_threshold" { value = var.alert_threshold }
output "scale_threshold" { value = var.scale_threshold }
output "shutoff_threshold" { value = var.shutoff_threshold }
