/*=============================================================================
  03_merge_and_rates.sas
  -------------------------
  Merge cleaned disease registry with population denominators and
  calculate county-level annual incidence rates per 100,000.

  Requirements
  ------------
  SAS 9.4 or later. Requires cleaned outputs from scripts 01 and 02.

  Input:   data/clean/sas_disease_registry_clean.csv
           data/raw/population_denominators.csv
  Output:  data/clean/sas_master_incidence.csv
           outputs/tables/sas_incidence_rates.csv
=============================================================================*/

%let root = /path/to/project2_epi_data_ingestion;

/* ── 1. Import cleaned registry ──────────────────────────────────────────── */
proc import
    datafile = "&root./data/clean/sas_disease_registry_clean.csv"
    out      = work.registry
    dbms     = csv
    replace;
    getnames = yes;
run;

/* ── 2. Import population denominators ───────────────────────────────────── */
proc import
    datafile = "&root./data/raw/population_denominators.csv"
    out      = work.population
    dbms     = csv
    replace;
    getnames = yes;
run;

/* ── 3. Aggregate case counts by county × year × condition ───────────────── */
proc sql;
    create table work.case_counts as
    select
        county_fips,
        report_year as year,
        condition_clean as condition,
        count(*) as case_count,
        mean(hospitalized) as pct_hospitalized
    from work.registry
    where fips_valid = 1
      and date_parse_error = 0
      and 2020 <= report_year <= 2023
    group by county_fips, report_year, condition_clean;
quit;

/* ── 4. Merge case counts with population denominators ──────────────────── */
proc sql;
    create table work.rates_raw as
    select
        c.county_fips,
        c.year,
        c.condition,
        c.case_count,
        p.population,
        p.county_name,
        p.state_abbr,
        (c.case_count / p.population) * 100000 as incidence_rate_per_100k format=8.2,
        c.pct_hospitalized
    from work.case_counts as c
    inner join work.population as p
        on  c.county_fips = p.county_fips
        and c.year        = p.year;
quit;

/* ── 5. Summary statistics by condition ──────────────────────────────────── */
proc means data=work.rates_raw n mean std min max maxdec=2;
    class condition;
    var incidence_rate_per_100k case_count;
    title "Incidence rates by condition (2020–2023)";
run;
title;

/* ── 6. Export master incidence dataset ──────────────────────────────────── */
proc export
    data    = work.rates_raw
    outfile = "&root./data/clean/sas_master_incidence.csv"
    dbms    = csv
    replace;
run;

/* ── 7. Export summary rate table ───────────────────────────────────────── */
proc sql;
    create table work.rate_summary as
    select
        condition,
        sum(case_count)                            as total_cases,
        mean(incidence_rate_per_100k)              as mean_rate,
        min(incidence_rate_per_100k)               as min_rate,
        max(incidence_rate_per_100k)               as max_rate,
        mean(pct_hospitalized)                     as mean_pct_hospitalized
    from work.rates_raw
    group by condition
    order by total_cases descending;
quit;

proc export
    data    = work.rate_summary
    outfile = "&root./outputs/tables/sas_incidence_rates.csv"
    dbms    = csv
    replace;
run;

%put NOTE: 03_merge_and_rates.sas completed successfully.;
