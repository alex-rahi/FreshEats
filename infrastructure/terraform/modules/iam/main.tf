variable "name" { type = string }
variable "oidc_issuer" { type = string }
variable "raw_bucket_arn" { type = string }
variable "recipes_bucket_arn" { type = string }
variable "sqs_queue_arn" { type = string }
variable "db_secret_arn" { type = string }
variable "namespace" {
  type    = string
  default = "plate"
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  oidc_host = replace(var.oidc_issuer, "https://", "")
}

resource "aws_iam_openid_connect_provider" "eks" {
  url             = var.oidc_issuer
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["9e99a48a9960b14926bb7f3b02e22da2b0ab7280"]
}

data "aws_iam_policy_document" "api_assume" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.eks.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "${local.oidc_host}:sub"
      values   = ["system:serviceaccount:${var.namespace}:plate-api"]
    }
  }
}

resource "aws_iam_role" "api" {
  name               = "${var.name}-api-irsa"
  assume_role_policy = data.aws_iam_policy_document.api_assume.json
}

data "aws_iam_policy_document" "api" {
  statement {
    actions = [
      "s3:PutObject", "s3:GetObject", "s3:DeleteObject", "s3:ListBucket"
    ]
    resources = [
      var.raw_bucket_arn,
      "${var.raw_bucket_arn}/*",
      var.recipes_bucket_arn,
      "${var.recipes_bucket_arn}/*",
    ]
  }
  statement {
    actions   = ["sqs:SendMessage", "sqs:GetQueueAttributes", "sqs:GetQueueUrl"]
    resources = [var.sqs_queue_arn]
  }
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [var.db_secret_arn]
  }
}

resource "aws_iam_role_policy" "api" {
  name   = "${var.name}-api"
  role   = aws_iam_role.api.id
  policy = data.aws_iam_policy_document.api.json
}

data "aws_iam_policy_document" "worker_assume" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.eks.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "${local.oidc_host}:sub"
      values   = ["system:serviceaccount:${var.namespace}:plate-worker"]
    }
  }
}

resource "aws_iam_role" "worker" {
  name               = "${var.name}-worker-irsa"
  assume_role_policy = data.aws_iam_policy_document.worker_assume.json
}

data "aws_iam_policy_document" "worker" {
  statement {
    actions = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
    resources = [
      var.raw_bucket_arn,
      "${var.raw_bucket_arn}/*",
      var.recipes_bucket_arn,
      "${var.recipes_bucket_arn}/*",
    ]
  }
  statement {
    actions = [
      "sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:ChangeMessageVisibility",
      "sqs:GetQueueAttributes", "sqs:GetQueueUrl"
    ]
    resources = [var.sqs_queue_arn]
  }
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [var.db_secret_arn]
  }
}

resource "aws_iam_role_policy" "worker" {
  name   = "${var.name}-worker"
  role   = aws_iam_role.worker.id
  policy = data.aws_iam_policy_document.worker.json
}

output "api_role_arn" { value = aws_iam_role.api.arn }
output "worker_role_arn" { value = aws_iam_role.worker.arn }
