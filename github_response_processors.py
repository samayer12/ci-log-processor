import logging
from typing import Dict,  Optional, Any

def find_workflow_id_by_name(workflows_data: Dict[str, Any], workflow_name: str) -> Optional[int]:
    """
    Extract the ID of a workflow that matches the given name.
    
    Args:
        workflows_data (dict): The JSON response containing workflow data
        workflow_name (str): Name of the workflow to find
    
    Returns:
        int or None: The ID of the workflow if found, None otherwise
    """
    if 'workflows' not in workflows_data:
        logging.error("Invalid workflow data: 'workflows' key not found")
        return None
    
    for workflow in workflows_data['workflows']:
        if workflow.get('name') == workflow_name:
            workflow_id = workflow.get('id')
            logging.info(f"Found workflow '{workflow_name}' with ID: {workflow_id}")
            return workflow.get('id')
    
    logging.warning(f"No workflow found with name: {workflow_name}")
    return None

