# Content refresh — check these every summer

Study cards cite U.S. government sources (or the Army manuals in `library/`). Most facts don't change, but the ones
below do. Before each school year (suggested: **every July**), open each source, compare, and edit the card in
`vanguard/cards/`. Then run `python -m unittest discover -s tests`. Each card's `source:` line says where it came from.

Last full check: **2026-10-09** (Phase 11).

## Changes every year

| Card | What to check | Where |
|---|---|---|
| `careers_fafsa` | Pell Grant maximum ($7,395 for 2026–27), which FAFSA year is open, what you need to apply | studentaid.gov/h/apply-for-aid/fafsa, studentaid.gov/understand-aid/types/grants |
| `careers_first_paycheck_taxes` | W-4 exemption deadline (February 15), $400 self-employment rule, $20 tip rule | IRS Publication 505 (newest year) |
| `jrotc_about`, `explore_jrotc_and_service` | Number of units and Cadets; E-2/E-3 enlistment rule; academy nominations | Congressional Research Service IF11313 (newest update) |
| `health_teen_driving` | CDC statistics (2019–2020 data) | cdc.gov/teen-drivers |
| `health_underage_drinking` | CDC statistics (deaths per year, binge drinking %) | cdc.gov/alcohol/underage-drinking |
| `leadership_bullying` | "About 1 in 5" (2022 survey) | stopbullying.gov — What Is Bullying |
| `health_vaping` | CDC facts; Smokefree Teen program names | cdc.gov/tobacco/e-cigarettes/youth.html, teen.smokefree.gov |

## Changes every few years

| Card | What to check | Where |
|---|---|---|
| `health_eating_well` | Dietary Guidelines **2025–2030** — next edition due for 2030 | dietaryguidelines.gov |
| `nutrition_hydration` | Uses FM 7-22 (2020), which says **low-fat** dairy; the 2025–2030 Dietary Guidelines say full-fat with no added sugar. Owner decision pending. | FM 7-22 newest edition |
| `citizenship_supreme_court` | Number of Associate Justices ("currently eight") | supremecourt.gov/about |
| `citizenship_congress` | 435 House seats; qualifications | house.gov, senate.gov |
| `careers_banking` | FDIC coverage ($250,000) | fdic.gov |
| `careers_credit_cards`, `careers_credit_reports`, `careers_spotting_scams`, `careers_protect_accounts`, `careers_budget` | FTC/CFPB advice, $50 unauthorized-charge limit, AnnualCreditReport.com rules | consumer.ftc.gov, consumerfinance.gov |
| `careers_compound_interest`, `careers_emergency_savings` | Investor.gov examples | investor.gov |
| `careers_interview_*`, `careers_resume`, `careers_references`, `careers_job_applications` | CareerOneStop pages (blocks automated tools — open in a browser) | careeronestop.org |
| `health_until_help_arrives`, `health_cpr`, `health_choking` | First aid steps (CPR guidance is updated every few years) | ready.gov/you-are-help-until-help-arrives, medlineplus.gov |
| `health_managing_stress` | 988 Lifeline details | cdc.gov/mental-health, 988lifeline.org |

## Army manuals (library/)

Cards built from these name the edition in their `source:` line. When a newer edition is published, re-check the cards
that cite it: TC 7-21.13 (Sep 2025), TC 3-21.5 (May 2021), FM 7-22 (Oct 2020), FM 6-22 (Nov 2022), ATP 6-22.1
(Feb 2024), AR 600-25 (May 2026), AR 670-1, Ranger Handbook. Especially time-sensitive: **`aft_events`** (the Army fitness
test changes), `uniform_agsu`, `grooming_facial_hair`, `gi_bill`, `tuition_assistance`, `money_readiness`.

## Still flagged `verified: no`

Cards with `verified: no` show a "not yet checked" note to Cadets. As of 2026-10-09: `land_navigation` (TC 3-25.26 is
restricted to CAC holders; `map_reading_topo` covers the basics from USGS instead) and `officer_candidate_school`.
List them with:

```
grep -l "verified: no" vanguard/cards/*.md
```
