# Luncher Agents
This folder contains ADK agents which implement Luncher functionality:

## 🛰️ Luncher Orchestrator Agent (`luncher_agent`)
The centralized Orchestrator Agent (the cognitive frontend) for the Luncher platform. It coordinates with `sched_agent` (Scheduling Agent) using the Google Agent Development Kit (ADK) and the Agent-to-Agent (A2A) protocol.

## Child tools
The Orchestrator acts as the "cognitive frontend" or user gateway, delegating specialized sub-tasks to the backend agents:
1. **`sched_agent`**: Queried via A2A to perform team schedule checks, manage preferences, and book catering.
(strat_agent is removed from this repo for the moment)
---

## 🚀 Local Development & Execution

To run the orchestrator and downstream agents locally, run the following commands in separate terminals:

### 1. Start Scheduling Agent (Port 8081)
```bash
cd agents/sched_agent
port=8081 uv run app/main.py
```

### 2. Start Orchestrator Agent (Port 8082)
```bash
cd agents/luncher_agent
uv run adk web app --port 8082
```

## 🏗️ Deployment to Cloud Run and Agent Runtime

### Step 1: Deploy `sched_agent`

1. Navigate to the agent directory:
   ```bash
   cd agents/sched_agent
   ```
2. Deploy the agent to Agent Runtime:
   ```bash
   gcloud run deploy sched-agent --project luncher-davidstanke --region us-central1 --source . --memory 4Gi --cpu 1 --min-instances 1 --max-instances 10 --concurrency 8 --allow-unauthenticated --no-cpu-throttling
   ```
### Step 2: Deploy `luncher_agent`
(Uses hard-coded sched_agent URL from Dave's project)

1. Navigate to the agent directory:
   ```bash
   cd agents/luncher_agent
   ```
2. Deploy the orchestrator, passing the A2A endpoints of the deployed `strat_agent` and `sched_agent` (replacing URLs with the proper A2A agent card locations from the prior deployments):
   ```bash
   uv run agents-cli deploy \
     --project luncher-davidstanke \
     --region us-central1 \
     --no-confirm-project \
     --update-env-vars "SCHED_AGENT_URL=https://sched-agent-98226488336.us-central1.run.app/a2a/app/.well-known/agent-card.json"
   ```

## Sample prompts
```
Plan a lunch meeting for all team members. Schedule it for the earliest possible day and order food.
```