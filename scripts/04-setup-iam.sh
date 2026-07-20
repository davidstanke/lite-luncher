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

SA_EMAIL="${GCP_SA_GITHUB_ACTIONS}@${GCP_PROJECT_ID}.iam.gserviceaccount.com"

echo "Adding IAM roles to GitHub Actions Service Account: ${SA_EMAIL}..."

# List of roles required for GitHub Actions to manage and deploy to Cloud Run via Terraform
ROLES=(
    "artifactregistry.admin"
    "cloudbuild.builds.editor"
    "run.admin"
    "iam.serviceAccountUser"
    "logging.logWriter"
    "storage.admin"
    "resourcemanager.projectIamAdmin"
)

for role in "${ROLES[@]}"; do
  echo "Binding role roles/${role}..."
  gcloud projects add-iam-policy-binding "$GCP_PROJECT_ID" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role "roles/$role" \
    --condition=None >/dev/null
done

echo "IAM bindings successfully applied."
