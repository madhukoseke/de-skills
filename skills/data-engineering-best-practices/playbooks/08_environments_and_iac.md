---
title: "Environments & IaC"
description: "Multi-environment strategy, GCP project structure, Terraform patterns, CI/CD for data engineering"
tags: [environments, terraform, iac, ci-cd, gcp, cloud-build, github-actions]
related_templates:
  - ../templates/runbook.md
---

# Environments & IaC Playbook

> **Guiding principles:** Environments must be code-identical. Separation of concerns. Lineage is not optional.
> Infrastructure is code. Pipelines are code. Both belong in version control and must go through CI.

---

## 1. GCP Project Structure

### Recommended: Separate Projects Per Environment

```
GCP Organization
├── my-company-de-dev          # Development / sandbox
├── my-company-de-staging      # Staging / pre-prod
└── my-company-de-prod         # Production (hardened IAM, VPC SC)
```

**Why separate projects over separate datasets in one project?**
- Billing isolation: dev spending cannot impact prod budgets
- IAM isolation: dev engineers cannot accidentally access prod data
- Quota isolation: a runaway dev job does not exhaust prod API quotas
- VPC Service Controls can be applied independently per project

### When One Project Is Acceptable

Acceptable only for very small teams or early-stage products:
- Total team < 5 engineers
- No PII or regulated data
- Monthly GCP spend < $2,000
- No external consumers of prod data

Even then: use separate BQ datasets with strict IAM, not a single dataset with naming prefixes.

---

## 2. Dataset and Resource Naming Convention

Apply environment as a suffix on dataset names when using a single project (not recommended), or encode it in the project ID.

### With Separate Projects (Recommended)

```
Project: my-company-de-prod
  BQ Datasets:
    raw_salesforce          (not raw_salesforce_prod — project already encodes env)
    stg_salesforce
    cur_sales
    mart_revenue

Project: my-company-de-staging
  BQ Datasets:
    raw_salesforce          (same names, different project = environment parity)
    stg_salesforce
    cur_sales
    mart_revenue
```

### GCP Resource Naming Convention

```
{service}-{domain}-{environment}
```

| Resource | Dev | Staging | Prod |
|---|---|---|---|
| Composer environment | `composer-orders-dev` | `composer-orders-staging` | `composer-orders-prod` |
| Pub/Sub topic | `dev-orders-created` | `staging-orders-created` | `prod-orders-created` |
| GCS bucket | `my-co-de-raw-dev` | `my-co-de-raw-staging` | `my-co-de-raw-prod` |
| Dataflow job template | `orders-etl-dev` | `orders-etl-staging` | `orders-etl-prod` |
| Cloud Run service | `extractor-orders-dev` | `extractor-orders-staging` | `extractor-orders-prod` |

---

## 3. Terraform Module Structure

```
infrastructure/
├── modules/
│   ├── bigquery/            # Reusable BQ dataset + table module
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── composer/            # Cloud Composer environment module
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── pubsub/              # Pub/Sub topic + subscription + DLT module
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   └── iam/                 # Service account + role bindings module
│       ├── main.tf
│       └── variables.tf
├── environments/
│   ├── dev/
│   │   ├── main.tf          # Calls modules with dev-specific vars
│   │   ├── terraform.tfvars
│   │   └── backend.tf       # Remote state in GCS (dev bucket)
│   ├── staging/
│   │   ├── main.tf
│   │   ├── terraform.tfvars
│   │   └── backend.tf
│   └── prod/
│       ├── main.tf
│       ├── terraform.tfvars
│       └── backend.tf
└── shared/
    ├── org_policies.tf      # Org-level guardrails
    └── billing_alerts.tf    # Budget alerts per environment
```

### BigQuery Module

