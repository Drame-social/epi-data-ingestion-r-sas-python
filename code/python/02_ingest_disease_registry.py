"""
02_ingest_disease_registry.py
─────────────────────────────────────────────────────────────────────────────
Purpose : Ingest, validate, and clean the raw reportable disease registry.
          Key data quality issue: mixed date formats.

Input   : data/raw/reportable_disease_registry.csv
Outputs : data/clean/registry_clean.csv
          outputs/tables/dq_report_registry.csv
─────────────────────────────────────────────────────────────────────────────
"""

import os
import logging
from datetime import datetime
import numpy as np
import pandas as pd

ROOT     = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
RAW_PATH = os.path.join(ROOT, 'data', 'raw',   'reportable_disease_registry.csv')
CLN_PATH = os.path.join(ROOT, 'data', 'clean', 'registry_clean.csv')
DQ_PATH  = os.path.join(ROOT, 'outputs', 'tables', 'dq_report_registry.csv')
LOG_PATH = os.path.join(ROOT, 'outputs', 'logs',   'pipeline_run_log.txt')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)-8s  %(message)s',
    handlers=[logging.FileHandler(LOG_PATH, mode='a'), logging.StreamHandler()]
)
log = logging.getLogger(__name__)
log.info("=" * 60)
log.info("START: 02_ingest_disease_registry.py")
log.info("=" * 60)

df = pd.read_csv(RAW_PATH, dtype=str)
log.info(f"Loaded {len(df):,} raw rows")

dq = []

# ── 1. Standardize dates (mixed formats) ────────────────────────────────────
def parse_date_mixed(s):
    """Try ISO 8601 first, then MM/DD/YYYY."""
    if pd.isna(s):
        return pd.NaT
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%d-%m-%Y'):
        try:
            return datetime.strptime(str(s).strip(), fmt)
        except ValueError:
            continue
    return pd.NaT

df['report_date_parsed'] = df['report_date'].apply(parse_date_mixed)
n_bad_dates = df['report_date_parsed'].isna().sum()
dq.append({'check': 'Unparseable report_date', 'n_affected': n_bad_dates,
           'action': 'Set to NULL'})
log.info(f"Date parsing: {len(df) - n_bad_dates}/{len(df)} parsed successfully")

# Count how many were in non-ISO format
n_non_iso = df['report_date'].str.contains('/', na=False).sum()
dq.append({'check': 'Non-ISO date formats (MM/DD/YYYY)', 'n_affected': int(n_non_iso),
           'action': 'Parsed and converted to ISO 8601'})

df['report_year'] = df['report_date_parsed'].apply(
    lambda d: d.year if pd.notna(d) else np.nan
)

# ── 2. Patient age ────────────────────────────────────────────────────────────
df['patient_age_num'] = pd.to_numeric(df['patient_age'], errors='coerce')
n_miss_age = df['patient_age_num'].isna().sum()
dq.append({'check': 'Missing patient_age', 'n_affected': int(n_miss_age),
           'action': 'Retained as NULL; flagged'})
df['age_missing'] = df['patient_age_num'].isna().astype(int)

# ── 3. Sex ────────────────────────────────────────────────────────────────────
valid_sex = {'Male', 'Female', 'Unknown'}
n_invalid_sex = (~df['patient_sex'].isin(valid_sex)).sum()
if n_invalid_sex:
    dq.append({'check': 'Invalid sex values', 'n_affected': int(n_invalid_sex),
               'action': 'Set to Unknown'})
    df['sex_clean'] = df['patient_sex'].where(df['patient_sex'].isin(valid_sex), 'Unknown')
else:
    df['sex_clean'] = df['patient_sex']
    dq.append({'check': 'Sex values', 'n_affected': 0, 'action': 'All valid — no action'})

# ── 4. Outbreak indicator ─────────────────────────────────────────────────────
df['is_outbreak_case'] = (~df['outbreak_id'].isna() & (df['outbreak_id'] != '')).astype(int)

# ── 5. Hospitalization and death binary ──────────────────────────────────────
for col, new_col in [('hospitalized', 'hospitalized_bin'), ('died', 'died_bin')]:
    df[new_col] = df[col].map({'Yes': 1, 'No': 0}).fillna(np.nan)

# ── 6. County FIPS zero-padding ───────────────────────────────────────────────
df['county_fips_clean'] = df['county_fips'].str.strip().str.zfill(5)

# ── 7. Condition name standardization ────────────────────────────────────────
df['condition_name_clean'] = df['condition_name'].str.strip().str.title()

# ── Save ──────────────────────────────────────────────────────────────────────
KEEP = [
    'case_id', 'report_date_parsed', 'report_year', 'condition_name_clean',
    'icd10_code', 'patient_age_num', 'sex_clean', 'county_fips_clean',
    'outbreak_id', 'is_outbreak_case', 'hospitalized', 'hospitalized_bin',
    'died', 'died_bin', 'source_lab', 'age_missing',
]
df_clean = df[KEEP].copy()
df_clean.columns = [
    'case_id', 'report_date', 'report_year', 'condition_name',
    'icd10_code', 'patient_age', 'sex', 'county_fips',
    'outbreak_id', 'is_outbreak_case', 'hospitalized', 'hospitalized_bin',
    'died', 'died_bin', 'source_lab', 'age_missing',
]
df_clean.to_csv(CLN_PATH, index=False)
log.info(f"Clean registry saved: {len(df_clean):,} rows")

pd.DataFrame(dq).assign(dataset='reportable_disease_registry',
                         run_timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        ).to_csv(DQ_PATH, index=False)
log.info("END: 02_ingest_disease_registry.py")
print(f"\n✓ Registry cleaning complete. {len(df_clean):,} records saved.")
