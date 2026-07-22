# 🤖 Antigravity Code Review Agent

An autonomous, Antigravity-powered code review agent designed to analyze GitHub Pull Requests for **code quality, maintainability, and readability**. Built with the Antigravity SDK (`google-genai`), `google-adk`, and `PyGithub`, and deployed as an Agent Runtime service on GCP Cloud Run.

---

## 📁 File Structure

```
/utils/agents/code-review/
├── Dockerfile                  # Container definition for Cloud Run / Agent Runtime
├── pyproject.toml              # Dependencies & build metadata
├── README.md                   # Documentation & Infrastructure Setup Guide
└── app/
    ├── __init__.py
    ├── agent.py                # Antigravity SDK review engine & PyGithub integration
    └── main.py                 # FastAPI service entrypoint
```

---

## ⚡ Local Development & Execution

### 1. Install Dependencies
```bash
cd utils/agents/code-review
uv sync
```

### 2. Authenticate with Application Default Credentials (ADC)
```bash
gcloud auth application-default login

# (Optional) Set GCP project and location
export GOOGLE_CLOUD_PROJECT="your-gcp-project-id"
export GOOGLE_CLOUD_LOCATION="us-central1"
```

### 3. Run Service
```bash
uv run uvicorn app.main:app --reload --port 8080
```

### 4. Trigger Local Review Request
```bash
curl -X POST http://localhost:8080/review \
  -H "Content-Type: application/json" \
  -d '{
    "repo_full_name": "davidstanke/lite-luncher",
    "pr_number": 1,
    "github_token": "ghp_your_github_token"
  }'
```

#### How to obtain a `github_token`:
1. Go to **GitHub Settings** > **Developer Settings** > **Personal Access Tokens** ([tokens page](https://github.com/settings/tokens)).
2. Select **Fine-grained tokens** (recommended) or **Tokens (classic)** and click **Generate new token**.
3. Set repository access for the target repository (e.g., `davidstanke/lite-luncher`).
4. Grant permissions:
   - **Pull requests**: Read and write (to post review comments)
   - **Contents**: Read-only (to read PR files and diffs)
5. Copy the generated token string (`ghp_...` or `github_pat_...`).
6. (optional) save to /.env which is .gitexcluded

---

## 🏗️ GCP Infrastructure Setup Guide

To allow GitHub Actions to trigger this agent securely on Agent Runtime without long-lived credentials, configure Workload Identity Federation:

```bash
# Set variables
export PROJECT_ID="luncher-davidstanke"
export REGION="us-central1"
export SERVICE_NAME="code-review-agent"
export SA_NAME="github-code-review-agent-sa"
export WORKPOOL_NAME="github-actions-pool"
export PROVIDER_NAME="github-actions-provider"
export REPO="davidstanke/lite-luncher"

# 1. Enable required GCP APIs
gcloud services enable \
  run.googleapis.com \
  iamcredentials.googleapis.com \
  iam.googleapis.com \
  cloudresourcemanager.googleapis.com \
  --project=${PROJECT_ID}

# 2. Create Service Account for GitHub Actions & Agent Runtime
gcloud iam service-accounts create ${SA_NAME} \
  --display-name="GitHub Actions Code Review Agent SA" \
  --project=${PROJECT_ID}

export SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# 3. Grant IAM roles to Service Account (Cloud Run Invoker & AI Platform User)
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/run.invoker"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/aiplatform.user"

# 4. Create Workload Identity Pool
gcloud iam workload-identity-pools create ${WORKPOOL_NAME} \
  --location="global" \
  --display-name="GitHub Actions Pool" \
  --project=${PROJECT_ID}

export WORKPOOL_ID=$(gcloud iam workload-identity-pools describe ${WORKPOOL_NAME} \
  --location="global" \
  --project=${PROJECT_ID} \
  --format="value(name)")

# 5. Create Workload Identity Provider for GitHub
gcloud iam workload-identity-pools providers create-oidc ${PROVIDER_NAME} \
  --location="global" \
  --workload-identity-pool=${WORKPOOL_NAME} \
  --display-name="GitHub Provider" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --project=${PROJECT_ID}

# 6. Allow GitHub repo to impersonate Service Account
gcloud iam service-accounts add-iam-policy-binding ${SA_EMAIL} \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/${WORKPOOL_ID}/attribute.repository/${REPO}" \
  --project=${PROJECT_ID}
```

---

## 🔐 GitHub Secrets Setup

In GitHub Repository Settings (`Settings > Secrets and variables > Actions`), add the following secrets:

| Secret Name | Description / Example Value |
| :--- | :--- |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | `projects/<PROJECT_NUMBER>/locations/global/workloadIdentityPools/github-actions-pool/providers/github-actions-provider` |
| `GCP_SERVICE_ACCOUNT` | `github-code-review-agent-sa@luncher-davidstanke.iam.gserviceaccount.com` |
| `CODE_REVIEW_AGENT_URL` | Cloud Run / Agent Runtime endpoint URL (e.g., `https://code-review-agent-98226488336.us-central1.run.app`) |

---

## 🚀 Deployment to Agent Runtime / Cloud Run

```bash
cd utils/agents/code-review

gcloud run deploy code-review-agent \
  --source=. \
  --project=luncher-davidstanke \
  --region=us-central1 \
  --allow-unauthenticated
```
