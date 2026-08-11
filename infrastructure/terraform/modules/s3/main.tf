variable "name" { type = string }

resource "aws_s3_bucket" "raw" {
  bucket = "${var.name}-raw-uploads"
  tags   = { Name = "${var.name}-raw-uploads" }
}

resource "aws_s3_bucket" "recipes" {
  bucket = "${var.name}-recipe-images"
  tags   = { Name = "${var.name}-recipe-images" }
}

resource "aws_s3_bucket_public_access_block" "raw" {
  bucket                  = aws_s3_bucket.raw.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "recipes" {
  bucket                  = aws_s3_bucket.recipes.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "recipes" {
  bucket = aws_s3_bucket.recipes.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_cors_configuration" "raw" {
  bucket = aws_s3_bucket.raw.id
  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["PUT", "GET", "HEAD"]
    allowed_origins = ["*"]
    max_age_seconds = 3000
  }
}

output "raw_bucket" { value = aws_s3_bucket.raw.id }
output "recipes_bucket" { value = aws_s3_bucket.recipes.id }
output "raw_bucket_arn" { value = aws_s3_bucket.raw.arn }
output "recipes_bucket_arn" { value = aws_s3_bucket.recipes.arn }
output "recipes_bucket_regional_domain" {
  value = aws_s3_bucket.recipes.bucket_regional_domain_name
}
