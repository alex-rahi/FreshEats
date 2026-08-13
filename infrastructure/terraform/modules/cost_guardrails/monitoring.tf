# Shutoff / scale monitoring: log metrics, alarms, dashboard, RDS stop events.

resource "aws_cloudwatch_log_group" "cutoff" {
  name              = "/aws/lambda/${var.name}-cost-cutoff"
  retention_in_days = 30
}

locals {
  guardrail_namespace = "FreshEats/CostGuardrails"
  cutoff_log_group    = aws_cloudwatch_log_group.cutoff.name
}

resource "aws_cloudwatch_log_metric_filter" "soft_scale" {
  name           = "${var.name}-soft-scale"
  log_group_name = local.cutoff_log_group
  pattern        = "COST_GUARDRAIL_EVENT phase=soft_scale"

  metric_transformation {
    name      = "SoftScaleEvents"
    namespace = local.guardrail_namespace
    value     = "1"
  }
}

resource "aws_cloudwatch_log_metric_filter" "lock" {
  name           = "${var.name}-lock"
  log_group_name = local.cutoff_log_group
  pattern        = "COST_GUARDRAIL_EVENT phase=lock"

  metric_transformation {
    name      = "LockEvents"
    namespace = local.guardrail_namespace
    value     = "1"
  }
}

resource "aws_cloudwatch_log_metric_filter" "shutoff" {
  name           = "${var.name}-shutoff"
  log_group_name = local.cutoff_log_group
  pattern        = "COST_GUARDRAIL_EVENT phase=shutoff"

  metric_transformation {
    name      = "ShutoffEvents"
    namespace = local.guardrail_namespace
    value     = "1"
  }
}

resource "aws_cloudwatch_log_metric_filter" "dry_run" {
  name           = "${var.name}-dry-run"
  log_group_name = local.cutoff_log_group
  pattern        = "COST_GUARDRAIL_EVENT dry_run=true"

  metric_transformation {
    name      = "DryRunEvents"
    namespace = local.guardrail_namespace
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "cutoff_errors" {
  alarm_name          = "${var.name}-cost-cutoff-errors"
  alarm_description   = "Cost cutoff Lambda errors — scale/shutoff may have failed"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 60
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.cutoff.function_name
  }

  alarm_actions = [aws_sns_topic.budget.arn]
  ok_actions    = [aws_sns_topic.budget.arn]
}

resource "aws_cloudwatch_metric_alarm" "soft_scale" {
  alarm_name          = "${var.name}-cost-soft-scale"
  alarm_description   = "Budget soft scale (50%) fired — EKS desired→1"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "SoftScaleEvents"
  namespace           = local.guardrail_namespace
  period              = 60
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.budget.arn]
}

resource "aws_cloudwatch_metric_alarm" "lock" {
  alarm_name          = "${var.name}-cost-lock"
  alarm_description   = "Budget hard lock (70%) fired — EKS max=1"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "LockEvents"
  namespace           = local.guardrail_namespace
  period              = 60
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.budget.arn]
}

resource "aws_cloudwatch_metric_alarm" "shutoff" {
  alarm_name          = "${var.name}-cost-shutoff"
  alarm_description   = "Budget shutoff (80%) fired — check EKS=0, RDS stopped, Redis deleted"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ShutoffEvents"
  namespace           = local.guardrail_namespace
  period              = 60
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.budget.arn]
}

# RDS stopped (single-AZ shutoff path)
resource "aws_cloudwatch_event_rule" "rds_stopped" {
  name        = "${var.name}-rds-stopped"
  description = "Notify when FreshEats RDS instance is stopped (shutoff)"

  event_pattern = jsonencode({
    source      = ["aws.rds"]
    detail-type = ["RDS DB Instance Event"]
    detail = {
      EventID          = ["RDS-EVENT-0087"]
      SourceIdentifier = [var.rds_instance_id]
    }
  })
}

resource "aws_cloudwatch_event_target" "rds_stopped_sns" {
  rule      = aws_cloudwatch_event_rule.rds_stopped.name
  target_id = "sns"
  arn       = aws_sns_topic.budget.arn
}

