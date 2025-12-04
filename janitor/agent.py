from google.adk import Agent
from google.adk.agents import SequentialAgent
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool import StreamableHTTPConnectionParams


import janitor.schemas as schemas
import janitor.settings as settings
import janitor.tools as tools


resource_scanner_agent = Agent(
    name="resource_scanner_agent",
    model=settings.GEMINI_MODEL,
    instruction="""
    You are a Cloud Resource Scanner. 
    Return *all* resources.
    """,
    tools=[tools.get_compute_instances_list],
    output_schema=schemas.VMInstanceList,
    output_key="resources",
)

resource_labeler_agent = Agent(
    name="resource_labeler_agent",
    model=settings.GEMINI_MODEL,
    instruction="""
    You are a Cloud Resource Labeler. 
    Please lavel as 'janitor-scheduled' with the value set to 7 days in the future to the idle instances. Do not add the label 'janitor-scheduled' if already added to the instance
    """,
    tools=[
        tools.get_current_date,
        tools.add_days_to_date,
         McpToolset(
            connection_params=StreamableHTTPConnectionParams(url="http://127.0.0.1:8080")
        )
    ],
    output_schema=schemas.VMInstanceList,
    output_key="resources",
)

resource_cleaner_agent = Agent(
    name="resource_cleaner_agent",
    model=settings.GEMINI_MODEL,
    instruction="""
    You are a Cloud Resource cleaner. 
    Please stop all instances with label 'janitor-scheduled'
    """,
    tools=[
         McpToolset(
            connection_params=StreamableHTTPConnectionParams(url="http://127.0.0.1:8081")
        )
    ],
    output_schema=schemas.VMInstanceList,
    output_key="resources",
)

resource_monitor_agent = Agent(
    name="resource_monitor_agent",
    model=settings.GEMINI_MODEL,
    instruction="""
    You are a Cloud Resource Monitor. Filter the list of VMs from state variable named resources to identify idle VMs. 
    Store the result in a new state variable with key idle_resources.
    
    CRITICAL STEPS - Follow these exactly:
    
    1. First, call get_VMs_from_state with key "resources" to retrieve all VM instances.
    
    2. Separate the instances into two groups:
       - TERMINATED instances: These are automatically idle. Add them to the idle list.
       - RUNNING instances: These need CPU/network analysis.
    
    3. For ALL RUNNING instances, you MUST call get_compute_instance_stats:
       - Create a list of strings in format "project_id/zone/instance_name" for all RUNNING instances
       - Call get_compute_instance_stats with this list
       - The tool returns statistics with cpu_utilization (0-1 scale, where 1 = 100%), received_bytes, and sent_bytes
    
    4. Analyze the statistics for each RUNNING instance:
       - An instance is IDLE if cpu_utilization is very low (less than 0.01 or near 0) AND network activity is minimal
       - If cpu_utilization is above 0.01 or there's significant network activity, the instance is NOT idle
    
    5. After identifying all idle VMs (TERMINATED + low-usage RUNNING), call write_VMs_in_state:
       - Key: "idle_resources"
       - Value: A dictionary with "vm_instances" key containing a list of idle VM dictionaries
       - Each VM dict must have: project_id, name, zone, status, machine_type
    
    IMPORTANT: You must call get_compute_instance_stats for ALL RUNNING instances before making any decisions.
    Do not skip this step. The tool requires format "project_id/zone/instance_name".
    """,
    tools=[tools.get_VMs_from_state, tools.write_VMs_in_state, tools.get_compute_instance_stats],
)


orchestrator_agent = SequentialAgent(
    name="orchestrator_agent",
    sub_agents=[resource_scanner_agent, resource_monitor_agent, resource_labeler_agent, resource_cleaner_agent],
)

# The root_agent is the entry point for the user query.
root_agent = orchestrator_agent
