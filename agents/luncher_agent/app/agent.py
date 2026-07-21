import os
from dotenv import load_dotenv
import google.auth
from google.auth.transport.requests import Request
from google.adk.agents import Agent
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.tools import AgentTool, McpToolset
from google.adk.tools.mcp_tool import StreamableHTTPConnectionParams

# Load environment variables
load_dotenv()

# Retrieve remote agent URLs, defaulting to standard local dev ports
SCHED_AGENT_URL = os.getenv("SCHED_AGENT_URL", "http://localhost:8081")
BIGQUERY_MCP_URL = os.getenv("BIGQUERY_MCP_URL", "https://bigquery.googleapis.com/mcp")
CATERING_MENU_TABLE = os.getenv("CATERING_MENU_TABLE", "luncher-davidstanke.catering.menu-items")

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


# Auth for connecting to BQ MCP
def get_auth_header(context=None) -> dict[str, str]:
    """Retrieves standard Google Cloud Application Default Credentials."""
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/bigquery"]
    )
    # Refresh token if necessary
    auth_req = Request()
    credentials.refresh(auth_req)
    return {
        "Authorization": f"Bearer {credentials.token}",
        "x-goog-user-project": "luncher-davidstanke"  # Required for BigQuery quota/billing
    }


# Instantiate BigQuery MCP toolset with HTTP transport and Auth Headers
bigquery_mcp_toolset = McpToolset(
    connection_params=StreamableHTTPConnectionParams(
        url=BIGQUERY_MCP_URL,
        timeout=15.0,
        sse_read_timeout=15.0
    ),
    tool_filter=["execute_sql"],
    header_provider=get_auth_header
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
        "1. `scheduling_agent` - Use this to manage team schedules, check/update availability preferences, and finalize bookings.\n"
        "2. `execute_sql` - Use this tool to query catering menu items from BigQuery.\n\n"
        
        "COORDINATION & CATERING PROTOCOL:\n"
        f"- As part of your default flow, query the catering menu items from BigQuery table `{CATERING_MENU_TABLE}` using tool `execute_sql`.\n"
        "- Propose 3 distinct menu options (containing a main, 1-2 sides, drinks, and dessert) to serve at the event, matching any dietary restrictions specified by the user.\n"
        "- Include pricing details and breakdown for each proposed menu option.\n"
        "- Delegate to the scheduling_agent to identify the optimal overlapping time slot for the team based on those priorities.\n"
        "- The scheduling_agent returns a structured JSON response containing the proposals with the first names of the participants who are part of the meeting (those who have overlapping availability).\n"
        "- Parse this structured JSON and ensure your final response lists the first names of the people who are part of the meeting alongside the proposed time and catering menu.\n"
        "- Synthesize the schedule and catering menu proposals into a single cohesive response.\n"
    ),
    tools=[AgentTool(scheduling_agent_connector), bigquery_mcp_toolset]
)

root_agent = luncher_agent

from google.adk.apps import App

app = App(root_agent=root_agent, name="app")
