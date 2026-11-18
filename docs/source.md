# Source notes: OpenFEMA NFIP

## Endpoints
- Claims: https://www.fema.gov/api/open/v3/NfipClaims
- Policies: https://www.fema.gov/api/open/v3/NfipPolicies
- Data version: field `asOfDate` (same value on every row). Last seen: 2026-11-16.
  FEMA describes the refresh as roughly monthly; to be confirmed by tracking asOfDate (step S5).
- Note: `metadata.rundate` is when the API answered the request, not when the data was produced.

## Row counts (North Carolina, asOfDate 2026-11-16)
- Claims, all years (1978 onward): 109,642
- Claims, yearOfLoss 2019 onward: 8,984
- Policies, policyEffectiveDate 2019 onward: 962,804 (one row per policy term, ~1 year)
- First estimate of claim frequency: 8,984 / 962,804 ≈ 0.93% claims per policy-year

## How the API behaves
- `metadata.count` is 0 unless the request includes `$count=true`; with it, the count is the
  total matching the filter, not the size of the current page.
- Maximum page size: 8984 rows. Larger `$top` values are silently capped, so a single request
  cannot be trusted to return everything.
- Paging: `$top` = page size, `$skip` = rows to jump over. Always page with `$orderby=id`;
  without a fixed order, pages can overlap or skip rows with no error.
- Completeness check: after fetching, compare the number of rows received with `metadata.count`
  (NC claims 2019+: 8,984 received, 8,984 expected).

## Columns we keep

### Claims
| Column | Why |
|---|---|
| id | Unique row key |
| asOfDate | Data version |
| dateOfLoss, yearOfLoss | Filter to 2019+, group by year |
| state, countyCode, censusGeoid | Filter to NC, group by county (Q2) |
| ratedFloodZone | Group by flood zone (Q1) |
| occupancyType | Building type (Q3) |
| elevatedBuildingIndicator | Elevated vs not (Q4) |
| floodEvent | Named events (Q5) |
| amountPaidOnBuildingClaim, amountPaidOnContentsClaim | Money paid out (Q1–Q5) |
| buildingDamageAmount | Assessed damage, compared with what was paid |
| totalBuildingInsuranceCoverage | Coverage limit, for sanity checks (paid > coverage?) |
| causeOfDamage | Filter out non-flood causes if needed |

### Policies
| Column | Why |
|---|---|
| id | Unique row key |
| asOfDate | Data version |
| policyEffectiveDate, policyTerminationDate | Filter to 2019+, assign policy year |
| propertyState, censusGeoid | Filter to NC, county from the first 5 digits |
| ratedFloodZone | Group by flood zone (Q1) |
| totalInsurancePremiumOfThePolicy | Money in, for the loss ratio (Q1) |
| totalBuildingInsuranceCoverage | Exposure |
| policyCount | Number of policies a row represents (usually 1) |
| occupancyType, elevatedBuildingIndicator | Same breakdowns as claims (Q3, Q4) |

## Naming differences between the tables
| Meaning | Claims | Policies |
|---|---|---|
| State | state | propertyState |
| Number of floors | numberOfFloorsInTheInsuredBuilding | numberOfFloorsInInsuredBuilding |
| Place of worship | houseWorship | houseOfWorshipIndicator |
| Built before the first flood map (pre-FIRM) | preFirmIndicator | preFIRMConstructionIndicator |
| Disaster assistance required | disasterAssistanceCoverageRequired | disasterAssistanceCoverageRequiredCode |
| County | countyCode | (none) first 5 digits of censusGeoid |



## Codes to decode
| Column | What the codes mean | Plan |
|---|---|---|
| ratedFloodZone | FEMA flood zone. Zones starting with A or V are high risk (Special Flood Hazard Area); B, C and X are moderate to low; D is undetermined. Many spellings (A, AE, A07, AO, VE, X...). | Map to a zone group with one rule (macro in S7) |
| occupancyType | Number code for building type (single family, 2–4 units, non-residential...). | Seed lookup table from the OpenFEMA data dictionary (S7) |
| causeOfDamage | Code for what caused the loss (rainfall accumulation, river overflow, tidal water...). | Seed lookup table from the data dictionary (S7) |
| elevatedBuildingIndicator | true/false | Use as is |

Source for code meanings: the OpenFEMA data dictionary on the dataset pages for NFIP Redacted Claims v3 and NFIP Redacted Policies v3.

## Oddities found
rows: 8984
zero total payment: 1676
negative payment: 1
building paid > building coverage: 5
missing ratedFloodZone: 10
distinct zone spellings: 24
missing floodEvent: 3681
reportedCity placeholders: {'Currently Unavailable': 8984}
dateOfLoss type: str
duplicate ids: 0