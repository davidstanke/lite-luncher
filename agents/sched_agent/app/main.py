import os
import json
import datetime
import uvicorn
from dotenv import load_dotenv

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
CATERING_FILE = os.path.join(DATA_DIR, "catering_options.json")
BOOKINGS_FILE = os.path.join(DATA_DIR, "booked_meetings.json")

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

def get_catering_options() -> list[dict]:
    """Loads and returns the available catering and local restaurant options.

    Includes restaurant name, cuisine type, rating, and dietary tags (e.g., Gluten-Free, Vegetarian, Vegan, Halal).
    """
    print("[Scheduling Agent] Fetching catering options...")
    try:
        if os.path.exists(CATERING_FILE):
            with open(CATERING_FILE, "r") as f:
                return json.load(f)
        return []
    except Exception as e:
        print(f"[Scheduling Agent] Error reading {CATERING_FILE}: {e}")
        return []

def book_meeting(time_slot: str, restaurant: str, reason: str = "") -> str:
    """Appends a new meeting booking to the central system to finalize a slot and catering choice.

    Args:
        time_slot: The day and time range of the confirmed meeting, e.g., "Monday 10:00-11:00".
        restaurant: The name of the selected restaurant for catering, e.g., "Fiesta Tacos".
        reason: Optional brief reason/summary for selecting this choice.
    """
    print(f"[Scheduling Agent] Finalizing booking: {time_slot} with catering from {restaurant}...")
    try:
        bookings = []
        if os.path.exists(BOOKINGS_FILE):
            with open(BOOKINGS_FILE, "r") as f:
                try:
                    bookings = json.load(f)
                except json.JSONDecodeError:
                    bookings = []

        new_booking = {
            "booking_id": f"bk_{int(datetime.datetime.now().timestamp())}",
            "time_slot": time_slot,
            "catering_restaurant": restaurant,
            "reason": reason,
            "booked_at": datetime.datetime.now().isoformat()
        }
        bookings.append(new_booking)

        with open(BOOKINGS_FILE, "w") as f:
            json.dump(bookings, f, indent=2)

        return f"Successfully booked! Meeting scheduled for {time_slot} with catering from {restaurant}. Booking ID: {new_booking['booking_id']}."
    except Exception as e:
        return f"Failed to book meeting: {str(e)}"

def update_team_member_preferences(
    name: str, 
    preferred_time_of_day: str = None, 
    dietary_restrictions: list[str] = None, 
    cuisine_preferences: list[str] = None
) -> str:
    """Updates a team member's preferred meeting times and food preferences in the central registry.
    
    This acts as the agent's central long-term memory, ensuring the updated preferences 
    persist and are automatically applied to all future meeting scheduling requests.

    Args:
        name: Name of the team member to update (e.g. "Alice", "Bob").
        preferred_time_of_day: New preferred meeting time window (e.g., "morning", "afternoon").
        dietary_restrictions: Updated list of dietary restrictions (e.g., ["Vegan", "Gluten-Free"]).
        cuisine_preferences: Updated list of preferred cuisines (e.g., ["Mexican", "Asian"]).
    """
    print(f"[Scheduling Agent] Updating long-term preferences database for team member: {name}...")
    try:
        members = get_team_members()
        updated = False
        for member in members:
            if member["name"].strip().lower() == name.strip().lower():
                if preferred_time_of_day is not None:
                    member["preferred_time_of_day"] = preferred_time_of_day
                if dietary_restrictions is not None:
                    member["dietary_restrictions"] = dietary_restrictions
                if cuisine_preferences is not None:
                    member["cuisine_preferences"] = cuisine_preferences
                updated = True
                break

        if not updated:
            return f"Team member '{name}' not found in the database. No updates made."

        with open(MEMBERS_FILE, "w") as f:
            json.dump(members, f, indent=2)

        return f"Successfully updated central database preferences for {name}. These preferences are now saved permanently in long-term memory."
    except Exception as e:
        return f"Failed to update team member preferences: {str(e)}"


from google.adk.models import Gemini

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
    description="Helps coordinate meeting times and catering food preferences across team members interactively.",
    instruction=(
        "You are the Meeting and Catering Coordinator Agent. Your job is to help coordinate a meeting "
        "time and a catering restaurant for the team.\n\n"
        "Your available tools:\n"
        "1. 'get_team_members' - Loads profiles, timezone, availability, dietary restrictions, and cuisine preferences.\n"
        "2. 'get_catering_options' - Loads available catering restaurants, cuisines, dietary compatibility, and ratings.\n"
        "3. 'book_meeting' - Finalizes and records the booked meeting when the user confirms.\n"
        "4. 'update_team_member_preferences' - Permanently updates a member's preferences/dietary constraints in the database.\n\n"
        "CRITICAL BEHAVIOR RULES:\n"
        "- STEP 1: Always load the team members and catering options using 'get_team_members' and 'get_catering_options' on your first turn.\n"
        "- STEP 2: Find overlapping weekly availabilities among all members and cross-reference them with catering options that respect "
        "everyone's dietary restrictions and align with their cuisine preferences. (e.g., Alice is Vegetarian and Charlie is Gluten-Free, "
        "so the selected restaurant must accommodate both, and ideally match their cuisine interests).\n"
        "- STEP 3 (INTERACTIVE PROPOSING): You must propose EXACTLY ONE optimal recommendation first. Keep it simple, clear, and "
        "conversational. Do NOT dump all possible options or overload the user. Ask clearly for confirmation (e.g., 'Does Monday 10:00-11:00 AM "
        "with Fiesta Tacos work for the team?').\n"
        "- STEP 4 (BOOKING EXECUTION): Only call 'book_meeting' after the user explicitly accepts your proposal. Never auto-book without consent.\n"
        "- STEP 5 (REJECTION & ALTERNATIVES): If the user rejects your proposal, search your database for the next best slot or restaurant, "
        "and present that as the next single recommendation.\n"
        "- STEP 6 (MEMORY WRITING): If the user mentions a shift in general/permanent preferences (e.g., 'Alice is vegan now', or 'Bob doesn't like Mexican "
        "anymore'), you MUST call 'update_team_member_preferences' immediately to record it. Then recalculate your recommendations based "
        "on this updated central database."
    ),
    tools=[
        get_team_members,
        get_catering_options,
        book_meeting,
        update_team_member_preferences
    ],
)

# Convert to A2A-compliant FastAPI application
port = int(os.getenv("PORT", 8081))
a2a_app = to_a2a(scheduling_agent, port=port)

if __name__ == "__main__":
    print(f"[Scheduling Agent] Starting Meeting Scheduling A2A Agent server on port {port}...")
    uvicorn.run(a2a_app, host="0.0.0.0", port=port)
