# CI Log Processing

This repo attempts to provide detailed performance data for CI pipelines.
Sometimes, the basic data views provided by Github don't quite provide the data I'm after.

## Quickstart

```
# Set GITHUB_TOKEN envar (e.g., export GITHUB_TOKEN=your_token)
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 download_e2e_logs.py --repo ORG/REPO --workflow "WORKFLOW_NAME" --output logs --days 0 --page-size 1 --once
python3 ./process_e2e_data.py logs/run-* > py.log
python3 ./chart_e2e_data.py
# Observe failures_histogram.png and failures_stacked_histogram.png
```

## Current State

One can manually pull and visualize data for a particular workflow.

CLI Options:

```
usage: download_e2e_logs.py [-h] -r REPO -w WORKFLOW [-d DAYS] [-o OUTPUT] [-1] [-p PAGE_SIZE]

Download logs from a GitHub Actions workflow.

options:
  -h, --help            show this help message and exit
  -r, --repo REPO       Repository in owner/repo format
  -w, --workflow WORKFLOW
                        Workflow name
  -o, --output OUTPUT   Output directory (default: logs)
  -1, --once            Only fetch one page. Used with --page-size in testing to avoid API rate-limits
  -p, --page-size PAGE_SIZE
                        Set page size (default: 100)
  -d, --days DAYS       Days to look back (default: 7). Exclusive with --range
  --range RANGE         Set the date-range to pull events from (YYYY-MM-DD..YYYY-MM-DD). Exclusive with --days
```

## Future Goals

* Provide data to a monitoring/observability stack (e.g., LGTM).
* Handle rate-limiting for Github API.
* Create a consumable package of this work.

```mermaid
graph TD
    A[CronJob: Fetch Data] --> B[Raw JSON/Log Downloader]
    B --> C["Log Processor (Regex)
    - Failure types
    - Timings"]
    C --> D["Prometheus
    - Metrics"]
    C --> E["Loki (Optional)
    - Raw log search"]
    D --> F[Grafana]
```
