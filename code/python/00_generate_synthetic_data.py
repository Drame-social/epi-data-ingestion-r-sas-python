"""
00_generate_synthetic_data.py
─────────────────────────────────────────────────────────────────────────────
Purpose : Reproduce all three raw synthetic datasets used in the EPI data
          ingestion pipeline project.

Design  : The 50-county FIPS universe (01001–01050) is shared across all
          three datasets so that the registry↔denominator merge succeeds
          at a realistic match rate.

Intentional data quality issues introduced for demonstration:
  Hospital discharge: ~5% true MRN+admit_date duplicates (same MRN AND same
                      date — representing a billing system re-submission),
                      25 invalid age sentinels (999, -1), non-standard sex
                      codes (M/Male/1/MALE), 25 invalid ZIPs (00000)
  Disease registry  : ~115 dates in MM/DD/YYYY format instead of ISO 8601

Outputs : data/raw/hospital_discharge_records.csv   (1,500 rows, ~75 dups)
          data/raw/reportable_disease_registry.csv   (800 rows)
          data/raw/population_denominators.csv        (200 rows)

Seed    : 123 (fully reproducible)
Run     : python code/python/00_generate_synthetic_data.py
─────────────────────────────────────────────────────────────────────────────
"""

import os
import random
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

SEED = 123
np.random.seed(SEED)
random.seed(SEED)

ROOT    = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
RAW_DIR = os.path.join(ROOT, 'data', 'raw')
os.makedirs(RAW_DIR, exist_ok=True)

START = datetime(2020, 1, 1)

# ── Shared county universe ────────────────────────────────────────────────────
# 50 counties, FIPS 01001–01050.  All three datasets draw from this set so
# that the registry↔denominator merge joins cleanly.
COUNTY_FIPS_STR = [f'{c:05d}' for c in range(1001, 1051)]


# ── Dataset 1: Hospital discharge records ────────────────────────────────────
N_HOSP = 1_500

ICD10_CODES = {
    'J18.9':  'Pneumonia, unspecified',
    'J45.20': 'Mild intermittent asthma',
    'E11.9':  'Type 2 diabetes mellitus without complications',
    'I10':    'Essential (primary) hypertension',
    'I25.10': 'Atherosclerotic heart disease of native coronary artery',
    'J44.1':  'COPD with acute exacerbation',
    'N18.3':  'Chronic kidney disease, stage 3',
    'C34.10': 'Malignant neoplasm of upper lobe, bronchus or lung',
}
codes = list(ICD10_CODES.keys())

admit_dates     = [START + timedelta(days=random.randint(0, 1460)) for _ in range(N_HOSP)]
los_days        = (np.random.negative_binomial(3, 0.4, N_HOSP) + 1).astype(int)
discharge_dates = [admit_dates[i] + timedelta(days=int(los_days[i])) for i in range(N_HOSP)]
mrns            = [f'MRN{i + 1:06d}' for i in range(N_HOSP)]

# Introduce ~5% true MRN + admit_date duplicates (DQ issue #1)
# A duplicate is a row where both MRN and admit_date match an existing row,
# simulating a re-submitted or duplicated billing record.
N_DUPS = 75
dup_source_idx = np.random.choice(N_HOSP - N_DUPS, N_DUPS, replace=False)
for k, src in enumerate(dup_source_idx):
    tgt = N_HOSP - N_DUPS + k          # overwrite last 75 rows
    mrns[tgt]          = mrns[src]      # copy MRN
    admit_dates[tgt]   = admit_dates[src]   # copy SAME admit_date → true duplicate
    discharge_dates[tgt] = discharge_dates[src]
    los_days[tgt]      = los_days[src]

primary_dx   = np.random.choice(codes, N_HOSP)
secondary_dx = [
    np.random.choice([c for c in codes if c != primary_dx[i]] + [None, None])
    for i in range(N_HOSP)
]

# Age: valid range 18–89, with intentional sentinels (DQ issue #2)
ages_raw = np.random.randint(18, 90, N_HOSP).astype(object)
ages_raw[np.random.choice(N_HOSP, 15, replace=False)] = 999   # high sentinel
ages_raw[np.random.choice(N_HOSP, 10, replace=False)] = -1    # negative sentinel

# Sex: non-standard coding mixed in (DQ issue #3)
sex_raw = np.random.choice(['M', 'F', 'U'], N_HOSP, p=[0.47, 0.51, 0.02]).astype(object)
for i in np.random.choice(N_HOSP, 20, replace=False):
    sex_raw[i] = np.random.choice(['Male', 'Female', '1', '2', 'MALE'])

# ZIP codes: mostly valid, ~25 invalid (DQ issue #4)
zip_codes = [f'{np.random.randint(10_000, 99_999):05d}' for _ in range(N_HOSP)]
for i in np.random.choice(N_HOSP, 25, replace=False):
    zip_codes[i] = '00000'

facilities = [f'FAC{i:03d}' for i in range(1, 21)]
hosp_fips  = np.random.choice(COUNTY_FIPS_STR, N_HOSP)

