# Plate AWS infrastructure

- `terraform/` — modules + `environments/prod` (includes cost guardrails)
- `kubernetes/` — EKS manifests (api, worker, admin, ingress)
- `sql/001_aws_schema.sql` — RDS schema (no Supabase auth.users)
- `terraform/modules/cost_guardrails/` — $100 monthly budget → SNS → cutoff Lambda

Apply order: Terraform → SQL → Secrets → kubectl apply. See [docs/AWS.md](../docs/AWS.md).
