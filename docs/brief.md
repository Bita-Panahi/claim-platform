# Project brief: Flood loss experience, North Carolina

## Problem
An underwriting team insures homes against flood in North Carolina. In some areas,
claims paid out are higher than the premiums collected, so the insurer loses money
there. In other areas premiums are higher than claims. The team wants to find where
flood risk is underpriced, measured by the loss ratio (claims paid ÷ premium), so
they can review prices and risk selection in those areas.

## Users
- Underwriters: check loss experience for a county, flood zone or building type
  before deciding on price and terms.
- Analysts: answer follow-up questions from the underwriters.

## Questions
1. Which flood zone groups have had a loss ratio above 100% since 2019?
2. Which counties have the highest average claim payment?
3. Which building types (occupancy type) get the highest average claim payment?
4. How does the average claim payment differ between elevated and non-elevated buildings?
5. Which named flood events caused the highest total payments, and what was their average claim?

## Scope
- Data: FEMA NFIP claims and policies (OpenFEMA API v3), North Carolina only.
- Period: policy and loss years 2019 onward, so premiums and claims cover the same years.

## Out of scope
- Pricing models or premium recommendations
- Other states
- Real-time data (the source refreshes monthly)

## Success criteria
- The warehouse can be rebuilt from scratch with one command.
- A scheduled pipeline refreshes the data monthly.
- dbt tests stop the pipeline when the data has blocking defects.
- An app answers all five questions and shows the SQL behind each answer.