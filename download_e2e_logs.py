import argparse
import sys
from ghapi.all import GhApi
from datetime import datetime
import os
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=f"Download logs from a GitHub Actions workflow."
    )
    parser.add_argument("-r", "--repo", required=True, help=f"Repository in owner/repo format")
    parser.add_argument("-w", "--workflow", required=True, help=f"Workflow name")
    parser.add_argument("-d", "--days", type=int, default=7, help=f"Days to look back (default: 7)")
    parser.add_argument("-o", "--output", default="logs", help=f"Output directory (default: logs)")
    parser.add_argument("-p", "--page-size", type=int, default=100, help=f"Set page size. Pagination is currently unsupported.")
    
    args = parser.parse_args()
    
    # Validate repository format
    if '/' not in args.repo:
        parser.error("Repository must be in 'owner/repo' format")
    
    # Validate days argument
    if args.days <= 0:
        parser.error("Days must be a positive integer")
    
    # Validate page size
    if args.page_size <= 0:
        parser.error("Page size must be a positive integer")
    
    return args

def find_workflow_id_by_name(workflows_data, workflow_name, api):
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
            
            workflow_details = api.actions.get_workflow(workflow_id)
            # print(f"Workflow details: {workflow_details}")
            return workflow.get('id')
    
    logging.warning(f"No workflow found with name: {workflow_name}")
    return None

def get_run_ids(workflow_id: int, api, page_size: int, days: int):
    """
    Get the run IDs for a specific workflow.
    
    Args:
        workflow_id (int): ID of the workflow
    
    Returns:
        list: List of run IDs
    """
    try:
        # TODO: Pagination & long history requests
        runs = api.actions.list_workflow_runs(workflow_id, per_page=page_size)
        logging.info(f"There are {len(runs['workflow_runs'])} runs on the first page (no pagination)")
        
        if 'workflow_runs' not in runs:
            logging.error("Invalid response: 'workflow_runs' key not found")
            return []
            
        run_subset = [
            {
                "id": run.get('id'),
                "status": run.get('status'),
                "conclusion": run.get('conclusion'),
                "created_at": run.get('created_at')
            } 
            for run in runs['workflow_runs'] 
            if run.get('id') and run.get('created_at')  # Skip runs with missing required data
        ]
        
        run_subset = filter_by_date(run_subset, days)
        logging.info(f"There are {len(run_subset)} runs that happened within the past {days} days")
    except Exception as e:
        logging.error(f"Error fetching workflow runs: {e}")
        return []
    return run_subset


def filter_by_date(runs, days):
    """Filter runs by date.
    
    Args:
        runs (list): List of workflow runs
        days (int): Number of days to look back
        
    Returns:
        list: Filtered list of runs
    """
    filtered_runs = []
    for run in runs:
        try:
            created_at = run.get('created_at')
            if created_at:
                days_ago = (datetime.now() - datetime.strptime(created_at, f'%Y-%m-%dT%H:%M:%SZ')).days
                if days_ago <= days:
                    filtered_runs.append(run)
        except (ValueError, KeyError) as e:
            logging.warning(f"Skipping run with invalid date format: {e}")
    return filtered_runs

def get_jobs_for_workflow_run(run_id: int, api, output_dir: str = "logs"):
    run_dir = Path(output_dir) / f"run-{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    logging.info(f"Fetching jobs for run ID: {run_id}...")

    try:
        # TODO: Should be used iteratively in main loop
        jobs = api.actions.list_jobs_for_workflow_run(run_id)
        
        if 'jobs' not in jobs:
            logging.error(f"Invalid response for run {run_id}: 'jobs' key not found")
            return []
            
        return [
            {"id": job.get('id'), "name": job.get('name', 'unnamed-job')} 
            for job in jobs['jobs'] 
            if job.get('id')  # Skip jobs with missing ID
        ]
    except Exception as e:
        logging.error(f"Error fetching jobs for run {run_id}: {e}")
        return []

def get_logs_for_job(job_id: int, job_name: str, parent_run_id: int, repo: str, output_dir: str = "logs"):
    """
    Download logs for a specific job using GitHub CLI.
    
    Args:
        job_id (int): The job ID
        job_name (str): The name of the job
        parent_run_id (int): The parent run ID
    """

    run_dir = Path(output_dir) / f"run-{parent_run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    output_path = run_dir / f"{job_id}-{job_name}.log"
    
    try:
        import subprocess
        cmd = [
            "gh", "api",
            "-H", f"Accept: application/vnd.github+json",
            "-H", f"X-GitHub-Api-Version: 2022-11-28",
            f"repos/{repo}/actions/jobs/{job_id}/logs"
        ]
        
        with output_path.open("wb") as f:
            result = subprocess.run(cmd, stdout=f, check=True)
        
        logging.info(f"Log saved to: {output_path}")
        return output_path
    except subprocess.CalledProcessError as e:
        logging.error(f"Error downloading log for job {job_id}: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error downloading log for job {job_id}: {e}")
        return None

def main():
    """Main function to run the script."""
    try:
        args = parse_arguments()
        
        # Create output directory
        try:
            Path(args.output).mkdir(parents=True, exist_ok=True)
        except PermissionError:
            logging.error(f"Permission denied when creating directory: {args.output}")
            return 1
        except Exception as e:
            logging.error(f"Error creating output directory: {e}")
            return 1
        
        # Check for GitHub token
        try:
            github_token = os.environ["GITHUB_TOKEN"]
        except KeyError:
            logging.error("GITHUB_TOKEN environment variable is not set")
            print("Error: GITHUB_TOKEN environment variable must be set.")
            print("Set it with: export GITHUB_TOKEN=your_token")
            return 1
        
        try:
            # Parse repository
            if '/' not in args.repo:
                logging.error(f"Invalid repository format: {args.repo}")
                return 1
                
            owner, repo_name = args.repo.split("/")
            api = GhApi(owner=owner, repo=repo_name, token=github_token)
            
            # Get workflows
            try:
                all_workflows = api.actions.list_repo_workflows()
            except Exception as e:
                logging.error(f"Failed to list workflows: {e}")
                return 1
            
            # Find workflow ID by name
            workflow_name = args.workflow
            workflow_id = find_workflow_id_by_name(all_workflows, workflow_name, api)
            
            if workflow_id is None:
                logging.error(f"Could not find workflow: {workflow_name}")
                print(f"Error: Workflow '{workflow_name}' not found in repository {args.repo}")
                print("Available workflows:")
                for wf in all_workflows.get('workflows', []):
                    print(f"  - {wf.get('name')}")
                return 1
            
            # Get run IDs
            runs = get_run_ids(workflow_id, api, args.page_size, args.days)
            if not runs:
                logging.warning(f"No runs found for workflow {workflow_name} in the past {args.days} days")
                print(f"No workflow runs found for '{workflow_name}' in the past {args.days} days")
                return 0
            
            # Process each run
            success_count = 0
            for run in runs:
                jobs = get_jobs_for_workflow_run(run['id'], api, args.output)
                for job in jobs:
                    log_path = get_logs_for_job(job['id'], job['name'], run['id'], args.repo, args.output)
                    if log_path:
                        success_count += 1
            
            logging.info(f"Successfully downloaded {success_count} log files")
            print(f"\nSuccessfully downloaded {success_count} log files to {args.output}/")
            return 0
            
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            return 1
            
    except Exception as e:
        logging.error(f"Critical error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
