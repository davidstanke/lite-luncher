import os
import uvicorn
from dotenv import load_dotenv
from google.adk.a2a.utils.agent_to_a2a import to_a2a

# Load environment variables
load_dotenv()

# We import the root_agent from agent.py
from .agent import root_agent

port = int(os.getenv("PORT", 8082))
a2a_app = to_a2a(root_agent, port=port)

if __name__ == "__main__":
    print(f"[Orchestrator] Starting A2A Orchestrator server on port {port}...")
    uvicorn.run(a2a_app, host="0.0.0.0", port=port)
