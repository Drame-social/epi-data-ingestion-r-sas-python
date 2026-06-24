# ============================================================================
# 01_ingest_hospital_discharge.R
# Project: Epidemiologic Data Ingestion Pipeline
# Purpose: R equivalent of Python 01_ingest_hospital_discharge.py
#          Cleans the raw hospital discharge records.
#
# Prerequisites: install.packages(c("tidyverse", "lubridate", "janitor"))
# Input:  data/raw/hospital_discharge_records.csv
# Output: data/clean/hospital_discharge_clean_r.csv
# ============================================================================

library(tidyverse)
library(lubridate)
library(janitor)

# ── Paths ─────────────────────────────────────────────────────────────────────
# Set this to your project root directory
PROJECT_ROOT <- here::here()  # works if using RStudio project; otherwise setwd() first
# Alternatively: PROJECT_ROOT <- "/path/to/project2_epi_data_ingestion"

raw_path <- file.path(PROJECT_ROOT, "data", "raw",   "hospital_discharge_records.csv")
cln_path <- file.path(PROJECT_ROOT, "data", "clean", "hospital_discharge_clean_r.csv")
dq_path  <- file.path(PROJECT_ROOT, "outputs", "tables", "dq_report_hospital_r.csv")

dir.create(dirname(cln_path), showWarnings = FALSE, recursive = TRUE)
dir.create(dirname(dq_path),  showWarnings = FALSE, recursive = TRUE)

# ── 1. Load ───────────────────────────────────────────────────────────────────
message("Loading raw hospital discharge data...")
df_raw <- read_csv(raw_path, col_types = cols(.default = "c"), show_col_types = FALSE)
n_raw  <- nrow(df_raw)
message(sprintf("  %s rows loaded", format(n_raw, big.mark = ",")))

dq_log <- tibble(check = character(), n_affected = integer(), action = character())

# ── 2. Deduplication ──────────────────────────────────────────────────────────
n_before <- nrow(df_raw)
df <- df_raw %>%
  group_by(mrn, admit_date) %>%
  slice(1) %>%
  ungroup()

n_removed <- n_before - nrow(df)
dq_log <- add_row(dq_log, check = "Duplicate MRN + admit_date",
                  n_affected = as.integer(n_removed),
                  action = "Removed; kept first occurrence")
message(sprintf("  Deduplication: removed %d duplicate rows", n_removed))

# ── 3. Parse dates ────────────────────────────────────────────────────────────
df <- df %>%
  mutate(
    admit_date_parsed    = ymd(admit_date,    quiet = TRUE),
    discharge_date_parsed = ymd(discharge_date, quiet = TRUE),
    los_days_num         = as.integer(los_days),
    los_calculated       = as.integer(discharge_date_parsed - admit_date_parsed),
    admit_year           = year(admit_date_parsed)
  )

n_bad_dates <- sum(is.na(df$admit_date_parsed))
dq_log <- add_row(dq_log, check = "Unparseable admit_date",
                  n_affected = as.integer(n_bad_dates), action = "Set to NA")

# ── 4. Clean age ──────────────────────────────────────────────────────────────
df <- df %>%
  mutate(
    patient_age_num   = suppressWarnings(as.integer(patient_age)),
    patient_age_clean = if_else(patient_age_num >= 0 & patient_age_num <= 120,
                                patient_age_num, NA_integer_),
    age_valid         = as.integer(!is.na(patient_age_clean))
  )

n_invalid_age <- sum(is.na(df$patient_age_clean) & !is.na(df$patient_age_num))
dq_log <- add_row(dq_log,
                  check = "Invalid age sentinels (999, -1) or out of range",
                  n_affected = as.integer(n_invalid_age), action = "Set to NA")

# ── 5. Standardize sex ────────────────────────────────────────────────────────
sex_map <- c(
  "M" = "Male",  "MALE" = "Male",  "Male" = "Male",  "1" = "Male",
  "F" = "Female","FEMALE" = "Female","Female" = "Female","2" = "Female",
  "U" = "Unknown","UNK" = "Unknown","Unknown" = "Unknown"
)
df <- df %>%
  mutate(sex_clean = coalesce(sex_map[str_trim(patient_sex)], "Unknown"))

n_sex_remap <- sum(df$sex_clean != str_trim(df$patient_sex), na.rm = TRUE)
dq_log <- add_row(dq_log, check = "Non-standard sex codes",
                  n_affected = as.integer(n_sex_remap),
                  action = "Standardized to Male/Female/Unknown")

# ── 6. ZIP validation ─────────────────────────────────────────────────────────
df <- df %>%
  mutate(
    patient_zip_clean = str_pad(str_trim(patient_zip), 5, "left", "0"),
    zip_valid         = as.integer(patient_zip_clean != "00000" &
                                   str_detect(patient_zip_clean, "^\\d{5}$"))
  )
n_bad_zip <- sum(df$zip_valid == 0)
dq_log <- add_row(dq_log, check = "Invalid ZIP codes",
                  n_affected = as.integer(n_bad_zip), action = "Flagged zip_valid=0")

# ── 7. ICD-10 chapter ─────────────────────────────────────────────────────────
icd_chapters <- c(
  A = "Infectious / Parasitic", B = "Infectious / Parasitic",
  C = "Neoplasms",              E = "Endocrine / Metabolic",
  I = "Circulatory",            J = "Respiratory",
  K = "Digestive",              N = "Genitourinary"
)
df <- df %>%
  mutate(icd10_chapter = coalesce(icd_chapters[str_sub(primary_dx_icd10, 1, 1)], "Other"))

# ── 8. Select and save ────────────────────────────────────────────────────────
df_clean <- df %>%
  select(
    mrn,
    admit_date       = admit_date_parsed,
    discharge_date   = discharge_date_parsed,
    los_days_recorded = los_days_num,
    los_days_calculated = los_calculated,
    primary_dx_icd10,
    secondary_dx_icd10,
    patient_age       = patient_age_clean,
    sex               = sex_clean,
    patient_zip       = patient_zip_clean,
    facility_id,
    admit_year,
    age_valid,
    zip_valid,
    icd10_chapter
  )

write_csv(df_clean, cln_path)
write_csv(dq_log %>% mutate(dataset = "hospital_discharge", run = Sys.time()), dq_path)

message(sprintf("✓ Clean hospital discharge dataset: %s rows saved to %s",
                format(nrow(df_clean), big.mark = ","), cln_path))
print(dq_log)
