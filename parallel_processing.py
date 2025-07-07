import concurrent.futures
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from github_api_calls import get_logs_for_job


def get_job_logs_in_parallel(all_jobs, repo, output):
    rate_limit_index = 900
    if len(all_jobs) > rate_limit_index:
        logging.warning(
            "More than 1000 jobs detected (found %d). " "Only fetching first %d jobs to avoid rate-limit.",
            len(all_jobs),
            rate_limit_index,
        )
        all_jobs = all_jobs[:rate_limit_index]
    logging.info("Processing %d jobs in parallel.", len(all_jobs))
    # Process each run in parallel
    success_count = 0

    # Helper function for parallel execution
    def process_job(job_data: Dict[str, Any], run_id: int) -> Optional[Path]:
        return get_logs_for_job(job_data["id"], job_data["name"], run_id, repo, output)

    # TODO: Rate-limiting @ 1000 requests per hour per repo
    # https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api?apiVersion=2022-11-28#primary-rate-limit-for-github_token-in-github-actions
    # Use ThreadPoolExecutor to process jobs in parallel
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Create a list of futures
        futures = [executor.submit(process_job, job, run_id) for job, run_id in all_jobs]

        # Process results as they complete
        for future in concurrent.futures.as_completed(futures):
            try:
                log_path = future.result()
                if log_path:
                    success_count += 1
            except Exception as exc:
                logging.error("Job processing failed: %s", exc)
    logging.info(
        "(%d/%d) Successfully downloaded %d log files to %s/", success_count, len(all_jobs), success_count, output
    )