```hcl
# modules/bigquery/main.tf

variable "project_id" { type = string }
variable "location"   { type = string; default = "US" }
variable "environment" { type = string }

variable "datasets" {
  type = map(object({
    description = string
    labels      = map(string)
    delete_contents_on_destroy = bool
    tables = map(object({
      schema              = string   # JSON schema file path
      partition_field     = string
      partition_type      = string
      clustering_fields   = list(string)
      expiration_ms       = number
      labels              = map(string)
    }))
  }))
}

resource "google_bigquery_dataset" "datasets" {
  for_each  = var.datasets
  project   = var.project_id
  dataset_id = each.key
  location  = var.location
  description = each.value.description

  labels = merge(each.value.labels, {
    environment = var.environment
    managed_by  = "terraform"
  })

  delete_contents_on_destroy = each.value.delete_contents_on_destroy

  # Prevent accidental deletion of production datasets
  lifecycle {
    prevent_destroy = true
  }
}

resource "google_bigquery_table" "tables" {
  for_each = {
    for combo in flatten([
      for dataset_key, dataset in var.datasets : [
        for table_key, table in dataset.tables : {
          dataset_key = dataset_key
          table_key   = table_key
          table       = table
        }
      ]
    ]) : "${combo.dataset_key}.${combo.table_key}" => combo
  }

  project    = var.project_id
  dataset_id = each.value.dataset_key
  table_id   = each.value.table_key
  schema     = file(each.value.table.schema)

  dynamic "time_partitioning" {
    for_each = each.value.table.partition_field != "" ? [1] : []
    content {
      type  = each.value.table.partition_type
      field = each.value.table.partition_field
    }
  }

  clustering = length(each.value.table.clustering_fields) > 0 ? each.value.table.clustering_fields : null

  labels = merge(each.value.table.labels, {
    environment = var.environment
    managed_by  = "terraform"
  })

  deletion_protection = var.environment == "prod" ? true : false
}
```

### Pub/Sub Module with DLT

```hcl
# modules/pubsub/main.tf

variable "project_id"   { type = string }
variable "environment"  { type = string }

variable "topics" {
  type = map(object({
    schema_id            = string
    message_retention_duration = string
    subscriptions = map(object({
      ack_deadline_seconds      = number
      max_delivery_attempts     = number
      enable_exactly_once       = bool
      message_retention_duration = string
    }))
  }))
}

resource "google_pubsub_topic" "topics" {
  for_each = var.topics
  project  = var.project_id
  name     = "${var.environment}-${each.key}"

  message_retention_duration = each.value.message_retention_duration

  labels = {
    environment = var.environment
    managed_by  = "terraform"
  }
}

resource "google_pubsub_topic" "dead_letter_topics" {
  for_each = var.topics
  project  = var.project_id
  name     = "${var.environment}-${each.key}-dead-letter"
  labels = {
    environment = var.environment
    managed_by  = "terraform"
    type        = "dead-letter"
  }
}

resource "google_pubsub_subscription" "subscriptions" {
  for_each = merge([
    for topic_key, topic in var.topics : {
      for sub_key, sub in topic.subscriptions :
      "${topic_key}-${sub_key}" => merge(sub, { topic_key = topic_key })
    }
  ]...)

  project = var.project_id
  name    = "${var.environment}-${each.key}"
  topic   = google_pubsub_topic.topics[each.value.topic_key].name

  ack_deadline_seconds = each.value.ack_deadline_seconds
  enable_exactly_once_delivery = each.value.enable_exactly_once

  message_retention_duration = each.value.message_retention_duration

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dead_letter_topics[each.value.topic_key].id
    max_delivery_attempts = each.value.max_delivery_attempts
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  labels = {
    environment = var.environment
    managed_by  = "terraform"
  }
}
```

### Environment-Specific tfvars

```hcl
# environments/prod/terraform.tfvars

project_id  = "my-company-de-prod"
environment = "prod"
location    = "US"

datasets = {
  raw_salesforce = {
    description = "Raw Salesforce data ingested from Fivetran"
    labels      = { domain = "sales", tier = "raw" }
    delete_contents_on_destroy = false
    tables = {
      opportunities = {
        schema            = "../../schemas/salesforce_opportunities.json"
        partition_field   = "close_date"
        partition_type    = "DAY"
        clustering_fields = ["stage_name", "owner_id"]
        expiration_ms     = 0   # no expiration for raw
        labels            = { source = "salesforce" }
      }
    }
  }
}
```

