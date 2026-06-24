"""
04_summary_outputs.py
─────────────────────────────────────────────────────────────────────────────
Purpose : Generate summary visualizations from the master incidence dataset.

Inputs  : data/clean/master_incidence_dataset.csv
          outputs/tables/summary_by_condition.csv
Outputs : outputs/figures/fig1_incidence_by_condition.png
          outputs/figures/fig2_hospitalization_by_condition.png
          outputs/figures/fig3_annual_trends.png
─────────────────────────────────────────────────────────────────────────────
"""

import os
import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

warnings.filterwarnings('ignore')

ROOT    = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
MST_PATH = os.path.join(ROOT, 'data', 'clean', 'master_incidence_dataset.csv')
SUM_PATH = os.path.join(ROOT, 'outputs', 'tables', 'summary_by_condition.csv')
FIG_DIR  = os.path.join(ROOT, 'outputs', 'figures')
os.makedirs(FIG_DIR, exist_ok=True)

master = pd.read_csv(MST_PATH)
cond   = pd.read_csv(SUM_PATH).sort_values('mean_rate_100k', ascending=True)

PALETTE = ['#4393c3', '#d6604d', '#74add1', '#f46d43', '#abd9e9',
           '#fdae61', '#fee090', '#e0f3f8']

# ── Figure 1: Mean incidence rate by condition ────────────────────────────────
fig, ax = plt.subplots(figsize=(10, 6))
colors = PALETTE[:len(cond)]
ax.barh(cond['condition_name'], cond['mean_rate_100k'], color=colors, alpha=0.85, edgecolor='white')
ax.set_xlabel('Mean Annual Incidence Rate per 100,000 Population', fontsize=11)
ax.set_title('Mean Annual Incidence Rate by Reportable Condition\n(Synthetic Data — Illustrative Only)',
             fontsize=12, fontweight='bold')
ax.spines[['top', 'right']].set_visible(False)
for i, (rate, cases) in enumerate(zip(cond['mean_rate_100k'], cond['total_cases'])):
    ax.text(rate + 0.05, i, f'{rate:.1f}  (n={cases})', va='center', fontsize=9)
plt.tight_layout()
fig.savefig(os.path.join(FIG_DIR, 'fig1_incidence_by_condition.png'), dpi=150, bbox_inches='tight')
plt.close()
print("Figure 1 saved.")

# ── Figure 2: Hospitalization and case fatality rates ────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(13, 6))
fig.suptitle('Hospitalization and Case Fatality Rates by Condition\n(Synthetic Data)',
             fontsize=12, fontweight='bold')

cond_h = cond.sort_values('hospitalization_rate')
axes[0].barh(cond_h['condition_name'], cond_h['hospitalization_rate'],
             color='#4393c3', alpha=0.85, edgecolor='white')
axes[0].set_xlabel('Hospitalization Rate (%)', fontsize=11)
axes[0].set_title('Hospitalization Rate')
axes[0].spines[['top', 'right']].set_visible(False)

cond_d = cond.sort_values('case_fatality_rate')
axes[1].barh(cond_d['condition_name'], cond_d['case_fatality_rate'],
             color='#d6604d', alpha=0.85, edgecolor='white')
axes[1].set_xlabel('Case Fatality Rate (%)', fontsize=11)
axes[1].set_title('Case Fatality Rate')
axes[1].spines[['top', 'right']].set_visible(False)

plt.tight_layout()
fig.savefig(os.path.join(FIG_DIR, 'fig2_hospitalization_cfr.png'), dpi=150, bbox_inches='tight')
plt.close()
print("Figure 2 saved.")

# ── Figure 3: Annual case counts by condition (trend lines) ───────────────────
annual = (
    master
    .groupby(['year', 'condition_name'])
    ['case_count'].sum()
    .reset_index()
    .dropna(subset=['year'])
)
annual['year'] = annual['year'].astype(int)

fig, ax = plt.subplots(figsize=(11, 6))
for i, cond_name in enumerate(annual['condition_name'].unique()):
    d = annual[annual['condition_name'] == cond_name].sort_values('year')
    ax.plot(d['year'], d['case_count'], marker='o', linewidth=2,
            label=cond_name, color=PALETTE[i % len(PALETTE)])

ax.set_xlabel('Year', fontsize=11)
ax.set_ylabel('Total Case Count', fontsize=11)
ax.set_title('Annual Case Counts by Reportable Condition (2020–2023)\n(Synthetic Data)',
             fontsize=12, fontweight='bold')
ax.legend(loc='upper right', fontsize=8, ncol=2)
ax.set_xticks(sorted(annual['year'].unique()))
ax.spines[['top', 'right']].set_visible(False)
plt.tight_layout()
fig.savefig(os.path.join(FIG_DIR, 'fig3_annual_trends.png'), dpi=150, bbox_inches='tight')
plt.close()
print("Figure 3 saved.")

print("\n✓ Summary outputs complete.")
