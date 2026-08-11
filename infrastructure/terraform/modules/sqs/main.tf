variable "name" { type = string }

resource "aws_sqs_queue" "dlq" {
  name                      = "${var.name}-moderation-dlq"
  message_retention_seconds = 1209600
}

resource "aws_sqs_queue" "moderation" {
  name                       = "${var.name}-moderation"
  visibility_timeout_seconds = 300
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = 5
  })
}

output "queue_url" { value = aws_sqs_queue.moderation.url }
output "queue_arn" { value = aws_sqs_queue.moderation.arn }
output "dlq_url" { value = aws_sqs_queue.dlq.url }