---

## 4. IAM: Least Privilege Service Accounts

Every pipeline component must have its own service account with the minimum required permissions.

### Service Account Pattern

```hcl
# modules/iam/main.tf

variable "service_accounts" {
  type = map(object({
    description = string
    roles       = list(string)
    project_id  = string
  }))
}

resource "google_service_account" "accounts" {
  for_each     = var.service_accounts
  project      = each.value.project_id
  account_id   = each.key
  display_name = each.value.description
}

resource "google_project_iam_member" "bindings" {
  for_each = merge([
    for sa_key, sa in var.service_accounts : {
      for role in sa.roles :
      "${sa_key}-${replace(role, "/", "_")}" => {
        sa_email = google_service_account.accounts[sa_key].email
        role     = role
        project  = sa.project_id
      }
    }
  ]...)

  project = each.value.project
  role    = each.value.role
  member  = "serviceAccount:${each.value.sa_email}"
}
```

### Standard Service Account Matrix

| Component | Service Account | Required Roles |
|---|---|---|
| Cloud Composer | `sa-composer@{project}` | `roles/bigquery.dataEditor`, `roles/bigquery.jobUser`, `roles/storage.objectAdmin`, `roles/pubsub.subscriber` |
| Dataflow jobs | `sa-dataflow@{project}` | `roles/dataflow.worker`, `roles/bigquery.dataEditor`, `roles/storage.objectAdmin` |
| Cloud Run extractors | `sa-extractor@{project}` | `roles/storage.objectCreator`, `roles/pubsub.publisher` |
| dbt Cloud / dbt Core | `sa-dbt@{project}` | `roles/bigquery.dataEditor`, `roles/bigquery.jobUser` |
| CI/CD pipeline | `sa-cicd@{project}` | `roles/bigquery.dataViewer` (dry-run only), `roles/run.developer` |

**Never use** `roles/bigquery.admin`, `roles/owner`, or `roles/editor` for pipeline service accounts.

---

## 5. CI/CD Pipeline for Data Engineering

### What Must Run in CI

Every PR to main must pass:

```
[ PR opened ]
    │
    ├── Lint: sqlfluff (SQL), flake8/ruff (Python), terraform fmt
    ├── Validate: terraform validate, terraform plan (no apply)
    ├── dbt compile (syntax check, no execution)
    ├── dbt test --select {changed_models} (against dev BQ project)
    ├── Unit tests: pytest for Python operators and helpers
    └── Cost dry-run: bq query --dry_run for changed SQL files
```

### Cloud Build Configuration

```yaml
# cloudbuild.yaml
steps:

  # 1. Python lint
  - name: 'python:3.11-slim'
    id: python-lint
    entrypoint: bash
    args:
      - -c
      - |
        pip install ruff --quiet
        ruff check dags/ plugins/ --select E,W,F

  # 2. SQL lint
  - name: 'python:3.11-slim'
    id: sql-lint
    entrypoint: bash
    args:
      - -c
      - |
        pip install sqlfluff --quiet
        sqlfluff lint dbt_project/models/ --dialect bigquery

  # 3. Terraform validate
  - name: 'hashicorp/terraform:1.7'
    id: terraform-validate
    dir: infrastructure/environments/$_ENVIRONMENT
    args: ['validate']

  # 4. Terraform plan (no apply in CI)
  - name: 'hashicorp/terraform:1.7'
    id: terraform-plan
    dir: infrastructure/environments/$_ENVIRONMENT
    args:
      - plan
      - -var="project_id=$_PROJECT_ID"
      - -out=tfplan

  # 5. dbt compile
  - name: 'python:3.11-slim'
    id: dbt-compile
    dir: dbt_project
    entrypoint: bash
    args:
      - -c
      - |
        pip install dbt-bigquery --quiet
        dbt compile --target dev --project-dir .

  # 6. dbt test on changed models
  - name: 'python:3.11-slim'
    id: dbt-test
    dir: dbt_project
    entrypoint: bash
    args:
      - -c
      - |
        dbt test --select state:modified+ --target dev --defer --state ./prod-manifest

  # 7. Python unit tests
  - name: 'python:3.11-slim'
    id: pytest
    entrypoint: bash
    args:
      - -c
      - |
        pip install pytest pytest-mock apache-airflow --quiet
        pytest tests/ -v --tb=short

  # 8. BQ cost dry-run for changed SQL
  - name: 'gcr.io/cloud-builders/gcloud'
    id: bq-dry-run
    entrypoint: bash
    args:
      - -c
      - |
        for f in $(git diff --name-only origin/main HEAD -- '*.sql'); do
          echo "=== Dry-run: $f ==="
          bq query --dry_run --nouse_legacy_sql < "$f" || true
        done

substitutions:
  _ENVIRONMENT: staging
  _PROJECT_ID: my-company-de-staging

options:
  machineType: E2_HIGHCPU_8
  logging: CLOUD_LOGGING_ONLY
```

