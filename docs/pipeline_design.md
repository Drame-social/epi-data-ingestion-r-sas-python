# Pipeline Design

## Overview

This pipeline ingests three synthetic public health data sources, applies systematic data quality (DQ) remediation, links them via a shared geographic key, and outputs county-level annual disease incidence rates per 100,000 population.

```
data/raw/
├── hospital_discharge_records.csv  (1,500 rows, includes 75 duplicates)
├── reportable_disease_registry.csv (800 rows, mixed date formats)
└── population_denominators.csv     (200 rows — 50 counties × 4 years)
        │
        ▼
  01_ingest_hospital_discharge  →  hospital_discharge_clean.csv  (1,425 rows)
  02_ingest_disease_registry    →  registry_clean.csv             (800 rows)
        │
        ▼
  03_merge_denominators
        │  (inner join on county_fips × year)
        ▼
  master_incidence_dataset.csv   (624 county × year × condition rows)
        │
        ▼
  04_summary_outputs  →  3 figures + summary tables
```

---

## Data Sources

| Source | File | Raw rows | Clean rows | Key geographic field |
|--------|------|---------|-----------|---------------------|
| Hospital discharge | `hospital_discharge_records.csv` | 1,500 | 1,425 | `county_fips` |
| Disease registry | `reportable_disease_registry.csv` | 800 | 800 | `county_fips` |
| Population denominators | `population_denominators.csv` | 200 | 200 | `county_fips` |

**Geographic universe:** 50 counties, FIPS codes 01001–01050. All three datasets share this universe, ensuring the registry↔denominator merge produces complete incidence rates with no FIPS mismatches.

---

## DQ Issues and Remediation

| Dataset | Issue | N rows | Action |
|---------|-------|--------|--------|
| Hospital discharge | Duplicate MRN + admit_date | **75** | Remove; keep first occurrence |
| Hospital discharge | Invalid age (sentinels 999, -1; range <0 or >120) | ~22 | Set to NULL |
| Hospital discharge | Non-standard sex codes | 1,415 rows standardised | Standardise to Male/Female/Unknown |
| Hospital discharge | Invalid ZIP codes (00000) | 25 | Flag `zip_valid=0`; retain value |
| Disease registry | Mixed date formats (ISO + MM/DD/YYYY) | 115 (14%) | Parse both formats; convert to datetime |

---

## Step-by-Step

### `00_generate_synthetic_data.py`
Generates all three raw CSVs from seed=123. Can be skipped if using the provided files.

### `01_ingest_hospital_discharge.py`
- Load 1,500 rows
- Identify and remove 75 true MRN+admit_date duplicate pairs (keep first)
- Nullify age sentinels and out-of-range values (~22 rows)
- Standardise all sex codes → Male/Female/Unknown
- Flag invalid ZIP codes (`zip_valid=0`)
- Log all DQ actions with row counts → `outputs/logs/pipeline_run_log.txt`
- Output: `data/clean/hospital_discharge_clean.csv` (1,425 rows)
- Output: `outputs/tables/dq_report_hospital_discharge.csv`

### `02_ingest_disease_registry.py`
- Load 800 rows as character dtype to preserve leading zeros in FIPS
- Parse mixed dates: try `%Y-%m-%d` first, then `%m/%d/%Y` — 115/800 rows use US format
- Zero-pad `county_fips` to 5 characters
- Derive binary indicators: `hospitalized_bin`, `died_bin`, `is_outbreak_case`, `age_missing`
- Output: `data/clean/registry_clean.csv` (800 rows)
- Output: `outputs/tables/dq_report_registry.csv`

### `03_merge_denominators.py`
- Aggregate registry by `county_fips × year × condition_name`
- Inner join with population denominators on `county_fips × year`
- Calculate: `incidence_rate_100k = (case_count / population_total) × 100,000`
- Output: `data/clean/master_incidence_dataset.csv` (624 rows, 100% with valid rates)
- Output: `outputs/tables/incidence_rates_by_county_year.csv`
- Output: `outputs/tables/summary_by_condition.csv`

### `04_summary_outputs.py`
- Figure 1: Mean incidence rate per 100K by condition
- Figure 2: Hospitalisation and case-fatality rates by condition
- Figure 3: Total annual cases by condition (2020–2023 trend)

---

## Merge Performance

| Metric | Value |
|--------|-------|
| Registry records with valid FIPS | 800 (100%) |
| Population denominator records | 200 (50 counties × 4 years) |
| Master dataset rows (post-merge) | 624 |
| Rows with complete incidence rate | 624 (100%) |

---

## Logging

All pipeline runs append to `outputs/logs/pipeline_run_log.txt`. Each DQ action records: issue description, number of rows affected, action taken, and timestamp. Supports audit trails and pipeline monitoring.

---

## Admin vs. Surveillance — Source Comparison

| Dimension | Hospital Discharge (Admin) | Disease Registry (Surveillance) |
|-----------|--------------------------|----------------------------------|
| Trigger | Any inpatient admission | Mandatory reportable disease report |
| Coverage | Hospital-bound cases only | Community + hospital |
| Disease coding | ICD-10-CM | Condition names |
| Geography | Patient county | Reporting county |
| Primary DQ issues | Duplicates, mixed sex codes | Mixed date formats |
| After cleaning | 1,425 rows | 800 rows |

---

## Reproducibility

With seed=123 and the provided raw CSVs, all downstream outputs are deterministic. Run scripts 00→04 in sequence from the project root directory.
