---
name: sanity-checker
description: A workspace skill that runs both credential detection and variable naming checks as specialized, parallel sub-agents, then consolidates their reports into a unified quality and security review artifact. It NEVER makes any changes to the codebase.
---

# Sanity Checker Skill

This skill orchestrates both the `credential-detector` and `variable-naming-checker` skills by running them concurrently as specialized, read-only sub-agents, then consolidating their findings into a single, beautiful Markdown report artifact for the user's review. It does not make any changes to the codebase.

---

## Technical Orchestration Flow

### Step 1: Define the Two Sub-Agents
The agent should define the two sub-agents using the `define_subagent` tool:

#### 1. Credential Detector Sub-Agent
*   **name**: `credential-detector`
*   **description**: `Dedicated agent that scans files for credentials and secrets using regex patterns and reports findings. It NEVER writes any changes.`
*   **system_prompt**:
    ```
    You are a security-focused sub-agent. Your only task is to run the credential scanning script and report any secret findings. You must NEVER write or modify any files under any circumstances; only detect credentials and report back to the root agent.
    
    To scan the files:
    1. Run the scanning script via command:
       `uv run python .agents/skills/credential-detector/scripts/detect_credentials.py`
    2. If the command succeeds (exit code 0), report back that no secrets were found.
    3. If the command fails (exit code 1), parse the output, extract the listed violations (files, line numbers, pattern type, and masked snippets), and report them clearly as errors.
    ```
*   **enable_write_tools**: `true` (required to run shell commands)

#### 2. Variable Naming Checker Sub-Agent
*   **name**: `variable-naming-checker`
*   **description**: `Dedicated agent that scans files for variable naming style mismatches, built-in shadowing, and overly short names, then reports findings. It NEVER writes any changes.`
*   **system_prompt**:
    ```
    You are a code quality focused sub-agent. Your only task is to run the variable naming check script and report any compliance findings. You must NEVER write or modify any files under any circumstances; only detect naming mismatches and report back to the root agent.
    
    To scan the files:
    1. Run the scanning script via command:
       `uv run python .agents/skills/variable-naming-checker/scripts/check_variable_naming.py`
    2. If the command succeeds (exit code 0), report back that all variables are compliant with naming best practices.
    3. If the command fails (exit code 1), parse the output, extract the listed violations (files, line numbers, issue type, non-compliant names, and suggestions), and report them clearly.
    ```
*   **enable_write_tools**: `true` (required to run shell commands)

### Step 2: Invoke Sub-Agents Concurrently
Invoke both sub-agents in a single `invoke_subagent` tool call to execute the scans in parallel:
*   **Subagents**:
    *   `{ "TypeName": "credential-detector", "Role": "Credential Scanner", "Prompt": "Please run the credential scanner script and report any findings or errors." }`
    *   `{ "TypeName": "variable-naming-checker", "Role": "Naming Convention Auditor", "Prompt": "Please run the variable naming checker script and report any findings or errors." }`

### Step 3: Await Results & Consolidate
Once both sub-agents have reported back:
1.  Analyze their outputs.
2.  Create a unified Markdown artifact titled `sanity_check_report.md` under the conversation's artifact directory (`<appDataDir>/brain/<conversation-id>/sanity_check_report.md`).
3.  Include metadata such as the date and time of the run, followed by clean sections for **Secrets & Security** and **Naming & Style Compliance**.
4.  Use GitHub-style alert blocks to highlight critical secret exposures (`> [!CAUTION]`) or style warnings (`> [!NOTE]`).

---

## Expected Artifact Format

Your consolidated artifact should look like this:

```markdown
# Codebase Sanity Check Report

**Timestamp**: 2026-06-25T11:00:00Z  
**Status**: ⚠️ Issues Found / ✅ Passed

---

## 🔒 1. Secrets & Security Scan

> [!CAUTION]
> (If credentials found) CRITICAL: Unmasked credentials or placeholder API keys detected in source code. Please address these immediately before deploying!
> OR
> ✅ No active credentials or secrets found in the tracked workspace files.

| File | Line | Key Type | Match Snippet / Details |
| :--- | :--- | :------- | :---------------------- |
| ...  | ...  | ...      | ...                     |

---

## 🎨 2. Variable Naming & Style Compliance

> [!NOTE]
> (If naming issues found) Style guidelines mismatches and PEP 8 naming suggestions.
> OR
> ✅ All analyzed variables conform to naming convention standards.

| File | Line | Issue Type | Offending Name | Suggestion |
| :--- | :--- | :--------- | :------------- | :--------- |
| ...  | ...  | ...        | ...            | ...        |

---

*Note: You can bypass specific line violations in Python using `# ignore-naming` or `# ignore-credential`, and in JS/TS using `// ignore-naming` or `// ignore-credential`.*
```

### Step 4: Present to the User
After writing the artifact to disk, present a summary to the user pointing them to the generated `sanity_check_report.md` artifact.
