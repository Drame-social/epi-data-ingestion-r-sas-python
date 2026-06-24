# ============================================================================
# 02_ingest_disease_registry.R
# Purpose: Clean the reportable disease registry; handle mixed date formats.
# Input:  data/raw/reportable_disease_registry.csv
# Output: data/clean/registry_clean_r.csv
# ============================================================================

library(tidyverse)
library(lubridate)

PROJECT_ROOT <- here::here()

raw_path <- file.path(PROJECT_ROOT, "data", "raw",   "reportable_disease_registry.csv")
cln_path <- file.path(PROJECT_ROOT, "data", "clean", "registry_clean_r.csv")

df_raw <- read_csv(raw_path, col_types = cols(.default = "c"), show_col_types = FALSE)
message(sprintf("Loaded %s registry rows", format(nrow(df_raw), big.mark = ",")))

# ── Parse mixed date formats ───────────────────────────────────────────────────
parse_mixed_date <- function(x) {
  # Try ISO 8601 first, then MM/DD/YYYY
  d <- parse_date_time(x, orders = c("Ymd", "mdy"), quiet = TRUE)
  as.Date(d)
}

df <- df_raw %>%
  mutate(
    report_date_parsed = parse_mixed_date(report_date),
    report_year        = year(report_date_parsed),
    patient_age_num    = suppressWarnings(as.numeric(patient_age)),
    age_missing        = as.integer(is.na(patient_age_num)),
    is_outbreak_case   = as.integer(!is.na(outbreak_id) & outbreak_id != ""),
    hospitalized_bin   = case_when(
      hospitalized == "Yes" ~ 1L,
      hospitalized == "No"  ~ 0L,
      TRUE ~ NA_integer_
    ),
    died_bin = case_when(
      died == "Yes" ~ 1L,
      died == "No"  ~ 0L,
      TRUE ~ NA_integer_
    ),
    county_fips_clean    = str_pad(str_trim(county_fips), 5, "left", "0"),
    condition_name_clean = str_to_title(str_trim(condition_name))
  )

n_bad_dates <- sum(is.na(df$report_date_parsed))
message(sprintf("  Date parsing: %d/%d successfully parsed", nrow(df) - n_bad_dates, nrow(df)))
message(sprintf("  Mixed format dates (MM/DD/YYYY): %d",
                sum(str_detect(df_raw$report_date, "/"), na.rm = TRUE)))

df_clean <- df %>%
  select(
    case_id,
    report_date     = report_date_parsed,
    report_year,
    condition_name  = condition_name_clean,
    icd10_code,
    patient_age     = patient_age_num,
    sex             = patient_sex,
    county_fips     = county_fips_clean,
    outbreak_id,
    is_outbreak_case,
    hospitalized,
    hospitalized_bin,
    died,
    died_bin,
    source_lab,
    age_missing
  )

write_csv(df_clean, cln_path)
message(sprintf("✓ Registry clean: %s rows → %s", format(nrow(df_clean), big.mark = ","), cln_path))
