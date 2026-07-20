from .main import scheduling_agent

# Expose the scheduling agent as the root agent for ADK discovery
root_agent = scheduling_agent

from google.adk.apps import App

app = App(root_agent=root_agent, name="app")
