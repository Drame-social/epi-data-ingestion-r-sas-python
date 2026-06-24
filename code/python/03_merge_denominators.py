"""
03_merge_denominators.py
─────────────────────────────────────────────────────────────────────────────
Purpose : Merge the clean disease registry with population denominators to
          compute annual incidence rates by county, year, and condition.

Inputs  : data/clean/registry_clean.csv
          data/raw/population_denominators.csv
Outputs : data/clean/master_incidence_dataset.csv
          outputs/tables/incidence_rates_by_county_year.csv
          outputs/tables/summary_by_condition.csv
─────────────────────────────────────────────────────────────────────────────
"""

import os
import logging
import numpy as np
import pandas as pd

ROOT    = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
REG_PATH = os.path.join(ROOT, 'data', 'clean', 'registry_clean.csv')
POP_PATH = os.path.join(ROOT, 'data', 'raw',   'population_denominators.csv')
MST_PATH = os.path.join(ROOT, 'data', 'clean', 'master_incidence_dataset.csv')
TBL_DIR  = os.path.join(ROOT, 'outputs', 'tables')
LOG_PATH = os.path.join(ROOT, 'outputs', 'logs',  'pipeline_run_log.txt')
os.makedirs(TBL_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)-8s  %(message)s',
    handlers=[logging.FileHandler(LOG_PATH, mode='a'), logging.StreamHandler()]
)
log = logging.getLogger(__name__)
log.info("=" * 60)
log.info("START: 03_merge_denominators.py")
log.info("=" * 60)

# ── 1. Load ───────────────────────────────────────────────────────────────────
reg = pd.read_csv(REG_PATH)
pop = pd.read_csv(POP_PATH, dtype={'county_fips': str})
pop['county_fips'] = pop['county_fips'].str.zfill(5)

reg['report_year']  = pd.to_numeric(reg['report_year'],  errors='coerce').astype('Int64')
reg['county_fips']  = reg['county_fips'].astype(str).str.zfill(5)

log.info(f"Registry: {len(reg):,} rows")
log.info(f"Denominators: {len(pop):,} rows ({pop['county_fips'].nunique()} counties, {pop['year'].nunique()} years)")

# ── 2. Aggregate registry to county × year × condition ───────────────────────
agg = (
    reg
    .groupby(['county_fips', 'report_year', 'condition_name'])
    .agg(
        case_count        = ('case_id', 'count'),
        hospitalized_n    = ('hospitalized_bin', lambda x: x.sum(skipna=True)),
        hospitalized_unk  = ('hospitalized_bin', lambda x: x.isna().sum()),
        died_n            = ('died_bin', lambda x: x.sum(skipna=True)),
        died_unk          = ('died_bin', lambda x: x.isna().sum()),
        outbreak_cases    = ('is_outbreak_case', 'sum'),
    )
    .reset_index()
    .rename(columns={'report_year': 'year'})
)
log.info(f"Aggregated: {len(agg):,} county × year × condition rows")

# ── 3. Merge with population denominators ────────────────────────────────────
merged = agg.merge(
    pop[['county_fips', 'year', 'population_total']],
    on=['county_fips', 'year'],
    how='left'
)
n_no_denom = merged['population_total'].isna().sum()
if n_no_denom:
    log.warning(f"{n_no_denom} rows have no matching denominator — rates will be NULL")

# ── 4. Compute rates ──────────────────────────────────────────────────────────
merged['incidence_rate_100k'] = (
    merged['case_count'] / merged['population_total'] * 100_000
).round(2)
merged['hospitalized_pct'] = (
    merged['hospitalized_n'] / merged['case_count'] * 100
).round(1)
merged['case_fatality_pct'] = (
    merged['died_n'] / merged['case_count'] * 100
).round(2)

merged.to_csv(MST_PATH, index=False)
log.info(f"Master incidence dataset saved: {len(merged):,} rows → {MST_PATH}")

# ── 5. Summary tables ─────────────────────────────────────────────────────────
# Table A: rates by county + year (all conditions combined)
county_year = (
    merged
    .groupby(['county_fips', 'year'])
    .agg(
        total_cases           = ('case_count', 'sum'),
        population_total      = ('population_total', 'first'),
        total_hospitalized    = ('hospitalized_n', 'sum'),
        total_deaths          = ('died_n', 'sum'),
    )
    .reset_index()
)
county_year['all_condition_rate_100k'] = (
    county_year['total_cases'] / county_year['population_total'] * 100_000
).round(2)
county_year.to_csv(os.path.join(TBL_DIR, 'incidence_rates_by_county_year.csv'), index=False)

# Table B: summary by condition
cond_summary = (
    merged
    .groupby('condition_name')
    .agg(
        total_cases        = ('case_count', 'sum'),
        total_hospitalized = ('hospitalized_n', 'sum'),
        total_deaths       = ('died_n', 'sum'),
        n_county_years     = ('county_fips', 'count'),
        mean_rate_100k     = ('incidence_rate_100k', 'mean'),
    )
    .reset_index()
    .sort_values('total_cases', ascending=False)
)
cond_summary['mean_rate_100k'] = cond_summary['mean_rate_100k'].round(2)
cond_summary['hospitalization_rate'] = (
    cond_summary['total_hospitalized'] / cond_summary['total_cases'] * 100
).round(1)
cond_summary['case_fatality_rate'] = (
    cond_summary['total_deaths'] / cond_summary['total_cases'] * 100
).round(2)
cond_summary.to_csv(os.path.join(TBL_DIR, 'summary_by_condition.csv'), index=False)

print("\nCondition summary:")
print(cond_summary[['condition_name','total_cases','hospitalization_rate','case_fatality_rate']].to_string(index=False))
log.info("END: 03_merge_denominators.py")
print(f"\n✓ Merge and rate calculation complete.")
