import os
import json
import uvicorn
from dotenv import load_dotenv
from google.adk.models import Gemini

from google.adk.agents import Agent
from google.adk.a2a.utils.agent_to_a2a import to_a2a

# Load environment variables
load_dotenv()

current_dir = os.path.dirname(os.path.abspath(__file__))
# Traverse up to find the folder containing data/team_members.json
DATA_DIR = None
for _ in range(5):
    candidate = os.path.join(current_dir, "data")
    if os.path.exists(os.path.join(candidate, "team_members.json")):
        DATA_DIR = candidate
        break
    current_dir = os.path.dirname(current_dir)
else:
    DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

MEMBERS_FILE = os.path.join(DATA_DIR, "team_members.json")


def get_team_members() -> list[dict]:
    """Loads and returns the team members' profiles, schedules, and preferences.

    This lists each member's timezone, weekly availability slots, dietary restrictions,
    and preferred cuisines.
    """
    print("[Scheduling Agent] Fetching team members profiles...")
    try:
        if os.path.exists(MEMBERS_FILE):
            with open(MEMBERS_FILE, "r") as f:
                return json.load(f)
        return []
    except Exception as e:
        print(f"[Scheduling Agent] Error reading {MEMBERS_FILE}: {e}")
        return []


# Use Vertex AI (service authorization) instead of Gemini API (API key)
client_kwargs = {"enterprise": True}
if os.getenv("GOOGLE_CLOUD_PROJECT"):
    client_kwargs["project"] = os.getenv("GOOGLE_CLOUD_PROJECT")
if os.getenv("GOOGLE_CLOUD_LOCATION"):
    client_kwargs["location"] = os.getenv("GOOGLE_CLOUD_LOCATION")


# Define the ADK Agent
scheduling_agent = Agent(
    model=Gemini(
        model="gemini-2.5-flash",
        client_kwargs=client_kwargs
    ),
    name="scheduling_agent",
    description="Helps coordinate meeting times based on team member availability.",
    instruction=(
        """You are the Meeting Availability Coordinator Agent. Your job is to find an appropriate
        time for the team based on members' weekly availability.

        Your available tools:
        1. 'get_team_members' - Loads profiles, timezone, and weekly availability slots.

        CRITICAL BEHAVIOR RULES:
        - STEP 1: Always load the team members using 'get_team_members' on your first turn.
        - STEP 2: Find overlapping weekly availabilities among all members.
        - STEP 3 (BEST OPTION PROPOSAL): You must propose EXACTLY ONE optimal recommendation first. Keep it simple, clear, and
        conversational. Do NOT dump all possible options or overload the user.

        - OPTIONAL STEP (ALTERNATIVE PROPOSALS): If you have already made a best option proposal, you may be asked
        for additional possibilities. In this case, propose up to 5 alternative timeslots. These alternative
        proposals may be suboptimal.
        """
    ),
    tools=[
        get_team_members
    ],
)

# Convert to A2A-compliant FastAPI application
port = int(os.getenv("PORT", 8081))
a2a_app = to_a2a(scheduling_agent, port=port)

if __name__ == "__main__":
    print(f"[Scheduling Agent] Starting Meeting Scheduling A2A Agent server on port {port}...")
    uvicorn.run(a2a_app, host="0.0.0.0", port=port)
