import argparse
import sys
from ghapi.all import GhApi
import os
from pathlib import Path
import logging
import concurrent.futures
from typing import Dict,  Optional, Any
from github_api_calls import get_jobs_for_workflow_run, get_logs_for_job, get_run_ids
from github_response_processors import find_workflow_id_by_name

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def parse_arguments() -> argparse.Namespace:
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

def main() -> int:
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
                
            owner, repo_name = args.repo.split("/", 1)
            api = GhApi(owner=owner, repo=repo_name, token=github_token)
            
            # Get workflows
            try:
                all_workflows = api.actions.list_repo_workflows()
            except Exception as e:
                logging.error(f"Failed to list workflows: {e}")
                return 1
            
            # Find workflow ID by name
            workflow_name = args.workflow
            workflow_id = find_workflow_id_by_name(all_workflows, workflow_name)
            
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
            
            # Process each run in parallel
            success_count = 0
            
            # Helper function for parallel execution
            def process_job(job_data: Dict[str, Any], run_id: int) -> Optional[Path]:
                return get_logs_for_job(job_data['id'], job_data['name'], run_id, args.repo, args.output)
            
            # Collect all jobs from all runs
            all_jobs = []
            for run in runs:
                jobs = get_jobs_for_workflow_run(run['id'], api, args.output)
                for job in jobs:
                    all_jobs.append((job, run['id']))
            
            logging.info(f"Processing {len(all_jobs)} jobs in parallel...")
            
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
