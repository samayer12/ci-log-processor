from ghapi.all import GhApi
from datetime import datetime,timedelta 
from pathlib import Path
import logging
from typing import Dict, List, Optional, Any

def get_run_ids(workflow_id: int, api: GhApi, page_size: int, days: int) -> List[Dict[str, Any]]:
    """
    Get the run IDs for a specific workflow.
    
    Args:
        workflow_id (int): ID of the workflow
    
    Returns:
        list: List of run IDs
    """
    try:
        # TODO: Pagination & long history requests
        date_limit = datetime.today() - timedelta(days=days)
        date_limit_str = date_limit.strftime("%Y-%m-%d")
        runs = api.actions.list_workflow_runs(workflow_id, created=f">={date_limit_str}", per_page=page_size)
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
        
        logging.info(f"There are {len(run_subset)} runs that happened within the past {days} days. (Filter: >={date_limit_str})")
    except Exception as e:
        logging.error(f"Error fetching workflow runs: {e}")
        return []
    return run_subset

def get_jobs_for_workflow_run(run_id: int, api: GhApi, output_dir: str = "logs") -> List[Dict[str, Any]]:
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

def get_logs_for_job(job_id: int, job_name: str, parent_run_id: int, repo: str, output_dir: str = "logs") -> Optional[Path]:
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
