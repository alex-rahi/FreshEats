variable "name" { type = string }
variable "subnet_ids" { type = list(string) }
variable "security_group_ids" { type = list(string) }
variable "instance_class" {
  type    = string
  default = "db.t4g.micro"
}
variable "multi_az" {
  type        = bool
  default     = false
  description = "Single-AZ by default to fit budget and allow Lambda stop at shutoff"
}
variable "allocated_storage" {
  type    = number
  default = 20
}

resource "random_password" "db" {
  length  = 32
  special = false
}

resource "aws_db_subnet_group" "this" {
  name       = "${var.name}-db"
  subnet_ids = var.subnet_ids
  tags       = { Name = "${var.name}-db" }
}

resource "aws_secretsmanager_secret" "db" {
  name = "${var.name}/rds/credentials"
}

resource "aws_secretsmanager_secret_version" "db" {
  secret_id = aws_secretsmanager_secret.db.id
  secret_string = jsonencode({
    username = "fresheats"
    password = random_password.db.result
    dbname   = "fresheats"
  })
}

resource "aws_db_instance" "this" {
  identifier                 = "${var.name}-postgres"
  engine                     = "postgres"
  engine_version             = "16"
  instance_class             = var.instance_class
  allocated_storage          = var.allocated_storage
  max_allocated_storage      = 50
  db_name                    = "fresheats"
  username                   = "fresheats"
  password                   = random_password.db.result
  db_subnet_group_name       = aws_db_subnet_group.this.name
  vpc_security_group_ids     = var.security_group_ids
  multi_az                   = var.multi_az
  publicly_accessible        = false
  storage_encrypted          = true
  skip_final_snapshot        = true
  deletion_protection        = false
  backup_retention_period    = 3
  auto_minor_version_upgrade = true
  tags                       = { Name = "${var.name}-postgres" }
}

output "endpoint" { value = aws_db_instance.this.address }
output "port" { value = aws_db_instance.this.port }
output "db_name" { value = aws_db_instance.this.db_name }
output "secret_arn" { value = aws_secretsmanager_secret.db.arn }
output "instance_id" { value = aws_db_instance.this.id }
output "database_url" {
  value     = "postgresql://fresheats:${random_password.db.result}@${aws_db_instance.this.address}:5432/fresheats"
  sensitive = true
}
