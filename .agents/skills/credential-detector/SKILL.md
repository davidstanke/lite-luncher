---
name: credential-detector
description: A specialized workspace skill to detect API keys, credentials, and secrets in the codebase. Always execute this capability by defining and invoking a dedicated sub-agent that NEVER proposes or writes any changes. It only detects credentials and reports findings.
---

# Credential Detector Skill

This skill allows the agent to scan the repository for sensitive credentials, API keys, private keys, tokens, and placeholders before completing tasks or preparing a deployment. It does not propose any changes to the contents of the repo; it only scans.

## Mandatory Execution Policy: Always Run as Sub-Agent

To maintain security, keep logs clean, and avoid cluttering the parent agent's context, credential scanning **MUST ALWAYS** run as a specialized sub-agent.

### Step 1: Define the Sub-Agent
Define a dedicated sub-agent using the `define_subagent` tool with the following configuration:
*   **name**: `credential-detector`
*   **description**: `Dedicated agent that scans files for credentials and secrets using regex patterns and reports findings. It NEVER writes any changes.`
*   **system_prompt**:
    ```
    You are a security-focused sub-agent. Your only task is to run the credential scanning script and report any secret findings. You must NEVER write or modify any files under any circumstances; only detect credentials and report back to the root agent.
    
    To scan the files:
    1. Run the scanning script via command:
       `uv run python .agents/skills/credential-detector/scripts/detect_credentials.py`
    2. If the command succeeds (exit code 0), report back that no secrets were found.
    3. If the command fails (exit code 1), parse the output, extract the listed violations (files, line numbers, pattern type, and masked snippets), and report them clearly as errors. Do NOT continue with implementation or deployment when secrets are found.
    ```
*   **enable_write_tools**: `true` (required to run shell commands)

### Step 2: Invoke the Sub-Agent
Invoke the sub-agent using the `invoke_subagent` tool:
*   **TypeName**: `credential-detector`
*   **Role**: `Credential Scanner`
*   **Prompt**: `Please run the credential scanner script and report any findings or errors.`

---

## Technical Details

The scanning script runs:
`git ls-files --cached --others --exclude-standard`
to retrieve all repository files (excluding those in `.gitignore`).

### Supported Patterns
*   **Google API Key**: Maps, Places, Gemini, and other GCP API keys (`AIzaSy...`)
*   **GCP Private Key**: Service account JSON credentials and private key blocks
*   **AWS Credentials**: AWS Access Key ID & Secret Access Key
*   **GitHub Token**: GitHub Personal Access Tokens (`ghp_...` or `github_pat_...`)
*   **Slack Webhook**: Incoming Webhook URL endpoints
*   **Stripe Keys**: Stripe secret or restricted keys (`sk_...`, `rk_...`)
*   **Generic Placeholders**: Obvious placeholder strings such as `YOUR_MAPS_API_KEY`, `INSERT_API_KEY_HERE`, etc.

### Safe Bypasses & Exclusions
If a match is detected on a dummy or example file, you can bypass the check for that specific line by adding one of the following comments to the end of the line:
*   `# nosec`
*   `# ignore-credential`

Example:
```python
MAPS_KEY = "AIzaSyD_DUMMY_KEY_FOR_TESTS_123456789" # ignore-credential
```
