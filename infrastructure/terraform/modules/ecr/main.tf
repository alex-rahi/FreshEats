variable "name" { type = string }

locals {
  repos = ["api", "worker", "admin"]
}

resource "aws_ecr_repository" "this" {
  for_each             = toset(local.repos)
  name                 = "${var.name}-${each.key}"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration { scan_on_push = true }
}

output "repository_urls" {
  value = { for k, r in aws_ecr_repository.this : k => r.repository_url }
}
