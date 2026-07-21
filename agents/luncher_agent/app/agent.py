import os
from dotenv import load_dotenv
import google.auth
from google.auth.transport.requests import Request
from google.adk.agents import Agent
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.tools import AgentTool, McpToolset, FunctionTool, load_memory, ToolContext
from google.adk.tools.mcp_tool import StreamableHTTPConnectionParams
from google.adk.memory.memory_entry import MemoryEntry
from google.genai.types import Content, Part

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


async def save_food_preference(preference: str, tool_context: ToolContext) -> str:
    """Saves a team member's food preference or allergy to the memory store.

    Args:
        preference: The food preference statement to save (e.g., 'Alice is allergic to dairy').
    """
    content = Content(parts=[Part(text=preference)], role="user")
    try:
        entry = MemoryEntry(content=content)
        await tool_context.add_memory(memories=[entry])
    except NotImplementedError:
        from google.adk.events import Event
        event = Event(content=content, author="user")
        await tool_context.add_events_to_memory(events=[event])
    return f"Saved food preference: {preference}"

save_food_preference_tool = FunctionTool(save_food_preference)


# Define the central Luncher Orchestrator
luncher_agent = Agent(
    model="gemini-3.6-flash",
    name="luncher_agent",
    description="The centralized Luncher Orchestrator that coordinates strategy-aligned team lunch meetings.",
    instruction=(       
        """
        You are the central Luncher Orchestrator Agent. Your job is to act as the primary user-facing frontend
        to coordinate strategy-aligned team lunch meetings.

        ROUTING AND PREFERENCE SAVING PROTOCOL:
        - If the user prompt is a user preference (e.g., "Alice is allergic to dairy" or "Bob dislikes spicy food"), call the `save_food_preference` tool to save it to memory, then dynamically thank the user and confirm the saved preference. Do NOT perform any scheduling, meeting coordination, or menu queries in this case.

        COORDINATION & CATERING PIPELINE (EXECUTE IN EXACTLY 4 SEQUENTIAL STEPS):
        - If the user request is a scheduling request, follow this exact linear execution pipeline. In each step, output a very brief (1 line) emoji-prefixed status message BEFORE calling the tool:
          STEP 1: Output "📅 Checking team member availability..." and call `scheduling_agent` EXACTLY ONCE to determine the meeting time and attendee list.
          STEP 2: Output "🥗 Fetching saved dietary preferences..." and call `load_memory` EXACTLY ONCE with a consolidated query (e.g. query: "food preferences and dietary restrictions") to fetch all team member preferences in a single call.
          STEP 3: Output "🍽️ Searching and filtering catering menu options..." and call `execute_sql` EXACTLY ONCE on BigQuery table [CATERING_MENU_TABLE]. Use SQL WHERE clauses based on the dietary preferences retrieved in Step 2 to directly filter out unsuitable menu items.
          STEP 4: Synthesize the schedule and 3 distinct tailored menu options (main, 1-2 sides, drinks, dessert) with pricing breakdowns into a single final response.

        CRITICAL EFFICIENCY & ANTI-REINVOCATION RULES:
        - Do NOT invoke `scheduling_agent`, `load_memory`, or `execute_sql` more than once per user request.
        - Do NOT perform N separate `load_memory` queries for each individual attendee; fetch all preferences in 1 query in Step 2.
        - Do NOT execute exploratory SQL queries; issue exactly 1 filtered SQL query in Step 3.
        - At the end of the scheduling response:
          - List the team members who are included in the meeting.
          - Indicate any food preferences that were used to inform menu choices (e.g., "Food preferences considered: Alice (dairy allergy)").
          - Inform the user that they can specify team member food preferences at any time, in a format like "<PERSON> is allergic to dairy." (where <PERSON> is a random choice from the team members at this meeting)
        """
        f"[CATERING_MENU_TABLE] = {CATERING_MENU_TABLE}"
    ),
    tools=[
        AgentTool(scheduling_agent_connector),
        bigquery_mcp_toolset,
        save_food_preference_tool,
        load_memory,
    ]
)

root_agent = luncher_agent

from google.adk.apps import App

app = App(root_agent=root_agent, name="app")
