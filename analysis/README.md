# R analysis

`RQ2_NAR_analysis.R` is the retained research analysis script for model-specific RQ1/RQ2/RQ3 outputs. It requires private stats-ready CSV files; those data are not included in the public repository.

The script never installs packages automatically. Install these in an isolated R environment before use: `tidyverse`, `readr`, `writexl`, `janitor`, `nnet`, `broom`, `rstatix`, `cluster`, `ggplot2`, `forcats`, and `stringr`.

```bash
Rscript analysis/RQ2_NAR_analysis.R \
  --pipeline-dir=/path/to/private/rq2_pipeline_run \
  --output-dir=/path/to/private/analysis-output
```

Optional `--project-root=/path` changes the fallback root. The public synthetic files are not a statistical reproduction dataset and must not be used to validate the published findings.
