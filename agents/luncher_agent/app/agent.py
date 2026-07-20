import os
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.tools import AgentTool

# Load environment variables
load_dotenv()

# Retrieve remote agent URLs, defaulting to standard local dev ports
SCHED_AGENT_URL = os.getenv("SCHED_AGENT_URL", "http://localhost:8081")

def get_agent_card_url(base_url: str) -> str:
    if "v1/card" in base_url or base_url.endswith(".json"):
        return base_url
    return f"{base_url.rstrip('/')}/.well-known/agent-card.json"

# Instantiate A2A connectors to the specialized sub-agents
scheduling_agent_connector = RemoteA2aAgent(
    name="scheduling_agent",
    description="Interactively schedules team meetings and coordinates team member availability.",
    agent_card=get_agent_card_url(SCHED_AGENT_URL)
)

# Define the central Luncher Orchestrator
luncher_agent = Agent(
    model="gemini-2.5-flash",
    name="luncher_agent",
    description="The centralized Luncher Orchestrator that coordinates strategy-aligned team lunch meetings.",
    instruction=(
        "You are the central Luncher Orchestrator Agent. Your job is to act as the primary user-facing frontend "
        "to schedule team lunches that are strategically aligned with corporate priorities.\n\n"
        
        "Your available tools:\n"
        "1. 'scheduling_agent' - Use this to manage team schedules, check/update availability preferences, and finalize bookings.\n\n"
        
        "COORDINATION PROTOCOL:\n"
        "- Delegate to the scheduling_agent to identify the optimal overlapping time slot for the team based on those priorities.\n"
        "- Synthesize the information into a single cohesive response.\n"
    ),
    tools=[AgentTool(scheduling_agent_connector)]
)

root_agent = luncher_agent

from google.adk.apps import App

app = App(root_agent=root_agent, name="app")
