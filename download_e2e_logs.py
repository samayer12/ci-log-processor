import argparse
import logging
import os
import sys
from pathlib import Path

from ghapi.all import GhApi

from github_api_calls import get_all_job_ids, get_run_ids
from github_response_processors import find_workflow_id_by_name
from parallel_processing import get_job_logs_in_parallel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Download logs from a GitHub Actions workflow.")
    parser.add_argument("-r", "--repo", required=True, help="Repository in owner/repo format")
    parser.add_argument("-w", "--workflow", required=True, help="Workflow name")
    parser.add_argument(
        "-d",
        "--days",
        type=int,
        default=7,
        help="Days to look back (default: 7)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="logs",
        help="Output directory (default: logs)",
    )
    parser.add_argument(
        "-1",
        "--once",
        action="store_true",
        help="Only fetch one page. Used with --page-size in" "testing to avoid API rate-limits",
    )
    parser.add_argument(
        "-p",
        "--page-size",
        type=int,
        default=100,
        help="Set page size (default: 100)",
    )

    args = parser.parse_args()

    # Validate repository format
    if "/" not in args.repo:
        parser.error("Repository must be in 'owner/repo' format")

    # Validate days argument
    if args.days < 0:
        parser.error("Days must be a positive integer, or zero")

    # Validate page size
    if args.page_size <= 0:
        parser.error("Page size must be a positive non-zero integer")

    return args


def create_output_directory(output: str):
    # Create output directory
    try:
        Path(output).mkdir(parents=True, exist_ok=True)
    except PermissionError:
        logging.error("Permission denied when creating directory: %s", output)
        return 1
    except Exception as e:
        logging.error("Error creating output directory: %s", e)
        return 1


def is_invalid_github_token():
    # Check for GitHub token
    try:
        os.environ["GITHUB_TOKEN"]
    except KeyError:
        logging.error("GITHUB_TOKEN environment variable is not set")
        print("Error: GITHUB_TOKEN environment variable must be set.")
        print("Set it with: export GITHUB_TOKEN=your_token")
        return True
    return False


def get_workflow_id(repo, workflow_name, api):
    # Get workflows
    try:
        all_workflows = api.actions.list_repo_workflows()
    except Exception as e:
        logging.error("Failed to list workflows: %s", e)
        return 1

    # Find workflow ID by name
    workflow_id = find_workflow_id_by_name(all_workflows, workflow_name)

    if workflow_id is None:
        logging.error("Could not find workflow: %s", workflow_name)
        print(f"Error: Workflow '{workflow_name}' " f"not found in repository {repo}")
        print("Available workflows:")
        for wf in all_workflows.get("workflows", []):
            print(f"  - {wf.get('name')}")
        return None

    return workflow_id


def main() -> int:
    """Main function to run the script."""
    try:
        args = parse_arguments()

        create_output_directory(args.output)

        if is_invalid_github_token():
            return 1

        try:
            owner, repo_name = args.repo.split("/", 1)
            api = GhApi(owner=owner, repo=repo_name, token=os.environ["GITHUB_TOKEN"])

            workflow_id = get_workflow_id(args.repo, args.workflow, api)

            runs = get_run_ids(workflow_id, api, args.page_size, args.once, args.days)
            if not runs:
                return 0

            all_job_ids = get_all_job_ids(runs, api, args.output)

            get_job_logs_in_parallel(all_job_ids, args.repo, args.output)

            return 0

        except Exception as e:
            logging.error("Unexpected error: %s", e)
            return 1

    except Exception as e:
        logging.error("Critical error: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
