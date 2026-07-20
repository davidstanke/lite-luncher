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

if ! command -v gh >/dev/null 2>&1; then
  echo "bash: gh: command not found"
  echo "Consider installing gh cli at: https://github.com/cli/cli#installation"
fi

# figure out if we're logged into the gh CLI
GH_AVAILABLE=false
if gh auth status > /dev/null 2>&1; then
  echo "gh: command found and logged into GitHub"
  GH_AVAILABLE=true
fi

# Obtain possible defaults of key environment variables:
_GITHUB_REPO="luncher"
_GITHUB_ORG=""
if [ "$GH_AVAILABLE" = true ]; then
  _GITHUB_ORG=$(gh repo view --json owner -q ".owner.login" 2>/dev/null || echo "")
  _GITHUB_REPO=$(gh repo view --json name -q ".name" 2>/dev/null || echo "luncher")
else
  # fallback to git remote parsing
  REMOTE_URL=$(git remote get-url origin 2>/dev/null || echo "")
  if [[ $REMOTE_URL =~ github.com[:/]([^/]+)/([^.]+)(\.git)? ]]; then
    _GITHUB_ORG="${BASH_REMATCH[1]}"
    _GITHUB_REPO="${BASH_REMATCH[2]}"
  fi
fi

_GCP_SA_GITHUB_ACTIONS="sa-github-actions"
_GCP_PROJECT_ID=$(gcloud config get-value project 2>/dev/null || echo "")
_GCP_LOCATION=$(gcloud config get-value compute/region 2>/dev/null || echo "")
_GCP_LOCATION=${_GCP_LOCATION:-us-central1}

# Request acceptance of defaults or alternatives
read -r -p "Enter GitHub organization or owner [${_GITHUB_ORG}]: " GITHUB_ORG
read -r -p "Enter GitHub repository name [${_GITHUB_REPO}]: " GITHUB_REPO
read -r -p "Enter GCP project ID [${_GCP_PROJECT_ID}]: " GCP_PROJECT_ID
read -r -p "Enter default value region for this setup [${_GCP_LOCATION}]: " GCP_LOCATION

GITHUB_ORG="${GITHUB_ORG:-${_GITHUB_ORG}}"
GITHUB_REPO="${GITHUB_REPO:-${_GITHUB_REPO}}"
GCP_SA_GITHUB_ACTIONS="${GCP_SA_GITHUB_ACTIONS:-${_GCP_SA_GITHUB_ACTIONS}}"
GCP_PROJECT_ID="${GCP_PROJECT_ID:-${_GCP_PROJECT_ID}}"
GCP_LOCATION="${GCP_LOCATION:-${_GCP_LOCATION}}"

if [ -z "$GCP_PROJECT_ID" ]; then
  echo "Error: GCP project ID must not be empty. Please run gcloud config set project [PROJECT_ID] or specify one."
  exit 1
fi

gcloud config set project "${GCP_PROJECT_ID}" >/dev/null 2>&1

if [ "$GH_AVAILABLE" = true ] && [ -n "$GITHUB_ORG" ] && [ -n "$GITHUB_REPO" ]; then
  gh repo set-default "${GITHUB_ORG}/${GITHUB_REPO}" >/dev/null 2>&1 || true
fi

GCLOUD_CONFIG=$(gcloud config list 2> /dev/null)

cat << EOF

----------------------------------------
-------- GOOGLE CLOUD CONFIGURED -------
----------------------------------------

${GCLOUD_CONFIG}

----------------------------------------
----- GITHUB ACTIONS ENV KEY/VALUE -----
----------------------------------------

GITHUB_ORG:            ${GITHUB_ORG}
GITHUB_REPO:           ${GITHUB_REPO}
GCP_SA_GITHUB_ACTIONS: ${GCP_SA_GITHUB_ACTIONS}
GCP_PROJECT_ID:        ${GCP_PROJECT_ID}
GCP_LOCATION:          ${GCP_LOCATION}

EOF

cat << EOF > .env
GITHUB_ORG="${GITHUB_ORG}"
GITHUB_REPO="${GITHUB_REPO}"
GCP_SA_GITHUB_ACTIONS="${GCP_SA_GITHUB_ACTIONS}"
GCP_PROJECT_ID="${GCP_PROJECT_ID}"
GCP_LOCATION="${GCP_LOCATION}"
EOF

echo "Environment configuration completed and written to .env"
