# Data Ingestion Processes with R, SAS, and Python

*By Aly Drame, MD, MPH, MBA.* A county-level foodborne/enteric disease ingestion pipeline built three ways — Python (primary), R, and SAS — to compare how each language handles messy, multi-source surveillance data. All inputs are synthetic (generated with `seed=123`); no real patients, counties, or case counts.

---

## Research Question

> **What are county-level annual incidence rates of reportable foodborne and enteric diseases (2020–2023), and how do administrative hospital discharge records compare with surveillance-based disease registry data?**

---

## Project Overview

A multi-source epidemiologic data ingestion pipeline implemented in Python (primary), R, and SAS. Demonstrates: multi-format date parsing, systematic data quality (DQ) assessment and remediation, geographic key harmonisation, denominator linkage, and incidence rate calculation across heterogeneous public health data sources.

The same ingestion logic is implemented in all three languages to allow direct comparison of syntax, performance, and idioms across tools commonly used in public health practice.

---

## Data

| Dataset | File | Raw rows | Source type |
|---------|------|----------|-------------|
| Hospital discharge records | `data/raw/hospital_discharge_records.csv` | 1,500 | Administrative (synthetic) |
| Reportable disease registry | `data/raw/reportable_disease_registry.csv` | 800 | Surveillance (synthetic) |
| Population denominators | `data/raw/population_denominators.csv` | 200 | Census (synthetic) |

> All data are fully synthetic, generated with seed=123. No real patients, counties, or disease counts.

**Geographic design:** All three datasets share the same 50-county FIPS universe (01001–01050), mirroring real-world pipeline design where disease registries, hospital systems, and census denominators are keyed to the same geographic taxonomy — enabling a clean join with no FIPS mismatches.

---

## Intentional Data Quality Issues

| Dataset | DQ Issue | Rows affected | Resolution |
|---------|----------|--------------|------------|
| Hospital discharge | True MRN + admit_date duplicates (billing re-submissions) | 75 (5%) | Remove; keep first occurrence → 1,425 clean rows |
| Hospital discharge | Invalid age sentinels (999, -1) and out-of-range | 22 | Set to NULL |
| Hospital discharge | Non-standard sex values injected (Male, 1, 2, MALE) | 20 | Recode all sex values to Male/Female/Unknown |
| Hospital discharge | Invalid ZIP codes (00000) | 25 | Flag `zip_valid=0`; retain original |
| Disease registry | Mixed date formats (ISO 8601 and MM/DD/YYYY) | 115 (14%) | Parse both; convert to standard datetime |

---

## Repository Structure

```
epi-data-ingestion-r-sas-python/
├── README.md
├── ASSUMPTIONS.md
├── LICENSE
├── .gitignore
├── requirements/
│   ├── requirements_python.txt
│   └── requirements_r.txt
├── code/
│   ├── python/
│   │   ├── 00_generate_synthetic_data.py    # Reproduce raw CSVs from scratch (seed=123)
│   │   ├── 01_ingest_hospital_discharge.py  # DQ cleaning + structured logging
│   │   ├── 02_ingest_disease_registry.py    # Mixed-date parsing + binary indicators
│   │   ├── 03_merge_denominators.py         # Aggregate, join, calculate rates
│   │   └── 04_summary_outputs.py            # Figures and summary tables
│   ├── r/
│   │   ├── 01_ingest_hospital_discharge.R
│   │   ├── 02_ingest_disease_registry.R
│   │   └── 03_merge_and_rates.R
│   └── sas/
│       ├── 01_ingest_hospital_discharge.sas
│       ├── 02_ingest_disease_registry.sas
│       └── 03_merge_and_rates.sas
├── data/
│   ├── raw/
│   │   ├── hospital_discharge_records.csv
│   │   ├── reportable_disease_registry.csv
│   │   └── population_denominators.csv
│   └── clean/
│       ├── hospital_discharge_clean.csv      # 1,425 rows after deduplication
│       ├── registry_clean.csv                # 800 rows
│       └── master_incidence_dataset.csv      # 624 rows; county x year x condition
├── docs/
│   ├── data_dictionary.md
│   ├── pipeline_design.md
│   └── limitations.md
└── outputs/
    ├── figures/
    │   ├── fig1_incidence_by_condition.png
    │   ├── fig2_hospitalization_cfr.png
    │   └── fig3_annual_trends.png
    ├── logs/
    │   └── pipeline_run_log.txt
    └── tables/
        ├── dq_report_hospital_discharge.csv
        ├── dq_report_registry.csv
        ├── incidence_rates_by_county_year.csv
        └── summary_by_condition.csv
```

