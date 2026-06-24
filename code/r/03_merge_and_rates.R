# ============================================================================
# 03_merge_and_rates.R
# Purpose: Merge registry with denominators; compute incidence rates.
# Inputs:  data/clean/registry_clean_r.csv
#          data/raw/population_denominators.csv
# Output:  data/clean/master_incidence_dataset_r.csv
#          outputs/tables/summary_by_condition_r.csv
# ============================================================================

library(tidyverse)

PROJECT_ROOT <- here::here()

reg <- read_csv(file.path(PROJECT_ROOT, "data", "clean", "registry_clean_r.csv"),
                show_col_types = FALSE) %>%
  mutate(county_fips = str_pad(county_fips, 5, "left", "0"))

pop <- read_csv(file.path(PROJECT_ROOT, "data", "raw", "population_denominators.csv"),
                col_types = cols(county_fips = "c"), show_col_types = FALSE) %>%
  mutate(county_fips = str_pad(county_fips, 5, "left", "0"))

message(sprintf("Registry: %s rows | Denominators: %s rows",
                format(nrow(reg), big.mark = ","),
                format(nrow(pop), big.mark = ",")))

# ── Aggregate to county × year × condition ────────────────────────────────────
agg <- reg %>%
  filter(!is.na(report_year)) %>%
  group_by(county_fips, year = as.integer(report_year), condition_name) %>%
  summarise(
    case_count     = n(),
    hospitalized_n = sum(hospitalized_bin, na.rm = TRUE),
    died_n         = sum(died_bin,         na.rm = TRUE),
    outbreak_cases = sum(is_outbreak_case, na.rm = TRUE),
    .groups = "drop"
  )

# ── Merge denominators ────────────────────────────────────────────────────────
merged <- agg %>%
  left_join(pop %>% select(county_fips, year, population_total), by = c("county_fips", "year")) %>%
  mutate(
    incidence_rate_100k = round(case_count / population_total * 100000, 2),
    hospitalized_pct    = round(hospitalized_n / case_count * 100, 1),
    case_fatality_pct   = round(died_n         / case_count * 100, 2)
  )

n_no_denom <- sum(is.na(merged$population_total))
if (n_no_denom > 0) message(sprintf("WARNING: %d rows with no matching denominator", n_no_denom))

write_csv(merged,
          file.path(PROJECT_ROOT, "data", "clean", "master_incidence_dataset_r.csv"))

# ── Summary by condition ──────────────────────────────────────────────────────
cond_summary <- merged %>%
  group_by(condition_name) %>%
  summarise(
    total_cases          = sum(case_count),
    total_hospitalized   = sum(hospitalized_n),
    total_deaths         = sum(died_n),
    mean_rate_100k       = round(mean(incidence_rate_100k, na.rm = TRUE), 2),
    hospitalization_rate = round(total_hospitalized / total_cases * 100, 1),
    case_fatality_rate   = round(total_deaths / total_cases * 100, 2),
    .groups = "drop"
  ) %>%
  arrange(desc(total_cases))

write_csv(cond_summary,
          file.path(PROJECT_ROOT, "outputs", "tables", "summary_by_condition_r.csv"))

message("Condition summary:")
print(cond_summary %>% select(condition_name, total_cases, hospitalization_rate, case_fatality_rate))
message("✓ R pipeline complete.")
