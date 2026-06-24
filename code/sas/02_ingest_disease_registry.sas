/*=============================================================================
  02_ingest_disease_registry.sas
  --------------------------------
  Ingest and clean the reportable disease registry.

  Data quality issues addressed:
    1. Mixed date formats (YYYY-MM-DD and MM/DD/YYYY) → parse with ANYDTDTE
    2. Derive binary condition indicators from condition_name
    3. Validate county_fips format (5-digit string)

  Requirements
  ------------
  SAS 9.4 or later. Submit from project root directory.

  Input:   data/raw/reportable_disease_registry.csv
  Output:  data/clean/sas_disease_registry_clean.csv
=============================================================================*/

%let root = /path/to/project2_epi_data_ingestion;

/* ── 1. Import ───────────────────────────────────────────────────────────── */
proc import
    datafile = "&root./data/raw/reportable_disease_registry.csv"
    out      = work.reg_raw
    dbms     = csv
    replace;
    getnames = yes;
    guessingrows = 100;
run;

/* ── 2. Parse mixed-format report_date ─────────────────────────────────── */
data work.reg_dates;
    set work.reg_raw;
    report_date_dt = input(report_date, anydtdte20.);
    format report_date_dt date9.;
    report_year  = year(report_date_dt);
    report_month = month(report_date_dt);

    /* Flag unparseable dates */
    if missing(report_date_dt) then date_parse_error = 1;
    else date_parse_error = 0;
run;

/* ── 3. Validate county_fips (should be 5-character numeric string) ──────── */
data work.reg_fips;
    set work.reg_dates;
    if length(strip(county_fips)) = 5 and notdigit(compress(county_fips)) = 0
        then fips_valid = 1;
    else fips_valid = 0;
run;

/* ── 4. Derive binary condition indicators ────────────────────────────────── */
data work.reg_clean;
    set work.reg_fips;
    length condition_clean $30;
    condition_clean = propcase(strip(condition_name));

    /* Binary flags for common conditions */
    is_salmonella    = (index(upcase(condition_name),'SALMONELLA')    > 0);
    is_campylobacter = (index(upcase(condition_name),'CAMPYLOBACTER') > 0);
    is_ecoli         = (index(upcase(condition_name),'COLI')          > 0);
    is_listeria      = (index(upcase(condition_name),'LISTERIA')      > 0);
    is_hepatitis_a   = (index(upcase(condition_name),'HEPATITIS A')   > 0);
    is_shigella      = (index(upcase(condition_name),'SHIGELLA')      > 0);
    is_vibrio        = (index(upcase(condition_name),'VIBRIO')        > 0);
run;

/* ── 5. QC summary ───────────────────────────────────────────────────────── */
proc freq data=work.reg_clean;
    tables date_parse_error fips_valid condition_clean / missing;
    title "Registry: QC distributions";
run;

proc means data=work.reg_clean n nmiss;
    var report_year report_month;
    title "Registry: year/month distribution";
run;
title;

/* ── 6. Export ───────────────────────────────────────────────────────────── */
proc export
    data    = work.reg_clean
    outfile = "&root./data/clean/sas_disease_registry_clean.csv"
    dbms    = csv
    replace;
run;

%put NOTE: 02_ingest_disease_registry.sas completed successfully.;