### GitHub Actions Alternative

```yaml
# .github/workflows/de-ci.yml
name: DE CI Pipeline

on:
  pull_request:
    branches: [main]

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write   # for Workload Identity Federation

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # needed for dbt state comparison

      - name: Authenticate to GCP
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.WIF_PROVIDER }}
          service_account: ${{ secrets.CI_SA_EMAIL }}

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install ruff sqlfluff dbt-bigquery pytest pytest-mock apache-airflow

      - name: Lint Python
        run: ruff check dags/ plugins/

      - name: Lint SQL
        run: sqlfluff lint dbt_project/models/ --dialect bigquery

      - name: dbt compile
        run: dbt compile --target dev
        working-directory: dbt_project

      - name: dbt test (changed models only)
        run: dbt test --select state:modified+ --defer --state ./prod-manifest --target dev
        working-directory: dbt_project

      - name: Run pytest
        run: pytest tests/ -v

  terraform-plan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: 1.7.0

      - name: Terraform Init
        run: terraform init
        working-directory: infrastructure/environments/staging

      - name: Terraform Plan
        run: terraform plan -var="project_id=${{ secrets.STAGING_PROJECT_ID }}"
        working-directory: infrastructure/environments/staging
```

---

## 6. Deployment Strategy

### Promotion Flow

```
feature branch
    │
    ├── [CI passes] → merge to main
    │
    └── main
         │
         ├── Auto-deploy to dev (Terraform apply + dbt run --target dev)
         │
         ├── Manual approval → deploy to staging
         │    └── [Integration tests pass]
         │
         └── Manual approval → deploy to prod
              └── [Smoke test: row count + freshness checks]
```

**Never auto-deploy to production.** Always require a human gate before prod changes.

### dbt Slim CI: State-Aware Testing

Instead of running all dbt tests on every PR (too slow), use state comparison:

```bash
# In CI: fetch the latest prod manifest for state comparison
gsutil cp gs://my-co-dbt-artifacts/prod/manifest.json ./prod-manifest/manifest.json

# Run only tests for models that changed vs main
dbt test --select state:modified+ --defer --state ./prod-manifest --target staging
```

Upload the manifest after every successful prod run:

```bash
dbt run --target prod
gsutil cp target/manifest.json gs://my-co-dbt-artifacts/prod/manifest.json
```

---

## 7. Secret Management Strategy

Never store secrets in code, tfvars, or environment variables in plain text.

### Secret Hierarchy

```
Google Secret Manager (source of truth)
    │
    ├── Airflow Connections → via Composer Secret Manager backend
    ├── dbt profiles → injected as env vars at runtime via Cloud Build / GitHub Actions secrets
    ├── Terraform variables → via Secret Manager + data sources in Terraform
    └── Cloud Run → mounted as env vars from Secret Manager
```

### Accessing Secrets in Terraform

```hcl
data "google_secret_manager_secret_version" "db_password" {
  secret  = "orders-db-password"
  project = var.project_id
}

resource "google_cloud_run_service" "extractor" {
  name = "extractor-orders-${var.environment}"
  # ...
  template {
    spec {
      containers {
        env {
          name = "DB_PASSWORD"
          value_from {
            secret_key_ref {
              name = "orders-db-password"
              key  = "latest"
            }
          }
        }
      }
    }
  }
}
```

