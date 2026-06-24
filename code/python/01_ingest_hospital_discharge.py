"""
01_ingest_hospital_discharge.py
─────────────────────────────────────────────────────────────────────────────
Purpose : Ingest, validate, clean, and standardize the raw hospital discharge
          records.  Resolves all known data quality issues and produces a
          clean CSV with a companion data quality report.

Data quality issues resolved:
  - Duplicate MRNs (deduplication by MRN + admit_date)
  - Invalid age sentinels (999, -1) → NULL
  - Inconsistent sex coding → Male / Female / Unknown
  - Invalid ZIP codes (00000) → flagged
  - Date type casting and LOS cross-check

Input   : data/raw/hospital_discharge_records.csv
Outputs : data/clean/hospital_discharge_clean.csv
          outputs/tables/dq_report_hospital_discharge.csv
          outputs/logs/pipeline_run_log.txt  (appended)
─────────────────────────────────────────────────────────────────────────────
"""

import os
import logging
from datetime import datetime
import numpy as np
import pandas as pd

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT     = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
RAW_PATH = os.path.join(ROOT, 'data', 'raw',   'hospital_discharge_records.csv')
CLN_PATH = os.path.join(ROOT, 'data', 'clean', 'hospital_discharge_clean.csv')
DQ_PATH  = os.path.join(ROOT, 'outputs', 'tables', 'dq_report_hospital_discharge.csv')
LOG_PATH = os.path.join(ROOT, 'outputs', 'logs',   'pipeline_run_log.txt')
for d in [os.path.dirname(CLN_PATH), os.path.dirname(DQ_PATH), os.path.dirname(LOG_PATH)]:
    os.makedirs(d, exist_ok=True)

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)-8s  %(message)s',
    handlers=[
        logging.FileHandler(LOG_PATH, mode='a'),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger(__name__)
log.info("=" * 60)
log.info("START: 01_ingest_hospital_discharge.py")
log.info("=" * 60)

# ── 1. Load ────────────────────────────────────────────────────────────────────
df = pd.read_csv(RAW_PATH, dtype=str)   # read everything as string first
n_raw = len(df)
log.info(f"Loaded {n_raw:,} raw rows from {RAW_PATH}")

# ── DQ tracking ───────────────────────────────────────────────────────────────
dq = []
def record_dq(check, n_affected, action):
    dq.append({'check': check, 'n_affected': n_affected, 'action': action})
    log.info(f"DQ | {check}: {n_affected} rows → {action}")

# ── 2. Deduplication ──────────────────────────────────────────────────────────
n_before = len(df)
df['_dup'] = df.duplicated(subset=['mrn', 'admit_date'], keep='first')
n_dups = df['_dup'].sum()
record_dq('Duplicate MRN + admit_date', n_dups, 'Removed; keep first occurrence')
df = df[~df['_dup']].drop(columns=['_dup']).reset_index(drop=True)
log.info(f"After deduplication: {len(df):,} rows (removed {n_dups})")

# ── 3. Parse dates ────────────────────────────────────────────────────────────
df['admit_date_parsed']    = pd.to_datetime(df['admit_date'],    errors='coerce')
df['discharge_date_parsed']= pd.to_datetime(df['discharge_date'], errors='coerce')
n_bad_admit    = df['admit_date_parsed'].isna().sum()
n_bad_discharge= df['discharge_date_parsed'].isna().sum()
if n_bad_admit:
    record_dq('Unparseable admit_date', n_bad_admit, 'Set to NULL')
if n_bad_discharge:
    record_dq('Unparseable discharge_date', n_bad_discharge, 'Set to NULL')

# Cross-check LOS
df['los_days'] = pd.to_numeric(df['los_days'], errors='coerce')
df['los_calculated'] = (df['discharge_date_parsed'] - df['admit_date_parsed']).dt.days
los_mismatch = ((df['los_calculated'].notna()) &
                (df['los_days'].notna()) &
                (df['los_calculated'] != df['los_days'])).sum()
if los_mismatch:
    record_dq('LOS mismatch (calculated vs. recorded)', los_mismatch,
              'Use calculated LOS; flag for review')

df['admit_year'] = df['admit_date_parsed'].dt.year

# ── 4. Clean patient age ──────────────────────────────────────────────────────
df['patient_age_num'] = pd.to_numeric(df['patient_age'], errors='coerce')
invalid_ages = ((df['patient_age_num'] < 0) | (df['patient_age_num'] > 120)).sum()
record_dq('Invalid age (< 0 or > 120; includes sentinels 999, -1)',
          invalid_ages, 'Set to NULL')
df['patient_age_clean'] = np.where(
    (df['patient_age_num'] >= 0) & (df['patient_age_num'] <= 120),
    df['patient_age_num'], np.nan
)
df['age_valid'] = df['patient_age_clean'].notna().astype(int)

# ── 5. Standardize sex ────────────────────────────────────────────────────────
SEX_MAP = {
    'M':      'Male',   'MALE':   'Male',   'Male':   'Male',   '1': 'Male',
    'F':      'Female', 'FEMALE': 'Female', 'Female': 'Female', '2': 'Female',
    'U':      'Unknown','UNK':    'Unknown','Unknown':'Unknown',
}
df['sex_clean'] = df['patient_sex'].str.strip().map(SEX_MAP).fillna('Unknown')
n_sex_changed = (df['sex_clean'] != df['patient_sex'].str.strip()).sum()
record_dq('Non-standard sex codes', n_sex_changed,
          f'Standardized to Male/Female/Unknown via mapping')

# ── 6. Validate ZIP codes ─────────────────────────────────────────────────────
df['patient_zip_clean'] = df['patient_zip'].str.strip().str.zfill(5)
invalid_zip = ((df['patient_zip_clean'] == '00000') |
               (~df['patient_zip_clean'].str.match(r'^\d{5}$'))).sum()
record_dq('Invalid ZIP codes (00000 or non-numeric)', invalid_zip,
          'Flag zip_valid=0; retain original value')
df['zip_valid'] = np.where(
    (df['patient_zip_clean'] != '00000') & df['patient_zip_clean'].str.match(r'^\d{5}$'),
    1, 0
)

# ── 7. ICD-10 chapter ────────────────────────────────────────────────────────
ICD_CHAPTER = {
    'A': 'Infectious / Parasitic', 'B': 'Infectious / Parasitic',
    'C': 'Neoplasms',              'D': 'Blood / Immune',
    'E': 'Endocrine / Metabolic',  'F': 'Mental / Behavioral',
    'G': 'Nervous System',         'H': 'Eye / Ear',
    'I': 'Circulatory',            'J': 'Respiratory',
    'K': 'Digestive',              'L': 'Skin',
    'M': 'Musculoskeletal',        'N': 'Genitourinary',
    'O': 'Pregnancy',              'P': 'Perinatal',
    'Q': 'Congenital',             'R': 'Symptoms / Signs',
    'S': 'Injury / Poisoning',     'T': 'Injury / Poisoning',
    'Z': 'Factors / Health Status',
}
df['icd10_chapter'] = (df['primary_dx_icd10']
                       .str[0].str.upper()
                       .map(ICD_CHAPTER)
                       .fillna('Unknown'))

# ── 8. Build final clean dataset ─────────────────────────────────────────────
KEEP = [
    'mrn', 'admit_date_parsed', 'discharge_date_parsed', 'los_days',
    'los_calculated', 'primary_dx_icd10', 'secondary_dx_icd10',
    'patient_age_clean', 'sex_clean', 'patient_zip_clean', 'facility_id',
    'admit_year', 'age_valid', 'zip_valid', 'icd10_chapter',
]
df_clean = df[KEEP].copy()
df_clean.columns = [
    'mrn', 'admit_date', 'discharge_date', 'los_days_recorded',
    'los_days_calculated', 'primary_dx_icd10', 'secondary_dx_icd10',
    'patient_age', 'sex', 'patient_zip', 'facility_id',
    'admit_year', 'age_valid', 'zip_valid', 'icd10_chapter',
]

df_clean.to_csv(CLN_PATH, index=False)
log.info(f"Clean dataset saved: {len(df_clean):,} rows → {CLN_PATH}")

# ── 9. DQ report ──────────────────────────────────────────────────────────────
dq_df = pd.DataFrame(dq)
dq_df.insert(0, 'dataset', 'hospital_discharge')
dq_df['run_timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
dq_df.to_csv(DQ_PATH, index=False)

log.info("Data quality summary:")
for _, row in dq_df.iterrows():
    log.info(f"  {row['check']}: n={row['n_affected']} → {row['action']}")

log.info("END: 01_ingest_hospital_discharge.py")
print(f"\n✓ Hospital discharge cleaning complete. {len(df_clean):,} records saved.")
