variable "name" { type = string }
variable "recipes_bucket_id" { type = string }
variable "recipes_bucket_domain" { type = string }

resource "aws_cloudfront_origin_access_control" "recipes" {
  name                              = "${var.name}-recipes-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "recipes" {
  enabled             = true
  comment             = "${var.name} recipe images"
  default_root_object = ""

  origin {
    domain_name              = var.recipes_bucket_domain
    origin_id                = "recipes-s3"
    origin_access_control_id = aws_cloudfront_origin_access_control.recipes.id
  }

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "recipes-s3"
    viewer_protocol_policy = "redirect-to-https"
    compress               = true
    forwarded_values {
      query_string = false
      cookies { forward = "none" }
    }
  }

  restrictions {
    geo_restriction { restriction_type = "none" }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = { Name = "${var.name}-cdn" }
}

data "aws_iam_policy_document" "recipes_oac" {
  statement {
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    actions   = ["s3:GetObject"]
    resources = ["arn:aws:s3:::${var.recipes_bucket_id}/*"]
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.recipes.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "recipes" {
  bucket = var.recipes_bucket_id
  policy = data.aws_iam_policy_document.recipes_oac.json
}

output "domain_name" { value = aws_cloudfront_distribution.recipes.domain_name }
output "distribution_id" { value = aws_cloudfront_distribution.recipes.id }
