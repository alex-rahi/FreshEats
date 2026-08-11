variable "name" { type = string }
variable "subnet_ids" { type = list(string) }
variable "security_group_ids" { type = list(string) }
variable "node_type" {
  type    = string
  default = "cache.t4g.micro"
}

resource "aws_elasticache_subnet_group" "this" {
  name       = "${var.name}-redis"
  subnet_ids = var.subnet_ids
}

resource "aws_elasticache_cluster" "this" {
  cluster_id           = "${var.name}-redis"
  engine               = "redis"
  node_type            = var.node_type
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  port                 = 6379
  subnet_group_name    = aws_elasticache_subnet_group.this.name
  security_group_ids   = var.security_group_ids
}

output "endpoint" { value = aws_elasticache_cluster.this.cache_nodes[0].address }
output "port" { value = aws_elasticache_cluster.this.port }
output "cluster_id" { value = aws_elasticache_cluster.this.cluster_id }
