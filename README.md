# CI Log Processing

This repo attempts to provide detailed performance data for CI pipelines.
Sometimes, the basic data views provided by Github don't quite provide the data I'm after.

## Quickstart

```
# Authenticate with gh
./download-e2e-logs.sh -r defenseunicorns/pepr -w "E2E - Pepr Excellent Examples" -o loggy -d 1
python3 ./process_e2e_data.py loggy/run-* > py.log
python3 ./chart_e2e_data.py 
# Observe failures_histogram.png and failures_stacked_histogram.png
```

## Current State

Through a combination of shell & python scripts, one can manually pull and visualize data for a particular workflow.

## Future Goals

* Implement in Python.
* Provide data to a monitoring/observability stack (e.g., LGTM).
* Create a UDS package.