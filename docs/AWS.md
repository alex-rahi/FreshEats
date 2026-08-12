# FreshEats on AWS (EKS + full AWS)

## Architecture

```
Expo app ──Cognito JWT──▶ ALB / Ingress ──▶ FastAPI (EKS)
                                              ├─ RDS PostgreSQL
                                              ├─ S3 (presigned PUT)
                                              └─ SQS moderation queue
                                                   └─ YOLO worker (EKS)
CloudFront ──▶ S3 recipe-images
Admin (Next.js on EKS) ──X-Admin-Secret──▶ FastAPI
```

## Components

| Layer | AWS service |
|-------|-------------|
| Auth | Cognito User Pool |
| API / Admin / Worker | EKS |
| Database | RDS PostgreSQL 16 (Multi-AZ) |
| Images | S3 + CloudFront OAC |
| Moderation queue | SQS + DLQ |
| Cache | ElastiCache Redis |
| Images/repos | ECR |
| Secrets | Secrets Manager + K8s Secret |
| IaC | Terraform under `infrastructure/terraform/` |
| Cost guardrails | AWS Budgets ($100 default) → SNS → Lambda cutoff |

## Cost guardrails ($100 monthly budget)

Progressive spend protection (`modules/cost_guardrails`):

| Phase | Threshold | Action |
|-------|-----------|--------|
| **1 / 2** | **50%** ($50) | SNS email alert only |
| **2** | **70%** ($70) | Scale EKS node groups → **desired=1** (keep minimal footprint) |
| **1 / 2** | **80%** ($80) | **Shutoff**: EKS → 0, delete ElastiCache, stop/tag RDS |

Configure in `infrastructure/terraform/environments/prod/terraform.tfvars`:

```hcl
budget_limit_usd    = 100
budget_alert_emails = ["you@example.com"]
# optional overrides:
# alert_threshold   = 50
# scale_threshold   = 70
# shutoff_threshold = 80
```

**Limits to know:**
- AWS Budgets lag by ~hours — this is not instantaneous to-the-penny.
- Multi-AZ RDS cannot be stopped via API; the Lambda tags it and you must stop/delete manually (or change RDS to single-AZ in Terraform for auto-stop).
- S3 / Cognito / ECR data is kept (storage is cheap); only compute is burned down.
- Confirm the SNS email subscription after `terraform apply`.
- Optional: attach `deny_spend_policy_arn` to IAM users/roles to block new EC2/EKS/RDS creates after a breach.

## Apply infrastructure

```bash
cd infrastructure/terraform/environments/prod
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform apply
```

Capture outputs:

- `cognito_user_pool_id`, `cognito_client_id`, `cognito_issuer`
- `sqs_moderation_url`, `s3_*`, `cloudfront_domain`
- `database_url` (sensitive), `ecr_urls`, IRSA role ARNs

## Bootstrap database

```bash
psql "$DATABASE_URL" -f infrastructure/sql/001_aws_schema.sql
```

## Configure Kubernetes secrets

```bash
cp infrastructure/kubernetes/secrets.example.yaml /tmp/fresheats-secrets.yaml
# fill values from terraform output
kubectl apply -f infrastructure/kubernetes/namespace.yaml
kubectl apply -f /tmp/fresheats-secrets.yaml
# patch IRSA role ARNs + ECR image URLs in deployment YAMLs
kubectl apply -f infrastructure/kubernetes/
```

## App environment (AWS mode)

### API / worker pods

```
AUTH_PROVIDER=cognito
USE_PLACEHOLDERS=false
USE_LOCAL_YOLO=false
COGNITO_USER_POOL_ID=...
COGNITO_CLIENT_ID=...
COGNITO_ISSUER=https://cognito-idp.us-east-1.amazonaws.com/...
DATABASE_URL=postgresql://...
SQS_MODERATION_URL=https://sqs...
STORAGE_BUCKET_RAW=fresheats-raw-uploads
STORAGE_BUCKET_RECIPES=fresheats-recipe-images
CLOUDFRONT_DOMAIN=dxxxx.cloudfront.net
AWS_REGION=us-east-1
ADMIN_SECRET=...
```

### Mobile

```
EXPO_PUBLIC_USE_PLACEHOLDERS=false
EXPO_PUBLIC_USE_LOCAL_YOLO=false
EXPO_PUBLIC_API_URL=https://api.fresheats.app
EXPO_PUBLIC_COGNITO_USER_POOL_ID=...
EXPO_PUBLIC_COGNITO_CLIENT_ID=...
EXPO_PUBLIC_AWS_REGION=us-east-1
EXPO_PUBLIC_CDN_URL=https://dxxxx.cloudfront.net
```

Enable Cognito app client auth flow **USER_PASSWORD_AUTH** (Terraform already sets this).

## Upload / moderation flow (AWS)

1. `POST /api/v1/recipes` → creates recipe + `moderation_jobs` row + **presigned S3 PUT**
2. Client uploads image to S3
3. `POST /api/v1/recipes/{id}/confirm-upload` → copy to recipes bucket, enqueue SQS
4. Worker (`python -m app.sqs_consumer`) downloads image, runs YOLO food rules
5. Outcome: `published` | `rejected` | `pending_review` → admin dashboard

## CI/CD

GitHub Actions workflow: [`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml)

Required secret: `AWS_DEPLOY_ROLE_ARN` (OIDC trust to this repo).

Pipeline: Terraform apply → build/push ECR (`api`, `worker`, `admin`) → `kubectl` rollout.

## Local demo vs AWS

| Mode | Flags | Auth | Storage | Moderation |
|------|-------|------|---------|------------|
| Demo | `USE_PLACEHOLDERS=true` | placeholder token | in-memory / local disk | auto-publish |
| Local YOLO | `USE_LOCAL_YOLO=true` | placeholder token | local disk | sync worker HTTP |
| AWS | `AUTH_PROVIDER=cognito` | Cognito JWT | S3 + CF | SQS + worker |

## Notes

- Replace `ACCOUNT_ID` and IRSA ARNs in Kubernetes manifests after first apply.
- Live `terraform apply` requires AWS credentials in your account — this repo ships the code, not a live deploy.
- Cognito `sub` is stored as `profiles.cognito_sub`; API maps JWT → profile UUID automatically.