### Rotating Secrets Without Downtime

1. Create new secret version in Secret Manager.
2. Update service (Cloud Run revision, Composer Variable) to use new version.
3. Verify connectivity.
4. Disable (do not delete) the old secret version.
5. Delete after 7-day observation window.

---

## 8. Cost Controls Per Environment

Set budget alerts to catch runaway jobs before they cause bill shock.

```hcl
# shared/billing_alerts.tf
resource "google_billing_budget" "de_budgets" {
  for_each       = toset(["dev", "staging", "prod"])
  billing_account = var.billing_account_id
  display_name   = "DE ${each.key} budget"

  budget_filter {
    projects = ["projects/${var.project_ids[each.key]}"]
    services = [
      "services/95FF-2EF5-5EA1",  # BigQuery
      "services/E3C1-7B46-D82A",  # Dataflow
      "services/A1E8-BE35-7EFA",  # Cloud Composer
    ]
  }

  amount {
    specified_amount {
      currency_code = "USD"
      units         = tostring(var.monthly_budgets[each.key])
    }
  }

  threshold_rules { threshold_percent = 0.5;  spend_basis = "CURRENT_SPEND" }
  threshold_rules { threshold_percent = 0.8;  spend_basis = "CURRENT_SPEND" }
  threshold_rules { threshold_percent = 1.0;  spend_basis = "CURRENT_SPEND" }
  threshold_rules { threshold_percent = 1.2;  spend_basis = "FORECASTED_SPEND" }

  all_updates_rule {
    pubsub_topic = google_pubsub_topic.billing_alerts.id
  }
}
```

**Typical budget guardrails by environment:**

| Environment | Monthly Budget | Alert Behavior |
|---|---|---|
| Dev | $500 | Alert at 80%, disable BQ slot reservations at 100% |
| Staging | $2,000 | Alert at 80%, page at 100% |
| Prod | $20,000 | Alert at 80%, P1 incident at 100% |

---

## 9. Anti-Patterns

| Anti-Pattern | Risk | Fix |
|---|---|---|
| Single GCP project for all environments | Dev jobs exhaust prod quotas; dev engineers access prod data | Separate projects per environment |
| Secrets in `terraform.tfvars` committed to Git | Credential exposure | Use Secret Manager + Terraform data sources |
| Auto-deploying to prod from CI | Untested changes hit prod | Require manual approval gate before prod deploy |
| Different code per environment (env-specific branches) | Bugs exist only in prod; impossible to reproduce in dev | One codebase, environment only via config/vars |
| Hardcoded project IDs in DAG files | DAGs break when project changes; not portable | Use Airflow Variables or Connections for all project IDs |
| Shared service account across pipelines | One compromised pipeline = blast radius across all data | One SA per pipeline component, least privilege |
| No deletion protection on prod BQ tables | `terraform destroy` or a bug deletes prod tables | Set `deletion_protection = true` on all prod resources |
| Running `terraform apply` locally against prod | Bypasses CI gates, no audit trail | Restrict prod TF apply to CI/CD service account only |
| No resource tagging/labeling | Cost attribution impossible | Label every resource with `environment`, `team`, `pipeline` |

---

## Quick Reference Checklist: Environment Readiness

Before launching a new environment:

- [ ] Separate GCP project created with billing linked
- [ ] Terraform remote state backend configured (GCS bucket in that project)
- [ ] Service accounts created with least-privilege IAM (no `Owner`, no `Editor`)
- [ ] Secret Manager enabled; all secrets stored there (no plaintext in code)
- [ ] VPC Service Controls configured if project handles PII or regulated data
- [ ] Budget alerts configured at 50%, 80%, 100%, 120% of monthly budget
- [ ] CI/CD pipeline requires passing gates before deploy
- [ ] Production has `deletion_protection = true` on all BQ tables
- [ ] Workload Identity Federation configured for CI (no long-lived SA keys)
- [ ] Environment promoted only after staging validation passes
