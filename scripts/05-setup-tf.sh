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

# Terraform directory
TF_DIR=$(pwd)/terraform

# Bucket name: bkt-tf-state-<project-id>-<repo-name>
BUCKET_NAME="bkt-tf-state-${GCP_PROJECT_ID}-${GITHUB_REPO}"

echo "Checking Terraform remote state bucket: gs://${BUCKET_NAME}..."

# First check if the TF state bucket already exists
if gcloud storage buckets describe "gs://${BUCKET_NAME}" --project="${GCP_PROJECT_ID}" >/dev/null 2>&1; then
  printf "Terraform remote state bucket found, continuing...\n"
else
  # Create Google Cloud Storage bucket for Terraform Remote State
  echo "Creating Terraform remote state bucket gs://${BUCKET_NAME}..."
  gcloud storage buckets create "gs://${BUCKET_NAME}" \
    --project="${GCP_PROJECT_ID}" \
    --location="${GCP_LOCATION}" \
    --public-access-prevention \
    --uniform-bucket-level-access
  
  # Enable versioning on the state bucket
  echo "Enabling versioning on state bucket..."
  gcloud storage buckets update "gs://${BUCKET_NAME}" --versioning
fi

# Set up tfvars file
if [ -f "$TF_DIR/terraform.tfvars.example" ]; then
  echo "Copying terraform.tfvars.example to terraform.tfvars..."
  cp "$TF_DIR/terraform.tfvars.example" "$TF_DIR/terraform.tfvars"

  echo "Injecting configured variables into terraform.tfvars..."
  # Use portable sed logic or standard bash replacements to edit the tfvars file
  if [[ "${OSTYPE:-linux-gnu}" == "darwin"* ]]; then
    # MacOS compatibility
    sed -i '' "s/your-unique-project-id/${GCP_PROJECT_ID}/g" "$TF_DIR/terraform.tfvars"
    sed -i '' "s/your-cloud-location/${GCP_LOCATION}/g" "$TF_DIR/terraform.tfvars"
  else
    # Linux standard
    sed -i "s/your-unique-project-id/${GCP_PROJECT_ID}/g" "$TF_DIR/terraform.tfvars"
    sed -i "s/your-cloud-location/${GCP_LOCATION}/g" "$TF_DIR/terraform.tfvars"
  fi
  echo "terraform/terraform.tfvars has been successfully generated."
else
  echo "Warning: terraform.tfvars.example not found in $TF_DIR"
fi

echo "Terraform environment initialization complete."
