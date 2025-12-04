from google.adk import Agent

import janitor.schemas as schemas
import janitor.settings as settings
import janitor.tools as tools


resource_scanner_agent = Agent(
    name="resource_scanner_agent",
    model=settings.GEMINI_MODEL,
    instruction="""
    You are a Cloud Resource Scanner. 
    Return *all* resources.
    When you retrieve the list of virtual machines using get_compute_instances_list, save the result to session.state["resources"] using the VMInstanceList schema format.
    """,
    tools=[tools.get_compute_instances_list],
    output_schema=schemas.VMInstanceList,
)

# The root_agent is the entry point for the user query.
root_agent = resource_scanner_agent
