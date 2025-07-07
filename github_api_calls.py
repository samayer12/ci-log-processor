import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from ghapi.all import GhApi, paged


def get_run_ids(
    workflow_id: int, api: GhApi, page_size: int, max_pages: bool, days: int, date_range: str = ""
) -> List[Dict[str, Any]]:
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
            logging.info("Kludge! Setting page-depth to 5")
            page_depth = 5
        date_limit = datetime.today() - timedelta(days=days)
        date_limit_str = ">=" + date_limit.strftime("%Y-%m-%d")
        if days == 7 and date_range != "":  # 7 is the default for days
            date_limit_str = date_range
            logging.info("Filtering on date range: %s", date_limit_str)
        runs = paged(
            api.actions.list_workflow_runs,
            workflow_id,
            created=date_limit_str,
            per_page=page_size,
            max_pages=page_depth,
        )
        run_subset = []
        page_number = 1
        for page in runs:
            if len(page["workflow_runs"]) == 0:
                logging.info("No entries detected after %d pages", page_number - 1)
                return run_subset  # End of pagination, return the collection

            logging.info("There are %d runs on page %d", len(page["workflow_runs"]), page_number)
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
            "There are %d runs that happened in the filter range. (Filter: %s)",
            len(run_subset),
            date_limit_str,
        )
    except Exception as e:
        logging.error("Error fetching workflow runs: %s", e)
        return []
    if len(run_subset) == 0:
        logging.warning(
            "No runs found for this workflow (id: %d) in the past %d days",
            workflow_id,
            days,
        )
    return run_subset


def get_jobs_for_workflow_run(run_id: int, api: GhApi, output_dir: str = "logs") -> List[Dict[str, Any]]:
    run_dir = Path(output_dir) / f"run-{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    try:
        jobs = api.actions.list_jobs_for_workflow_run(run_id)

        if "jobs" not in jobs:
            logging.error("Invalid response for run %d: 'jobs' key not found", run_id)
            return []

        valid_jobs = [
            {"id": job.get("id"), "name": job.get("name", "unnamed-job")}
            for job in jobs["jobs"]
            if job.get("id")  # Skip jobs with missing ID
        ]
        logging.debug("Fetched %d valid jobs for run %d", len(valid_jobs), run_id)
        return valid_jobs
    except Exception as e:
        logging.error("Error fetching jobs for run %d: %s", run_id, e)
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

        # logging.info("Log saved to: %s", output_path)
        return output_path
    except subprocess.CalledProcessError as e:
        logging.error("Error downloading log for job %d: %s", job_id, e)
        return None
    except Exception as e:
        logging.error("Unexpected error downloading log for job %d: %s", job_id, e)
        return None


def get_all_job_ids(runs, api, output):
    fetch_limit = 90  # 30 runs w/ 30 jobs each
    all_jobs = []
    processed_runs = []
    for run in runs:
        jobs = get_jobs_for_workflow_run(run["id"], api, output)
        for job in jobs:
            all_jobs.append((job, run["id"]))
        logging.info("Fetched jobs for run %s. %d total jobs.", run["id"], len(all_jobs))
        processed_runs.append(run["id"])
        if len(all_jobs) > fetch_limit:
            logging.warning("Too many jobs were fetched (limit %d).", fetch_limit)
            logging.info("%d Processed runs: %s", len(processed_runs), processed_runs)
            logging.warning(
                "%d Unprocessed runs. %s",
                len(runs) - len(processed_runs),
                [run["id"] for run in runs if run["id"] not in processed_runs],
            )
            return all_jobs
    return all_jobs
