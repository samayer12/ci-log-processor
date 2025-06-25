#!/usr/bin/env python3
"""
Script to download E2E logs from GitHub Actions workflows.
Example Usage: python download_e2e_logs.py -r defenseunicorns/pepr -w "E2E - Pepr Excellent Examples" -o loggy
"""

import argparse
import json
import os
import subprocess
import sys
import tarfile
from datetime import datetime, timedelta, UTC


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Download logs from a GitHub Actions workflow."
    )
    parser.add_argument("-r", "--repo", required=True, help="Repository in owner/repo format")
    parser.add_argument("-w", "--workflow", required=True, help="Workflow name")
    parser.add_argument("-d", "--days", type=int, default=7, help="Days to look back (default: 7)")
    parser.add_argument("-o", "--output", default="logs", help="Output directory (default: logs)")
    parser.add_argument("-l", "--limit", default=100, help="Limit the amount of workflow runs that are pulled. Used to avoid API rate-limits during testing.")
    
    return parser.parse_args()


def validate_inputs(args):
    """Validate input arguments."""
    if not args.repo or not args.workflow:
        print("Error: Repository and workflow name are required.")
        sys.exit(1)


def get_workflow_id(repo, workflow_name):
    """Get the workflow ID for the given workflow name."""
    print(f"Fetching workflow ID for '{workflow_name}'...")
    
    try:
        cmd = ["gh", "workflow", "list", "--repo", repo, "--limit", "100", "--json", "name,id"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        workflows = json.loads(result.stdout)
        
        for workflow in workflows:
            if workflow["name"] == workflow_name:
                workflow_id = workflow["id"]
                print(f"Workflow ID: {workflow_id}")
                return workflow_id
        
        print(f"Error: Workflow '{workflow_name}' not found in repository '{repo}'.")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Error executing GitHub CLI: {e}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing GitHub CLI output: {e}")
        sys.exit(1)


def get_run_ids(repo, workflow_id, days):
    """Get workflow run IDs from the last specified days."""
    print(f"Fetching workflow runs from the last {days} days...")
    
    try:
        # Calculate date for cutoff
        cutoff_date = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        cmd = [
            "gh", "run", "list", 
            "--workflow", str(workflow_id), 
            "--repo", repo, 
            "--limit", limit,
            "--json", "databaseId,createdAt"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        runs = json.loads(result.stdout)
        
        run_ids = []
        for run in runs:
            if run["createdAt"] >= cutoff_date:
                run_ids.append(run["databaseId"])
        
        if not run_ids:
            print(f"No runs found for the past {days} days.")
            sys.exit(0)
            
        return run_ids
    except subprocess.CalledProcessError as e:
        print(f"Error executing GitHub CLI: {e}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing GitHub CLI output: {e}")
        sys.exit(1)


def download_logs_for_run(repo, run_id, output_dir):
    """Download logs for a specific run ID."""
    run_dir = os.path.join(output_dir, f"run-{run_id}")
    os.makedirs(run_dir, exist_ok=True)

    print(f"Fetching jobs for run ID: {run_id}...")
    try:
        cmd = ["gh", "run", "view", str(run_id), "--repo", repo, "--json", "jobs"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        jobs_data = json.loads(result.stdout)
        
        jobs = jobs_data.get("jobs", [])
        if not jobs:
            print(f"No jobs found for run ID: {run_id}")
            return
        
        for index, job in enumerate(jobs):
            job_id = job["databaseId"]
            job_name = job["name"].replace(" ", "_")
            job_log_file = os.path.join(run_dir, f"{index}-{job_name}.log")
            
            print(f"Downloading log for job: {job_name} (ID: {job_id})...")
            
            try:
                cmd = [
                    "gh", "api",
                    "-H", "Accept: application/vnd.github+json",
                    "-H", "X-GitHub-Api-Version: 2022-11-28",
                    f"repos/{repo}/actions/jobs/{job_id}/logs"
                ]
                with open(job_log_file, "wb") as f:
                    log_result = subprocess.run(cmd, stdout=f, check=True)
                
                print(f"Log saved to: {job_log_file}")
            except subprocess.CalledProcessError as e:
                print(f"Error downloading log for job {job_id}: {e}")
    
    except subprocess.CalledProcessError as e:
        print(f"Error fetching jobs for run {run_id}: {e}")
    except json.JSONDecodeError as e:
        print(f"Error parsing jobs data for run {run_id}: {e}")


def compress_logs(output_dir):
    """Compress logs directory into a tar.gz file."""
    print("Compressing logs...")
    tar_filename = f"{output_dir}.tar.gz"
    
    with tarfile.open(tar_filename, "w:gz") as tar:
        tar.add(output_dir, arcname=os.path.basename(output_dir))
    
    print(f"Logs compressed into '{tar_filename}'.")


def main():
    """Main execution function."""
    args = parse_arguments()
    validate_inputs(args)
    
    # Ensure output directory exists
    os.makedirs(args.output, exist_ok=True)
    
    # Get workflow ID and run IDs
    workflow_id = get_workflow_id(args.repo, args.workflow)
    run_ids = get_run_ids(args.repo, workflow_id, args.days, args.limit)
    
    print(f"Downloading logs for runs from the last {args.days} days...")
    for run_id in run_ids:
        download_logs_for_run(args.repo, run_id, args.output)
    
    compress_logs(args.output)
    print(f"All logs downloaded and compressed successfully in '{args.output}.tar.gz'.")


if __name__ == "__main__":
    main()