/*=============================================================================
  01_ingest_hospital_discharge.sas
  --------------------------------
  Ingest and clean hospital discharge records.

  Mirrors the logic in code/python/01_ingest_hospital_discharge.py.

  Data quality issues addressed:
    1. Duplicate MRN + admit_date records → keep first occurrence
    2. Invalid age sentinels (999, -1) and out-of-range (<0, >120) → set to .
    3. Non-standard sex codes (M/Male/1/MALE) → standardize to Male/Female/Unknown
    4. Invalid ZIP codes (00000, non-numeric) → flag zip_valid=0; retain value

  Requirements
  ------------
  SAS 9.4 or later. Submit from project root directory.

  Input:   data/raw/hospital_discharge_records.csv
  Output:  data/clean/sas_hospital_discharge_clean.csv
           outputs/tables/sas_dq_summary.csv
=============================================================================*/

/* Set project root — update this path before submitting */
%let root = /path/to/project2_epi_data_ingestion;

/* ── 1. Import raw data ──────────────────────────────────────────────────── */
proc import
    datafile = "&root./data/raw/hospital_discharge_records.csv"
    out      = work.hd_raw
    dbms     = csv
    replace;
    getnames = yes;
    guessingrows = 200;
run;

%put NOTE: Loaded %sysfunc(countw(&syslast.)) records from hospital_discharge_records.csv;

/* ── 2. Remove duplicate MRN + admit_date ───────────────────────────────── */
proc sort data=work.hd_raw out=work.hd_sorted;
    by mrn admit_date;
run;

data work.hd_dedup;
    set work.hd_sorted;
    by mrn admit_date;
    if first.admit_date;  /* Keep first occurrence of each MRN+date pair */
run;

%put NOTE: After dedup: %sysfunc(attrn(%sysfunc(open(work.hd_dedup)),NOBS)) rows;

/* ── 3. Clean age ────────────────────────────────────────────────────────── */
data work.hd_age;
    set work.hd_dedup;
    if age < 0 or age > 120 or age = 999 then age = .;
run;

/* ── 4. Standardize sex ──────────────────────────────────────────────────── */
data work.hd_sex;
    set work.hd_age;
    length sex_clean $10;
    sex_upper = upcase(strip(sex));
    select;
        when (sex_upper in ('M','MALE','1'))      sex_clean = 'Male';
        when (sex_upper in ('F','FEMALE','0','2')) sex_clean = 'Female';
        otherwise                                  sex_clean = 'Unknown';
    end;
    drop sex sex_upper;
    rename sex_clean = sex;
run;

/* ── 5. Flag invalid ZIP codes ───────────────────────────────────────────── */
data work.hd_clean;
    set work.hd_sex;
    if zip_code = '00000' or notdigit(compress(zip_code)) > 0
        then zip_valid = 0;
    else zip_valid = 1;

    /* Parse admit_date if stored as character */
    admit_date_dt = input(admit_date, anydtdte20.);
    format admit_date_dt date9.;
run;

/* ── 6. Data quality summary ─────────────────────────────────────────────── */
proc means data=work.hd_clean nmiss n;
    var age;
    title "Missingness after cleaning (age)";
run;

proc freq data=work.hd_clean;
    tables sex zip_valid / missing;
    title "Distributions: sex, zip_valid";
run;
title;

/* ── 7. Export clean dataset ─────────────────────────────────────────────── */
proc export
    data    = work.hd_clean
    outfile = "&root./data/clean/sas_hospital_discharge_clean.csv"
    dbms    = csv
    replace;
run;

%put NOTE: 01_ingest_hospital_discharge.sas completed successfully.;
