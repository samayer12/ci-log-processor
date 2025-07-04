import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from ghapi.all import GhApi, paged


def get_run_ids(workflow_id: int, api: GhApi, page_size: int, max_pages: bool, days: int) -> List[Dict[str, Any]]:
    """
    Get the run IDs for a specific workflow.

    Args:
        workflow_id (int): ID of the workflow

    Returns:
        list: List of run IDs
    """
    try:
        page_depth = 9999
        if max_pages:
            logging.info("--once flag detected. Only getting one page.")
            page_depth = 1
        date_limit = datetime.today() - timedelta(days=days)
        date_limit_str = date_limit.strftime("%Y-%m-%d")
        runs = paged(
            api.actions.list_workflow_runs,
            workflow_id,
            created=f">={date_limit_str}",
            per_page=page_size,
            max_pages=page_depth,
        )
        run_subset = []
        page_number = 1
        for page in runs:
            if len(page["workflow_runs"]) == 0:
                logging.info(f"No entries detected after {page_number - 1} pages")
                return run_subset  # End of pagination, return the collection

            logging.info(f"There are {len(page['workflow_runs'])} runs on page {page_number}")
            page_number += 1

            for run in page["workflow_runs"]:
                run_subset.append(
                    {
                        "id": run.get("id"),
                        "status": run.get("status"),
                        "conclusion": run.get("conclusion"),
                        "created_at": run.get("created_at"),
                    }
                )

        logging.info(
            f"There are {len(run_subset)} runs that happened within the past {days} days. (Filter: >={date_limit_str})"
        )
    except Exception as e:
        logging.error(f"Error fetching workflow runs: {e}")
        return []
    if len(run_subset) == 0:
        logging.warning(f"No runs found for this workflow (id: {workflow_id}) in the past {days} days")
    return run_subset


def get_jobs_for_workflow_run(run_id: int, api: GhApi, output_dir: str = "logs") -> List[Dict[str, Any]]:
    run_dir = Path(output_dir) / f"run-{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    logging.info(f"Fetching jobs for run ID: {run_id}...")

    try:
        jobs = api.actions.list_jobs_for_workflow_run(run_id)

        if "jobs" not in jobs:
            logging.error(f"Invalid response for run {run_id}: 'jobs' key not found")
            return []

        return [
            {"id": job.get("id"), "name": job.get("name", "unnamed-job")}
            for job in jobs["jobs"]
            if job.get("id")  # Skip jobs with missing ID
        ]
    except Exception as e:
        logging.error(f"Error fetching jobs for run {run_id}: {e}")
        return []


def get_logs_for_job(
    job_id: int,
    job_name: str,
    parent_run_id: int,
    repo: str,
    output_dir: str = "logs",
) -> Optional[Path]:
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
            "gh",
            "api",
            "-H",
            "Accept: application/vnd.github+json",
            "-H",
            "X-GitHub-Api-Version: 2022-11-28",
            f"repos/{repo}/actions/jobs/{job_id}/logs",
        ]

        with output_path.open("wb") as f:
            subprocess.run(cmd, stdout=f, check=True)

        logging.info(f"Log saved to: {output_path}")
        return output_path
    except subprocess.CalledProcessError as e:
        logging.error(f"Error downloading log for job {job_id}: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error downloading log for job {job_id}: {e}")
        return None


def get_all_job_ids(runs, api, output):
    all_jobs = []
    for run in runs:
        jobs = get_jobs_for_workflow_run(run["id"], api, output)
        for job in jobs:
            all_jobs.append((job, run["id"]))
    return all_jobs
