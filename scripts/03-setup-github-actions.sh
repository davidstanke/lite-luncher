#!/bin/bash
set -euo pipefail

# Copyright 2026 Antigravity
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

if [ ! -f .env ]; then
  echo "Error: .env file not found. Please run scripts/01-setup-env.sh first."
  exit 1
fi

# Source environment variables
# shellcheck source=/dev/null
source .env

SA_NAME="${GCP_SA_GITHUB_ACTIONS}"
SA_EMAIL="${SA_NAME}@${GCP_PROJECT_ID}.iam.gserviceaccount.com"
POOL_NAME="github-actions-pool"
PROVIDER_NAME="github-actions-provider"

echo "Setting up Workload Identity and Service Account for GitHub Actions..."

# 1. Create the Google Cloud Service Account
if gcloud iam service-accounts describe "${SA_EMAIL}" --project="${GCP_PROJECT_ID}" >/dev/null 2>&1; then
    echo "Service Account ${SA_NAME} already exists."
else
    echo "Creating Service Account ${SA_NAME}..."
    gcloud iam service-accounts create "${SA_NAME}" \
      --project "${GCP_PROJECT_ID}" \
      --display-name="GitHub Actions Service Account"
fi

# 2. Create the Workload Identity Pool
if gcloud iam workload-identity-pools describe "${POOL_NAME}" --project="${GCP_PROJECT_ID}" --location="global" >/dev/null 2>&1; then
    echo "Workload Identity Pool '${POOL_NAME}' already exists."
else
    echo "Creating Workload Identity Pool '${POOL_NAME}'..."
    gcloud iam workload-identity-pools create "${POOL_NAME}" \
      --project="${GCP_PROJECT_ID}" \
      --location="global" \
      --display-name="GitHub Actions Pool"
fi

# 3. Create or update the Workload Identity Provider
if gcloud iam workload-identity-pools providers describe "${PROVIDER_NAME}" \
    --project="${GCP_PROJECT_ID}" \
    --location="global" \
    --workload-identity-pool="${POOL_NAME}" >/dev/null 2>&1; then
    echo "Workload Identity Provider '${PROVIDER_NAME}' already exists. Updating its configuration..."
    gcloud iam workload-identity-pools providers update-oidc "${PROVIDER_NAME}" \
      --project="${GCP_PROJECT_ID}" \
      --location="global" \
      --workload-identity-pool="${POOL_NAME}" \
      --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
      --attribute-condition="assertion.repository_owner == '${GITHUB_ORG}'" \
      --issuer-uri="https://token.actions.githubusercontent.com"
else
    echo "Creating Workload Identity Provider '${PROVIDER_NAME}'..."
    gcloud iam workload-identity-pools providers create-oidc "${PROVIDER_NAME}" \
      --project="${GCP_PROJECT_ID}" \
      --location="global" \
      --workload-identity-pool="${POOL_NAME}" \
      --display-name="GitHub Actions Provider" \
      --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
      --attribute-condition="assertion.repository_owner == '${GITHUB_ORG}'" \
      --issuer-uri="https://token.actions.githubusercontent.com"
fi

# Get the Project Number
PROJECT_NUMBER=$(gcloud projects describe "${GCP_PROJECT_ID}" --format="value(projectNumber)")

# 4. Allow authentications from the Workload Identity Pool to your Service Account
echo "Binding Workload Identity role to Service Account..."
gcloud iam service-accounts add-iam-policy-binding "${SA_EMAIL}" \
  --project="${GCP_PROJECT_ID}" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_NAME}/attribute.repository/${GITHUB_ORG}/${GITHUB_REPO}"

# 5. Extract the Workload Identity Provider resource name
GCP_WI_PROVIDER_ID="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_NAME}/providers/${PROVIDER_NAME}"

# Update .env
# Remove existing GCP_WI_PROVIDER_ID if any
grep -v "GCP_WI_PROVIDER_ID=" .env > .env.tmp && mv .env.tmp .env
echo "GCP_WI_PROVIDER_ID=\"${GCP_WI_PROVIDER_ID}\"" >> .env

cat << EOF

----- GITHUB ACTIONS ENV KEY/VALUE -----

GCP_SA_GITHUB_ACTIONS: ${SA_NAME}
GCP_PROJECT_ID:        ${GCP_PROJECT_ID}
GCP_LOCATION:          ${GCP_LOCATION}
GCP_WI_PROVIDER_ID:    ${GCP_WI_PROVIDER_ID}

----------------------------------------
EOF

# 6. Check for gh CLI and set GitHub Actions repository variables if logged in
GH_AVAILABLE=false
if command -v gh >/dev/null 2>&1; then
  if gh auth status > /dev/null 2>&1; then
    GH_AVAILABLE=true
  fi
fi

if [ "$GH_AVAILABLE" = true ]; then
  echo "gh: Authenticated CLI found. Setting GitHub Actions repository variables..."
  gh variable set GCP_SA_GITHUB_ACTIONS --body "${SA_NAME}" --repo "${GITHUB_ORG}/${GITHUB_REPO}"
  gh variable set GCP_PROJECT_ID --body "${GCP_PROJECT_ID}" --repo "${GITHUB_ORG}/${GITHUB_REPO}"
  gh variable set GCP_LOCATION --body "${GCP_LOCATION}" --repo "${GITHUB_ORG}/${GITHUB_REPO}"
  gh variable set GCP_WI_PROVIDER_ID --body "${GCP_WI_PROVIDER_ID}" --repo "${GITHUB_ORG}/${GITHUB_REPO}"
  echo "gh: Variables successfully set in repository ${GITHUB_ORG}/${GITHUB_REPO}"
else
  echo "gh CLI not authenticated or not installed. Please manually set the following variables in your GitHub Repository settings (Settings > Secrets and variables > Actions > Variables):"
  echo "  - GCP_SA_GITHUB_ACTIONS: ${SA_NAME}"
  echo "  - GCP_PROJECT_ID: ${GCP_PROJECT_ID}"
  echo "  - GCP_LOCATION: ${GCP_LOCATION}"
  echo "  - GCP_WI_PROVIDER_ID: ${GCP_WI_PROVIDER_ID}"
fi
