# FreshEats AWS infrastructure

- `terraform/` — modules + `environments/prod` (includes cost guardrails)
- `kubernetes/` — EKS manifests (api, worker, admin, ingress)
- `sql/001_aws_schema.sql` — RDS schema (no Supabase auth.users)
- `terraform/modules/cost_guardrails/` — $250 budget → SNS → progressive scale/lock/shutoff Lambda + CloudWatch dashboard/alarms

Apply order: Terraform → SQL → Secrets → kubectl apply. See [docs/AWS.md](../docs/AWS.md).
