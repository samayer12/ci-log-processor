import argparse
from ghapi.all import GhApi
from datetime import datetime
import os
from pathlib import Path

def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=f"Download logs from a GitHub Actions workflow."
    )
    parser.add_argument("-r", "--repo", required=True, help=f"Repository in owner/repo format")
    parser.add_argument("-w", "--workflow", required=True, help=f"Workflow name")
    parser.add_argument("-d", "--days", type=int, default=7, help=f"Days to look back (default: 7)")
    parser.add_argument("-o", "--output", default="logs", help=f"Output directory (default: logs)")
    parser.add_argument("-p", "--page-size", default=100, help=f"Set page size. Pagination is currently unsupported.")
    return parser.parse_args()

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
            # print(f"Workflow details: {workflow_details}")
            return workflow.get('id')
    
    print(f"No workflow found with name: {workflow_name}")
    return None

def get_run_ids(workflow_id: int):
    """
    Get the run IDs for a specific workflow.
    
    Args:
        workflow_id (int): ID of the workflow
    
    Returns:
        list: List of run IDs
    """
    # TODO: Pagination & long history requests
    runs = api.actions.list_workflow_runs(workflow_id, per_page=args.page_size)
    print(f"There are {len(runs['workflow_runs'])} runs on the first page (no pagination)")
    run_subset = [{"id": run['id'], "status": run['status'], "conclusion": run['conclusion'], "created_at": run['created_at']} for run in runs['workflow_runs']]
    run_subset = filter_by_date(run_subset, args.days)
    print(f"There are {len(run_subset)} runs that happened within the past {args.days} days")
    return run_subset


def filter_by_date(runs, days):
    """Filter runs by date.
    
    Args:
        runs (list): List of workflow runs
        days (int): Number of days to look back
        
    Returns:
        list: Filtered list of runs
    """
    return [run for run in runs if (datetime.now() - datetime.strptime(run['created_at'], f'%Y-%m-%dT%H:%M:%SZ')).days <= days]

def get_jobs_for_workflow_run(run_id: int):
    run_dir = Path("logs") / f"run-{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"Fetching jobs for run ID: {run_id}...")

    # TODO: Should be used iteratively in main loop
    jobs = api.actions.list_jobs_for_workflow_run(run_id)
    return [{"id": job['id'], "name": job['name']} for job in jobs['jobs']]

def get_logs_for_job(job_id: int, job_name: str, parent_run_id: int):
    """
    Download logs for a specific job using GitHub CLI.
    
    Args:
        job_id (int): The job ID
        job_name (str): The name of the job
        parent_run_id (int): The parent run ID
    """

    run_dir = Path(args.output) / f"run-{parent_run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    output_path = run_dir / f"{job_id}-{job_name}.log"
    
    try:
        import subprocess
        repo = args.repo
        cmd = [
            "gh", "api",
            "-H", f"Accept: application/vnd.github+json",
            "-H", f"X-GitHub-Api-Version: 2022-11-28",
            f"repos/{repo}/actions/jobs/{job_id}/logs"
        ]
        
        with output_path.open("wb") as f:
            result = subprocess.run(cmd, stdout=f, check=True)
        
        print(f"Log saved to: {output_path}")
        return output_path
    except subprocess.CalledProcessError as e:
        print(f"Error downloading log for job {job_id}: {e}")
        return None

if __name__ == "__main__":
    args = parse_arguments()
    
    # Create output directory
    Path(args.output).mkdir(parents=True, exist_ok=True)
    
    # WARNING: API token should be stored securely, not in source code
    github_token = os.environ["GITHUB_TOKEN"]
    
    owner, repo_name = args.repo.split("/")
    api = GhApi(owner=owner, repo=repo_name, token=github_token)
    
    all_workflows = api.actions.list_repo_workflows()
    
    # Find workflow ID by name
    workflow_name = args.workflow
    workflow_id = find_workflow_id_by_name(all_workflows, workflow_name)

    runs = get_run_ids(workflow_id)
    for run in runs:
        jobs = get_jobs_for_workflow_run(run['id'])
        for job in jobs:
            get_logs_for_job(job['id'], job['name'], run['id'])
