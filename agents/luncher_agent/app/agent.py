import os
from dotenv import load_dotenv
import google.auth
from google.auth.transport.requests import Request
from google.adk.agents import Agent
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.tools import AgentTool, McpToolset, FunctionTool, load_memory, ToolContext, BaseTool
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


async def save_favorite_menu(menu_title: str, menu_details: str, tool_context: ToolContext) -> str:
    """Saves a favorite menu option to the memory store.

    Args:
        menu_title: The title or name of the favorite menu option (e.g., 'Taco Tuesday' or 'Option 1 - Mediterranean Delights').
        menu_details: The items included in the menu (main course, sides, drinks, dessert).
    """
    favorite_str = f"Favorite Menu: {menu_title} - {menu_details}"
    content = Content(parts=[Part(text=favorite_str)], role="user")
    try:
        entry = MemoryEntry(content=content)
        await tool_context.add_memory(memories=[entry])
    except NotImplementedError:
        from google.adk.events import Event
        event = Event(content=content, author="user")
        await tool_context.add_events_to_memory(events=[event])
    return f"Saved favorite menu: {menu_title}"

save_favorite_menu_tool = FunctionTool(save_favorite_menu)


# Define the central Luncher Orchestrator
luncher_agent = Agent(
    model="gemini-3.6-flash",
    name="luncher_agent",
    description="The centralized Luncher Orchestrator that coordinates strategy-aligned team lunch meetings.",
    instruction=(
        """
        You are the central Luncher Orchestrator Agent. Your job is to act as the primary user-facing frontend
        to coordinate strategy-aligned team lunch meetings.

        ROUTING AND PREFERENCE / FAVORITE SAVING PROTOCOL:
        - If the user prompt is a user preference (e.g., "Alice is allergic to dairy" or "Bob dislikes spicy food"), call the `save_food_preference` tool to save it to memory, then dynamically thank the user and confirm the saved preference. Do NOT perform any scheduling, meeting coordination, or menu queries in this case.
        - If the user prompt requests saving a favorite menu (e.g., "Save Option 1 as a favorite" or "Save Taco Tuesday as favorite"), call the `save_favorite_menu` tool to save it to memory, then dynamically thank the user and confirm the saved favorite menu. Do NOT perform any scheduling, meeting coordination, or menu queries in this case.

        PROGRESS REPORTING PROTOCOL:
        - Before invoking each tool, output a single line to the user updating them on your status (e.g., "📅 Checking team member availability...", "🥗 Fetching saved dietary preferences...", "⭐ Fetching saved favorite menus...", "🍽️ Searching and filtering catering menu options...", "💾 Saving food preference...", or "💾 Saving favorite menu...").

        COORDINATION & CATERING PIPELINE (EXECUTE IN EXACTLY 5 SEQUENTIAL STEPS):
        - If the user request is a scheduling request, follow this exact linear execution pipeline:
          STEP 1: Call `scheduling_agent` EXACTLY ONCE to determine the meeting time and attendee list.
          STEP 2: Call `load_memory` EXACTLY ONCE with a query for dietary preferences and restrictions (e.g. query: "food preferences and dietary restrictions") to fetch all team member preferences in a single call.
          STEP 3: Call `load_memory` EXACTLY ONCE with a query for saved favorite menus (e.g. query: "favorite menus") to fetch all previously saved favorite menus.
          STEP 4: Call `execute_sql` EXACTLY ONCE on BigQuery table [CATERING_MENU_TABLE]. Use SQL WHERE clauses based on the dietary preferences retrieved in Step 2 to directly filter out unsuitable menu items.
          STEP 5: Synthesize the schedule and 3 distinct tailored menu options (main, 1-2 sides, drinks, dessert) with pricing breakdowns into a single final response.
                  - Evaluate any saved favorite menus retrieved in Step 3 against all meeting attendees' dietary preferences retrieved in Step 2.
                  - If a saved favorite menu is completely compliant with all attendees' dietary constraints, preferentially offer it as one of the 3 menu options and clearly label it as a "[Favorite Menu]".
                  - If a saved favorite menu violates any attendee's dietary constraints, do NOT offer it as a menu option.

        CRITICAL EFFICIENCY & ANTI-REINVOCATION RULES:
        - Do NOT invoke `scheduling_agent` or `execute_sql` more than once per user request. Call `load_memory` exactly twice (once in Step 2 for food preferences, once in Step 3 for favorite menus).
        - Do NOT perform N separate `load_memory` queries for each individual attendee; fetch all preferences in 1 query in Step 2.
        - Do NOT execute exploratory SQL queries; issue exactly 1 filtered SQL query in Step 4.
        - At the end of the scheduling response:
          - List the team members who are included in the meeting.
          - Indicate any food preferences that were used to inform menu choices (e.g., "Food preferences considered: Alice (dairy allergy)").
          - Inform the user that they can specify team member food preferences at any time (e.g., "<PERSON> is allergic to dairy.") or save favorite menus (e.g., "Save Option 1 as a favorite.").
        """
        f"[CATERING_MENU_TABLE] = {CATERING_MENU_TABLE}"
    ),
    tools=[
        AgentTool(scheduling_agent_connector),
        bigquery_mcp_toolset,
        save_food_preference_tool,
        save_favorite_menu_tool,
        load_memory,
    ]
)

root_agent = luncher_agent

from google.adk.apps import App

app = App(root_agent=root_agent, name="app")
