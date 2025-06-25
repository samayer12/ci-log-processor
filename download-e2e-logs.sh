#!/bin/bash
# Example Usage: ./download-e2e-logs.sh -r defenseunicorns/pepr -w "E2E - Pepr Excellent Examples" -o loggy
set -e # Exit immediately if a command exits with a non-zero status

OUTPUT_DIR="logs" # Default values

usage() {
    echo "Usage: $0 -r <owner/repo> -w <workflow_name> [-d <days> -o <output_directory>]"
    exit 1
}

validate_inputs() {
    if [[ -z "$REPO" || -z "$WORKFLOW_NAME" ]]; then
        echo "Error: Repository and workflow name are required."
        usage
    fi
}

get_workflow_id() {
    echo "Fetching workflow ID for '$WORKFLOW_NAME'..."
    WORKFLOW_ID=$(gh workflow list --repo "$REPO" --limit 100 --json name,id | jq -r ".[] | select(.name==\"$WORKFLOW_NAME\") | .id")

    if [[ -z "$WORKFLOW_ID" ]]; then
        echo "Error: Workflow '$WORKFLOW_NAME' not found in repository '$REPO'."
        exit 1
    fi
    echo "Workflow ID: $WORKFLOW_ID"
}

# Get workflow runs from the last $DAYS days
get_run_ids() {
    echo "Fetching workflow runs from the last $DAYS days..."
    RUN_IDS=$(gh run list --workflow "$WORKFLOW_ID" --repo "$REPO" --limit 3 --json databaseId,createdAt \
        --jq "map(select(.createdAt >= \"$(date -v-$(echo $DAYS)d -u +"%Y-%m-%dT%H:%M:%SZ")\")) | .[].databaseId")

    if [[ -z "$RUN_IDS" ]]; then
        echo "No runs found for the past $DAYS days."
        exit 0
    fi
}

download_logs_for_run() {
    local RUN_ID=$1
    local RUN_DIR="$OUTPUT_DIR/run-$RUN_ID"
    mkdir -p "$RUN_DIR"

    echo "Fetching jobs for run ID: $RUN_ID..."
    JOBS_JSON=$(gh run view "$RUN_ID" --repo "$REPO" --json jobs)
    
    JOB_IDS=()
    while IFS= read -r job_id; do
        JOB_IDS+=("$job_id")
    done < <(jq -r '.jobs[].databaseId' <<< "$JOBS_JSON")
    
    JOB_NAMES=()
    while IFS= read -r job_name; do
        JOB_NAMES+=("$job_name")
    done < <(jq -r '.jobs[].name' <<< "$JOBS_JSON")

    if [[ ${#JOB_IDS[@]} -eq 0 ]]; then
        echo "No jobs found for run ID: $RUN_ID"
        return
    fi

    for INDEX in "${!JOB_IDS[@]}"; do
        local JOB_ID=${JOB_IDS[$INDEX]}
        local JOB_NAME
        JOB_NAME=$(echo "${JOB_NAMES[$INDEX]}" | tr ' ' '_')
        local JOB_LOG_FILE="$RUN_DIR/$INDEX-$JOB_NAME.log"

        echo "Downloading log for job: $JOB_NAME (ID: $JOB_ID)..."
        gh api -H "Accept: application/vnd.github+json" \
               -H "X-GitHub-Api-Version: 2022-11-28" \
               repos/"$REPO"/actions/jobs/"$JOB_ID"/logs > "$JOB_LOG_FILE"

        echo "Log saved to: $JOB_LOG_FILE"
    done
}

compress_logs() {
    echo "Compressing logs..."
    tar -czvf "$OUTPUT_DIR.tar.gz" "$OUTPUT_DIR"
    echo "Logs compressed into '$OUTPUT_DIR.tar.gz'."
}

# Parse command-line arguments
while getopts "r:w:d:o:h" opt; do
    case ${opt} in
        r ) REPO=$OPTARG ;;
        w ) WORKFLOW_NAME=$OPTARG ;;
        d ) DAYS=$OPTARG ;;
        o ) OUTPUT_DIR=$OPTARG ;;
        h ) usage ;;
        * ) usage ;;
    esac
done

# Main execution flow
validate_inputs
mkdir -p "$OUTPUT_DIR"
get_workflow_id
get_run_ids

echo "Downloading logs for runs from the last $DAYS days..."
for RUN_ID in $RUN_IDS; do
    download_logs_for_run "$RUN_ID"
done

compress_logs
echo "All logs downloaded and compressed successfully in '$OUTPUT_DIR.tar.gz'."

exit 0