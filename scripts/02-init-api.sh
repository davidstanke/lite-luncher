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
# Unless required by applicable law or agreed slide to in writing, software
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

echo "Enabling Google Cloud APIs for project ${GCP_PROJECT_ID}..."

# Enable APIs needed for CI/CD, Container Building, Artifact Registry, and Cloud Run
for GOOGLE_CLOUD_API in \
  compute.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  cloudresourcemanager.googleapis.com \
  iam.googleapis.com \
  run.googleapis.com \
  servicecontrol.googleapis.com \
  serviceusage.googleapis.com \
  storage.googleapis.com \
  aiplatform.googleapis.com \
    ; do
  echo "Enabling ${GOOGLE_CLOUD_API}..."
  gcloud services enable --project "${GCP_PROJECT_ID}" "${GOOGLE_CLOUD_API}"
done

echo "Google Cloud APIs successfully enabled."

gcloud config set compute/region "${GCP_LOCATION}" >/dev/null 2>&1

echo "Google Cloud default region set to ${GCP_LOCATION}"