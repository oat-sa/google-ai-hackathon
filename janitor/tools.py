import os
import statistics

from datetime import datetime, timedelta, timezone

from google.cloud import compute_v1
from google.cloud import monitoring_v3
from google.adk.tools import ToolContext

import janitor.schemas as schemas

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")


def get_compute_instances_list() -> list[dict]:
    """Retrieves a list of all Virtual Machine instances in the project.

    Returns:
        A list of dictionaries, where each dictionary represents a VM instance. The following keys are present:
           - project_id: The ID of the project where the VM is located.
           - name: The name of the VM.
           - zone: The Compute Engine zone where the VM is located (e.g. us-central1-a)
           - machine_type: The type of machine (e.g. n1-standard-1)
           - status: The current status of the VM (e.g. RUNNING, TERMINATED)
    """
    client = compute_v1.InstancesClient()
    resp = client.aggregated_list(project=PROJECT_ID)
    instances = []
    for zone, response in resp:
        if response.instances:
            for instance in response.instances:
                instances.append(
                    {
                        "project_id": PROJECT_ID,
                        "name": instance.name,
                        "zone": zone.split("/")[-1],
                        "machine_type": instance.machine_type.split("/")[-1],
                        "status": instance.status,
                    }
                )
    return instances


def get_compute_instance_stats(instances: list[str]) -> list[dict]:
    """Retrieves statistics for all the given Virtual Machine instances.

    Args:
        instances (list[str]): A list of instance names in the format project_id/zone/instance_name.

    Returns:
        A list of dictionaries, where each dictionary represents a VM instance. The following keys are present:
           - name: The name of the VM.
           - cpu_utilization: The average CPU utilization of the VM over the last week, 1 is 100%.
           - received_bytes: The average number of bytes received by the VM over the last week.
           - sent_bytes: The average number of bytes sent by the VM over the last week.
    """
    client = monitoring_v3.MetricServiceClient()

    # Statistics to collect
    metric_types = {
        "compute.googleapis.com/instance/cpu/utilization": "cpu_utilization",
        "compute.googleapis.com/instance/network/received_bytes_count": "received_bytes",
        "compute.googleapis.com/instance/network/sent_bytes_count": "sent_bytes",
    }

    period = 600  # seconds (we're looking at last 10 minutes for this exercise, but this should a whole week or more)

    # Define the time interval for the metric
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(seconds=period)

    # Create the time series query
    interval = monitoring_v3.TimeInterval(start_time=start_time, end_time=end_time)

    # Define the aggregation, we're getting the average utilization for metric interval
    aggregation = monitoring_v3.Aggregation(
        alignment_period={"seconds": period},
        per_series_aligner=monitoring_v3.Aggregation.Aligner.ALIGN_MEAN,
    )

    stats = {}

    for instance in instances:
        project_id, zone, instance_name = instance.split("/")

        for metric_type, key_name in metric_types.items():
            filter_str = f"""
                metric.type="{metric_type}" AND 
                metric.labels.instance_name="{instance_name}" AND
                resource.type="gce_instance" AND
                resource.labels.project_id="{project_id}" AND 
                resource.labels.zone="{zone}"
            """
            request = monitoring_v3.ListTimeSeriesRequest(
                name=f"projects/{project_id}",
                filter=filter_str,
                interval=interval,
                view=monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
                aggregation=aggregation,
            )

            results = client.list_time_series(request)

            for result in results:
                instance_name = result.metric.labels["instance_name"]
                if instance_name not in stats:
                    stats[instance_name] = {
                        "name": instance_name,
                        "cpu_utilization": 0,
                        "received_bytes": 0,
                        "sent_bytes": 0,
                    }

                points = [p.value.double_value for p in result.points]
                if points:
                    stats[instance_name][key_name] = statistics.mean(points)

    return list(stats.values())


def get_current_date() -> str:
    """Returns the current date in YYYY-MM-DD format.

    Returns:
        str: The current date in YYYY-MM-DD format.
    """
    return datetime.today().strftime("%Y-%m-%d")


def add_days_to_date(current_date: str, days: int) -> str:
    """Adds/subtracts the specified number of days to the given date.

    Args:
        current_date (str): The current date in YYYY-MM-DD format.
        days (int): The number of days to add/subtract.

    Returns:
        str: The new date in YYYY-MM-DD format.
    """
    new_date_obj = datetime.strptime(current_date, "%Y-%m-%d") + timedelta(days=days)
    return new_date_obj.strftime("%Y-%m-%d")


def get_VMs_from_state(key: str, tool_context: ToolContext):
    """Gets the current list of VMs stored in state.
    
    Args:
        key: The state key to retrieve (e.g., "resources")
        tool_context: The tool context providing access to session state
    
    Returns:
        The VMInstanceList from state, or None if not found
    """
    state = tool_context.state
    return state.get(key, None)


def write_VMs_in_state(key: str, value: dict, tool_context: ToolContext):
    """Writes the list of VMs in the state memory.
    
    Args:
        key: The state key to write to (e.g., "idle_resources")
        value: A dictionary representing VMInstanceList with "vm_instances" key containing a list of VM instances
        tool_context: The tool context providing access to session state
    
    Returns:
        The VMInstanceList object that was written
    """
    # Convert dict to VMInstanceList schema
    vm_list = schemas.VMInstanceList.model_validate(value)
    tool_context.state[key] = vm_list
    tool_context.actions.skip_summarization = True
    return vm_list