df_hosp = pd.DataFrame({
    'mrn':                mrns,
    'admit_date':         [d.strftime('%Y-%m-%d') for d in admit_dates],
    'discharge_date':     [d.strftime('%Y-%m-%d') for d in discharge_dates],
    'los_days':           los_days,
    'primary_dx_icd10':   primary_dx,
    'secondary_dx_icd10': secondary_dx,
    'patient_age':        ages_raw,
    'patient_sex':        sex_raw,
    'patient_zip':        zip_codes,
    'facility_id':        np.random.choice(facilities, N_HOSP),
    'county_fips':        hosp_fips,
})
hosp_path = os.path.join(RAW_DIR, 'hospital_discharge_records.csv')
df_hosp.to_csv(hosp_path, index=False)
n_dups_actual = df_hosp.duplicated(subset=['mrn', 'admit_date']).sum()
print(f"✓ hospital_discharge_records.csv  ({len(df_hosp):,} rows, {n_dups_actual} MRN+date duplicates)")


# ── Dataset 2: Reportable disease registry ───────────────────────────────────
N_REG = 800

CONDITIONS = [
    ('Salmonella',      'A02.0'),
    ('Campylobacter',   'A04.5'),
    ('Shigella',        'A03.9'),
    ('Hepatitis A',     'B15.9'),
    ('Listeria',        'A32.9'),
    ('E. coli O157:H7', 'A04.3'),
    ('Cryptosporidium', 'A07.2'),
    ('Vibrio',          'A05.4'),
]
cond_names   = [c[0] for c in CONDITIONS]
cond_codes   = [c[1] for c in CONDITIONS]
cond_indices = np.random.choice(len(CONDITIONS), N_REG)

report_dates = [START + timedelta(days=random.randint(0, 1460)) for _ in range(N_REG)]
# Mixed date formats: every 7th row uses MM/DD/YYYY instead of ISO 8601 (DQ issue #5)
report_dates_raw = [
    d.strftime('%m/%d/%Y') if i % 7 == 0 else d.strftime('%Y-%m-%d')
    for i, d in enumerate(report_dates)
]

case_ids  = [f'CASE{i + 1:07d}' for i in range(N_REG)]
ages_lab  = np.random.randint(0, 90, N_REG).astype(object)
ages_lab[np.random.choice(N_REG, 10, replace=False)] = np.nan

reg_fips     = np.random.choice(COUNTY_FIPS_STR, N_REG)
outbreak_ids = list(np.random.choice(
    [f'OB{i:04d}' for i in range(1, 12)] + [None] * 5, N_REG
))

df_reg = pd.DataFrame({
    'case_id':      case_ids,
    'report_date':  report_dates_raw,
    'condition_name': [cond_names[i] for i in cond_indices],
    'icd10_code':   [cond_codes[i] for i in cond_indices],
    'patient_age':  ages_lab,
    'patient_sex':  np.random.choice(['Male', 'Female', 'Unknown'], N_REG, p=[0.48, 0.50, 0.02]),
    'county_fips':  reg_fips,
    'outbreak_id':  outbreak_ids,
    'hospitalized': np.random.choice(['Yes', 'No', 'Unknown'], N_REG, p=[0.30, 0.65, 0.05]),
    'died':         np.random.choice(['Yes', 'No', 'Unknown'], N_REG, p=[0.03, 0.95, 0.02]),
    'source_lab':   np.random.choice(
                        ['State Lab', 'Private Lab A', 'Private Lab B', 'Hospital Lab'], N_REG
                    ),
})
reg_path = os.path.join(RAW_DIR, 'reportable_disease_registry.csv')
df_reg.to_csv(reg_path, index=False)
n_mixed_dates = sum(1 for d in report_dates_raw if '/' in d)
print(f"✓ reportable_disease_registry.csv ({len(df_reg):,} rows, {n_mixed_dates} mixed-format dates)")


# ── Dataset 3: Population denominators ───────────────────────────────────────
YEARS    = [2020, 2021, 2022, 2023]
pop_rows = []
for county_str in COUNTY_FIPS_STR:
    base_pop = int(np.random.uniform(5_000, 250_000))
    for year in YEARS:
        total = int(base_pop * (1 + np.random.uniform(0, 0.02)) ** (year - 2020))
        pop_rows.append({
            'county_fips':        county_str,
            'year':               year,
            'population_total':   total,
            'population_male':    int(total * np.random.uniform(0.48, 0.52)),
            'population_female':  int(total * np.random.uniform(0.48, 0.52)),
            'population_under18': int(total * np.random.uniform(0.20, 0.28)),
            'population_65plus':  int(total * np.random.uniform(0.12, 0.20)),
            'data_source':        'US Census ACS 5-Year Estimates (Simulated)',
        })

df_pop = pd.DataFrame(pop_rows)
pop_path = os.path.join(RAW_DIR, 'population_denominators.csv')
df_pop.to_csv(pop_path, index=False)
print(f"✓ population_denominators.csv     ({len(df_pop):,} rows, "
      f"{df_pop['county_fips'].nunique()} counties × {len(YEARS)} years)")
print("\n✓ All synthetic datasets generated successfully (seed=123).")
