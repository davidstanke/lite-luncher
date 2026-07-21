import os
import json
import uvicorn
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from google.adk.models import Gemini

from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.a2a.utils.agent_to_a2a import to_a2a

class MeetingProposal(BaseModel):
    timeslot: str = Field(description="The proposed meeting day and time slot.")
    participants: list[str] = Field(description="The first names of the team members who have overlapping availability for this slot.")

class SchedulingResponse(BaseModel):
    proposals: list[MeetingProposal] = Field(description="List of one or more meeting proposals.")

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


def compute_overlaps() -> str:
    """Calculates overlapping weekly availability slots from team_members.json."""
    if not os.path.exists(MEMBERS_FILE):
        return "No team members data available."
    
    try:
        with open(MEMBERS_FILE, "r") as f:
            members = json.load(f)
    except Exception as e:
        return f"Error reading team members: {e}"
        
    def parse_time(t_str):
        h, m = map(int, t_str.split(":"))
        return h * 60 + m

    def format_time(minutes):
        h = minutes // 60
        m = minutes % 60
        return f"{h:02d}:{m:02d}"

    from collections import defaultdict
    day_intervals = defaultdict(list)

    for m in members:
        name = m.get("name", "")
        avail = m.get("weekly_availability", {})
        for day, intervals in avail.items():
            for iv in intervals:
                try:
                    start_str, end_str = iv.split("-")
                    start = parse_time(start_str)
                    end = parse_time(end_str)
                    day_intervals[day].append((start, end, name))
                except Exception:
                    continue

    all_overlaps = []
    days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    for day in days_order:
        events = day_intervals[day]
        if not events:
            continue
        # Gather all unique start/end time points
        points = sorted(list(set([t for start, end, name in events for t in (start, end)])))
        intervals_overlap = []
        for i in range(len(points) - 1):
            s = points[i]
            e = points[i+1]
            avail_members = []
            for start, end, name in events:
                if start <= s and e <= end:
                    avail_members.append(name)
            if avail_members:
                intervals_overlap.append((s, e, avail_members))
        
        # Merge consecutive intervals with the same group of members
        merged = []
        for s, e, members_list in sorted(intervals_overlap):
            m_list_sorted = sorted(members_list)
            if merged and merged[-1][2] == m_list_sorted and merged[-1][1] == s:
                merged[-1] = (merged[-1][0], e, merged[-1][2])
            else:
                merged.append((s, e, m_list_sorted))
        
        for s, e, m_list in merged:
            all_overlaps.append({
                "day": day,
                "start": s,
                "end": e,
                "formatted": f"{day} {format_time(s)}-{format_time(e)}",
                "participants": m_list,
                "count": len(m_list)
            })

    # Sort all overlaps across all days by count descending, then by day order, then by start time
    day_index = {d: i for i, d in enumerate(days_order)}
    all_overlaps.sort(key=lambda x: (-x["count"], day_index[x["day"]], x["start"]))

    # Format as a clean text list
    lines = []
    for o in all_overlaps:
        names_str = ", ".join(o["participants"])
        lines.append(f"- {o['formatted']}: {o['count']} participants ({names_str})")
        
    return "\n".join(lines)


async def load_overlaps_callback(callback_context: CallbackContext) -> None:
    """Pre-calculates weekly availability overlaps and injects them into agent state."""
    overlaps_text = compute_overlaps()
    callback_context.state["overlaps"] = overlaps_text


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
    before_agent_callback=load_overlaps_callback,
    instruction=(
        """You are the Meeting Availability Coordinator Agent. Your job is to find an appropriate
        time for the team based on members' weekly availability.

        The pre-calculated overlapping weekly availabilities among all members are:
        {overlaps}

        CRITICAL BEHAVIOR RULES:
        - STEP 1: Use the pre-calculated overlaps provided in {overlaps} to make recommendations. Do NOT call any tools.
        - STEP 2 (BEST OPTION PROPOSAL): You must propose EXACTLY ONE optimal recommendation first. Include the proposed timeslot and the list of first names of all team members who have overlapping availability for that slot in the structured output.

        - OPTIONAL STEP (ALTERNATIVE PROPOSALS): If you have already made a best option proposal, you may be asked
        for additional possibilities. In this case, propose up to 5 alternative timeslots. For each alternative proposal, include the proposed timeslot and the list of first names of all team members who have overlapping availability for that slot.
        """
    ),
    output_schema=SchedulingResponse,
    tools=[],
)

# Convert to A2A-compliant FastAPI application
port = int(os.getenv("PORT", 8081))
a2a_app = to_a2a(scheduling_agent, port=port)

if __name__ == "__main__":
    print(f"[Scheduling Agent] Starting Meeting Scheduling A2A Agent server on port {port}...")
    uvicorn.run(a2a_app, host="0.0.0.0", port=port)
