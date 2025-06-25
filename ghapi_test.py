from ghapi.all import GhApi
import os

def find_workflow_id_by_name(workflows_data, workflow_name):
    """
    Extract the ID of a workflow that matches the given name.
    
    Args:
        workflows_data (dict): The JSON response containing workflow data
        workflow_name (str): Name of the workflow to find
    
    Returns:
        int or None: The ID of the workflow if found, None otherwise
    """
    if 'workflows' not in workflows_data:
        return None
    
    for workflow in workflows_data['workflows']:
        if workflow.get('name') == workflow_name:
            workflow_id = workflow.get('id')
            print(f"Found workflow '{workflow_name}' with ID: {workflow_id}")
            
            workflow_details = api.actions.get_workflow(workflow_id)
            print(f"Workflow details: {workflow_details}")
            return workflow.get('id')
    
    print(f"No workflow found with name: {workflow_name}")
    return None

if __name__ == "__main__":
    # WARNING: API token should be stored securely, not in source code
    github_token = os.environ["GITHUB_TOKEN"]
    
    api = GhApi(owner="defenseunicorns", repo="pepr", token=github_token)
    
    all_workflows = api.actions.list_repo_workflows()
    
    # Find workflow ID by name
    workflow_name = "E2E - Pepr Excellent Examples"
    workflow_id = find_workflow_id_by_name(all_workflows, workflow_name)