resource "aws_sns_topic_policy" "budget_events" {
  arn = aws_sns_topic.budget.arn
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowBudgets"
        Effect    = "Allow"
        Principal = { Service = "budgets.amazonaws.com" }
        Action    = "SNS:Publish"
        Resource  = aws_sns_topic.budget.arn
      },
      {
        Sid       = "AllowEventBridge"
        Effect    = "Allow"
        Principal = { Service = "events.amazonaws.com" }
        Action    = "SNS:Publish"
        Resource  = aws_sns_topic.budget.arn
        Condition = {
          ArnEquals = {
            "aws:SourceArn" = aws_cloudwatch_event_rule.rds_stopped.arn
          }
        }
      },
      {
        Sid       = "AllowCutoffLambda"
        Effect    = "Allow"
        Principal = { AWS = aws_iam_role.cutoff.arn }
        Action    = "SNS:Publish"
        Resource  = aws_sns_topic.budget.arn
      }
    ]
  })
}

resource "aws_cloudwatch_dashboard" "cost_guardrails" {
  dashboard_name = "${var.name}-cost-guardrails"

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
            # ${var.name} cost guardrails
            **50%** soft scale → **70%** lock → **80%** shutoff · DRY_RUN=${var.dry_run}
            Alarms + budget emails → SNS `${var.name}-budget-alerts`
          EOT
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 2
        width  = 8
        height = 6
        properties = {
          title  = "Cutoff Lambda"
          region = var.aws_region
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", aws_lambda_function.cutoff.function_name],
            [".", "Errors", ".", "."],
            [".", "Duration", ".", "."],
          ]
          period = 60
          stat   = "Sum"
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 2
        width  = 8
        height = 6
        properties = {
          title  = "Guardrail phases"
          region = var.aws_region
          metrics = [
            [local.guardrail_namespace, "SoftScaleEvents"],
            [".", "LockEvents"],
            [".", "ShutoffEvents"],
            [".", "DryRunEvents"],
          ]
          period = 60
          stat   = "Sum"
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 2
        width  = 8
        height = 6
        properties = {
          title  = "RDS ${var.rds_instance_id}"
          region = var.aws_region
          metrics = [
            ["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", var.rds_instance_id],
            [".", "DatabaseConnections", ".", "."],
          ]
          period = 60
          stat   = "Average"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 8
        width  = 12
        height = 6
        properties = {
          title  = "Redis ${var.redis_cluster_id}"
          region = var.aws_region
          metrics = [
            ["AWS/ElastiCache", "CPUUtilization", "CacheClusterId", var.redis_cluster_id],
            [".", "CurrConnections", ".", "."],
          ]
          period = 60
          stat   = "Average"
        }
      },
      {
        type   = "log"
        x      = 12
        y      = 8
        width  = 12
        height = 6
        properties = {
          title  = "Cutoff Lambda logs"
          region = var.aws_region
          query  = <<-EOT
            SOURCE '${local.cutoff_log_group}'
            | fields @timestamp, @message
            | filter @message like /COST_GUARDRAIL_EVENT|Shutoff|DRY_RUN|Scaling node/
            | sort @timestamp desc
            | limit 50
          EOT
        }
      },
      {
        type   = "text"
        x      = 0
        y      = 14
        width  = 24
        height = 3
        properties = {
          markdown = <<-EOT
            ### After shutoff — confirm resources
            ```bash
            aws eks describe-nodegroup --cluster-name ${var.eks_cluster_name} --nodegroup-name ${var.name}-general --query nodegroup.scalingConfig
            aws rds describe-db-instances --db-instance-identifier ${var.rds_instance_id} --query 'DBInstances[0].DBInstanceStatus'
            aws elasticache describe-cache-clusters --cache-cluster-id ${var.redis_cluster_id}
            ```
          EOT
        }
      }
    ]
  })
}

output "cost_guardrails_dashboard_name" { value = aws_cloudwatch_dashboard.cost_guardrails.dashboard_name }
output "cost_guardrails_dashboard_url" {
  value = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.cost_guardrails.dashboard_name}"
}
