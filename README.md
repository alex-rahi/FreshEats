# Plate

**Grid-style recipe sharing** for web and mobile — Expo + React Native Web, FastAPI, Cognito/JWT, YOLO moderation, and AWS (EKS) ready.

| Surface | Stack |
|---|---|
| Mobile / Web | React Native · Expo · TypeScript · React Native Web · Cognito |
| API | FastAPI · Uvicorn · Pydantic · JWT |
| Data (local) | Docker Postgres / in-memory demo |
| Data (AWS) | RDS PostgreSQL · S3 · CloudFront · SQS · ElastiCache |
| Moderation | YOLOv8 food/cooking detection + manual review queue |
| Admin | Next.js · Tailwind CSS |
| Ops | Docker Compose · Terraform · EKS · GitHub Actions |

## Screens

- Sign Up / Log In
- Recipe Grid (2-column mobile, more on larger screens)
- Upload Recipe · Recipe Details · User Profile

Grid cards: **image · title · username · like count · comment count**.

## Quick start (demo mode)

```bash
cp .env.example .env
cd backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

```bash
cd apps/mobile && npm install && npx expo start --web
```

```bash
cd apps/admin && npm install && npm run dev
```

Demo login: any email/password.

## AWS (EKS + full AWS)

See **[docs/AWS.md](docs/AWS.md)** for Terraform, Cognito, RDS, S3, SQS, EKS manifests, and CI/CD.

```bash
cd infrastructure/terraform/environments/prod
terraform init && terraform apply
psql "$DATABASE_URL" -f ../../../sql/001_aws_schema.sql
```

## Local YOLO (Docker)

```bash
USE_PLACEHOLDERS=false USE_LOCAL_YOLO=true docker compose up --build
```

## Project layout

```
apps/mobile/                  Expo app (Cognito + demo auth)
apps/admin/                   Moderation dashboard
backend/                      FastAPI (Cognito/S3/SQS/RDS adapters)
workers/                      YOLO HTTP + SQS consumer
infrastructure/terraform/     VPC, EKS, RDS, S3, CDN, SQS, Cognito, ECR, IRSA
infrastructure/kubernetes/    Deployments, HPA, Ingress
infrastructure/sql/           AWS Postgres schema
docs/AWS.md                   Deploy guide
.github/workflows/deploy.yml  OIDC → Terraform → ECR → kubectl
```