---

## How to Reproduce

### Python (primary — fully tested)

```bash
git clone https://github.com/Drame-social/epi-data-ingestion-r-sas-python.git
cd epi-data-ingestion-r-sas-python
pip install -r requirements/requirements_python.txt
```

Run scripts in order:

```bash
python code/python/00_generate_synthetic_data.py    # optional — raw CSVs included
python code/python/01_ingest_hospital_discharge.py
python code/python/02_ingest_disease_registry.py
python code/python/03_merge_denominators.py
python code/python/04_summary_outputs.py
```

### R

```r
install.packages(c("tidyverse", "lubridate", "janitor", "here"))
source("code/r/01_ingest_hospital_discharge.R")
source("code/r/02_ingest_disease_registry.R")
source("code/r/03_merge_and_rates.R")
```

### SAS

Update `%let root = ...` in each script to your project path, then submit in order from SAS 9.4.

---

## Key Results (Synthetic Data)

### DQ remediation — hospital discharge

| Check | N affected | Action |
|-------|-----------|--------|
| Duplicate MRN + admit_date | 75 | Removed; 1,425 clean rows remain |
| Invalid age (sentinels 999, -1) | 22 | Set to NULL |
| Non-standard sex values injected | 20 | Whole column recoded to Male/Female/Unknown |
| Invalid ZIP code (00000) | 25 | Flagged; value retained |

### County-level incidence rates by condition (2020–2023)

| Condition | Total cases | Mean rate per 100K | Hosp. rate | CFR |
|-----------|------------|-------------------|-----------|-----|
| Cryptosporidium | 112 | 1.81 | 29.5% | 0.9% |
| Campylobacter | 108 | 1.85 | 33.3% | 1.9% |
| E. coli O157:H7 | 104 | 1.73 | 29.8% | 3.9% |
| Hepatitis A | 101 | 1.79 | 36.6% | 4.0% |
| Salmonella | 97 | 1.57 | 27.8% | 1.0% |
| Listeria | 94 | 1.49 | 26.6% | 2.1% |
| Vibrio | 94 | 2.03 | 36.2% | 5.3% |
| Shigella | 90 | 1.59 | 32.2% | 2.2% |

*All figures synthetic; mean rate averaged across 50 counties and 4 years (2020–2023).*

---

## Software Requirements

| Tool | Version | Purpose |
|------|---------|---------|
| Python | >= 3.10 | Primary pipeline |
| pandas | >= 2.0 | Data manipulation |
| numpy | >= 1.24 | Numeric operations |
| matplotlib | >= 3.7 | Figures |
| seaborn | >= 0.12 | Figures |
| R | >= 4.2 | Parallel implementation |
| tidyverse | >= 2.0 | Data wrangling |
| lubridate | >= 1.9 | Date parsing |
| SAS | 9.4 | Reference implementation |

---

## Documentation

| File | Contents |
|------|----------|
| `docs/data_dictionary.md` | All variables across all 3 datasets + master schema |
| `docs/pipeline_design.md` | Step-by-step data flow, DQ log, source comparison |
| `docs/limitations.md` | Join assumptions, synthetic data caveats |
| `ASSUMPTIONS.md` | Data generation decisions and known constraints |
| `outputs/logs/pipeline_run_log.txt` | Structured DQ log from each pipeline run |

---

*All data in this project are synthetic and were generated solely for portfolio demonstration. No real patient records, disease surveillance data, or personally identifiable information are included.*
