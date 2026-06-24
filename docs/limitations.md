# Limitations

## 1. Synthetic Data
All three datasets were generated programmatically (seed=123). They mimic realistic surveillance and administrative data structures but contain no real patient records, county populations, or disease counts. Findings have no epidemiologic validity.

## 2. Inner Join Linkage
The merge between disease registry and population denominators uses an inner join on `county_fips` × `year`. Counties with registered cases but no matching denominator record are excluded. In real data, this would require investigation of FIPS code harmonization across sources.

## 3. Case Definition Consistency
The disease registry uses condition names (free text), while hospital discharge records use ICD-10 codes. Direct case-matching between the two sources was not performed. A real pipeline would require probabilistic record linkage or a crosswalk table.

## 4. Denominator Accuracy
Population denominators are synthetic and do not represent actual US county populations. Real analyses would use US Census Bureau annual estimates or ACS 5-year estimates.

## 5. Survey Design
The hospital discharge dataset does not represent a probability sample. Rates computed from administrative discharge records should not be interpreted as true population incidence without accounting for catchment areas and healthcare utilization patterns.

## 6. R Implementation
The R scripts have not been tested in a live R environment in this portfolio version. Logic mirrors the Python scripts, but package version differences (particularly `lubridate` date parsing) may require minor adjustments.

## 7. SAS Implementation
SAS scripts are provided as reference implementations and assume the analyst updates the `%let root` macro variable to their local project path. Scripts have not been executed; they represent documented analytic intent.
