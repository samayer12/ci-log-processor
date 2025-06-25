from github_api_calls import get_logs_for_job
import logging
import concurrent.futures
from typing import Dict,  Optional, Any
from pathlib import Path

def get_job_logs_in_parallel(all_jobs, repo, output):
    logging.info(f"Processing {len(all_jobs)} jobs in parallel...")
    # Process each run in parallel
    success_count = 0
    # Helper function for parallel execution
    def process_job(job_data: Dict[str, Any], run_id: int) -> Optional[Path]:
        return get_logs_for_job(job_data['id'], job_data['name'], run_id, repo, output)

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
                logging.error(f"Job processing failed: {exc}")
    logging.info(f"Successfully downloaded {success_count} log files to {output}/")