# Assumptions and open points

The live list. Where this file and section 15 of `docs/PLAN.md` differ, this file wins.

An **assumption** is a choice made without data. An **open point** is a fact not yet confirmed. Each line says where it stands.

## Decided 2026-11-24: how the score counts and weighs warnings

The plan first proposed counting every calendar day a warning touches, with weights of 1.0 (winter), 0.5 (flood) and 0.25 (severe storms) per such day, 5.0 days per hurricane event, and bands at 2, 5 and 10. The owner asked how those numbers were chosen. Checking the reasoning against the warning archive showed three problems and one confirmation. The owner then chose the revision at the end of this section.

Measured on 2026-11-24 from the Iowa State warning archive (city-centre test points, 2016 to 2025 unless stated):

| Warning type | Warnings measured | Typical length (median) |
|---|---|---|
| Winter Storm, Minneapolis | 34 | 17.9 hours |
| Winter Storm, Dallas | 6 | 30.5 hours |
| Flash Flood, Dallas | 53 | 3.0 hours |
| Flash Flood, Minneapolis | 8 | 3.1 hours |
| Severe Thunderstorm, Dallas | 120 | 0.9 hours |
| Severe Thunderstorm, Minneapolis | 45 | 0.7 hours |
| Tornado, Dallas and Minneapolis | 2 each | 0.4 hours |

1. **The flood and storm weights are far above what warning length supports.** A 3-hour warning is about one eighth of a day and a 0.8-hour warning about one thirtieth. The proposed 0.5 and 0.25 are roughly 4 and 7 times that. The extra was meant to cover aftermath, but its size was a guess.
2. **Counting every calendar day touched inflates winter.** Minneapolis had 35 separate winter warning spells covering 649 hours, which is 27.1 days of warning time. They touched 63 calendar days. That is 6.3 a year by the proposed rule against 2.7 a year of actual warning time.
3. **The test hub's "high" came from the markups.** Dallas scored about 6.6 under the proposed rule and weights. Estimated as time under warning (number of warnings times median length, not summed exactly) it is roughly 2.
4. **The hurricane weight holds up.** Time under Hurricane, Tropical Storm or Storm Surge Warnings in 2008 to 2025, divided by the number of events FEMA's frequency predicts for those 18 years, gives 4.4 days per event for Miami (579 hours, 5.5 expected events) and 5.3 for Houston (418 hours, 3.3 expected events).

Decided:

- Count **time under warning** (hours divided by 24), not calendar days touched.
- The winter, flood and severe-storm weights are **1.0**: disrupted for as long as the warning is in force. Analysts who believe a hazard outlasts its warning use the what-if.
- The hurricane weight is **5 days per event**, resting on point 4.
- The **band cut-offs are fixed at the milestone 2 review**, from the twelve real figures, with the owner's sign-off.

## Measured 2026-11-24 in milestone 1: what the loaded data shows

All figures are from `uv run wra data-report` on the data fetched that day (twelve hubs, 2016 to 2025), unless a source is named.

1. **Every hub resolved.** All twelve station ids exist at the station service, and FEMA's map and the Weather Service's map name the same county for every hub. Dallas Love Field is in Dallas County, as the plan expected.
2. **Two hubs sit in a different county than their city's name suggests.** The O'Hare station's coordinates are in DuPage County and Atlanta's are in Clayton County, on both maps. The station service labels them Cook and Fulton. The hub's county is the one that contains its coordinates (decision log, 2026-11-24).
3. **FEMA's hurricane figure counts tropical storms too.** Its technical documentation (December 2025, section 13) says: "The Hurricane data also includes tropical storms for which wind speeds range from 39 to 74 mph." The county figure is an area-weighted average built from a 49 km grid (section 13.5).
4. **FEMA has a floor.** A place it considers reachable by a hurricane, but with no storm on record, gets 0.01 events a year (section 13.5.1: "set at 0.01 (1 in 100 years)"). The Chicago hub's county shows exactly 0.0100, and FEMA's own count of storms reaching that county is zero (its field `HRCN_EVNTS`, read in the day's first fetch and not kept). So Chicago's hurricane figure is FEMA's assumption, not a record of storms. Whether the small figures at other inland hubs (Dallas and Phoenix, 0.0115 each) come from the floor or from real storms was not worked out.
5. **FEMA gives two hub counties no hurricane figure at all** (Hennepin for Minneapolis, Denver) and gives Platte (Kansas City) zero.
6. **Station records are nearly complete.** Snowfall is missing on 106 of 3,653 days at Miami (2.9%) and on 0.7% or less at every other hub. Rainfall is missing on one day at Dallas and none elsewhere. Denver 2025 reads 26 days of measurable snowfall, 19 trace days and 1 missing day, the same as the hand check in session 01.
7. **Coastal Flood Warnings barely occur.** One hub (Houston) had two, both in 2016, lasting 24 and 46 hours: 2.9 days in ten years.
8. **Area Flood Warnings (code FA) are typically short, but have a long tail.** Matched by drawn area: 156 at 11 hubs, median 5.9 hours, longest 143.9 hours, 52.7 days in total. Flash Flood Warnings by comparison: 296 at 12 hubs, median 3.0 hours, longest 8.0, 41.7 days in total. Area Flood Warnings stay excluded (A3); the milestone 2 review should confirm that with these figures in view.
9. **746 source records were left out** because their expiry is not after their start: 557 watches, 84 advisories, 1 statement and 104 warnings. Three of the warnings are of a type the score counts, all Winter Storm Warnings (Chicago 2018, Memphis 2022, Minneapolis 2023). In each case a Blizzard or Ice Storm Warning is in the data, starting at or within two hours of the time the skipped warning was due to begin, so the storm's time is still counted.
10. **The raw responses take 7.8 MB on disk** in 49 files. The whole repository, raw responses included, is about 1.4 MB as git stores it.

## Assumptions

| # | Assumption | Standing |
|---|---|---|
| A1 | Twelve fictional hubs, each at its city's main airport, grouped by US Census region (plan section 6). Dallas uses Love Field. A hub sits at its airport weather station's coordinates, and its county is the one containing that point: DuPage for the Chicago hub and Clayton for the Atlanta hub (point 2 above). | Approved with the plan; locations confirmed in M1. |
| A2 | Time under an official warning stands in for disruption. A warning is a forecast, not a closure record. Aftermath after the warning ends is not scored. | Approved (interview answer 5, refined 2026-11-24). |
| A3 | Which warning types count for each hazard, and what is left out: advisories, watches, cold and wind-chill warnings, high-wind warnings, river and area flood warnings (plan section 5.2). | Approved with the plan. |
| A4 | How warnings are counted: hours in force divided by 24, overlapping warnings of one hazard merged first, each hour assigned to its calendar year in the hub's time zone. | Decided 2026-11-24. |
| A5 | The weights: 1.0 for winter, flood and severe storms (neutral), 5.0 days per hurricane event (supported by two hubs' records, still a judgment). FEMA's event count includes tropical storms (O3, settled), so the 5.0 reads as days per tropical storm or hurricane. The supporting warning time also includes tropical storms and storm surge, so the two sides of that comparison count the same kind of event. | Decided 2026-11-24. |
| A6 | The band cut-offs. Not yet set: round numbers of days per year, to be fixed from the twelve real figures. | Open until the milestone 2 review. |
| A7 | An hour with warnings for two hazards counts once in each. A hurricane's flash flood warnings also count under flood. | Approved with the plan. |
| A8 | Measurable snowfall means 0.1 inch or more. Trace days are reported separately. Missing days are left out of the percentage. | Approved with the plan. |
| A9 | "Last year" means the last full calendar year by the server's clock. The evaluation pins the clock. | Approved with the plan. |
| A10 | The confidence thresholds (plan section 5.6). | Approved with the plan. |
| A11 | Analysts accept waiting roughly 10 to 20 seconds for an answer. | Not asked in the interview. |
| A12 | English only. | Not asked in the interview. |

## Open points

| # | Open point | Settled in |
|---|---|---|
| O1 | The NOAA station service (ACIS) publishes no usage terms on the two documentation pages read on 2026-11-24. The owner accepted committing its raw responses to this repository on 2026-11-24. The terms themselves remain unconfirmed. | Accepted by owner; terms still open |
| O2 | A checker reported FEMA's FAQ as saying "This data may be used for commercial purposes." That document was not re-read. Confirmed directly: FEMA requires the notice "This product uses the Federal Emergency Management Agency's National Risk Index dataset API or downloadable datasets but is not endorsed by FEMA." It goes in the README and the page footer. | M5 |
| O3 | Whether FEMA's hurricane event count includes weaker tropical storms. It does (point 3 of the milestone 1 section). The 5.0 weight reads as days per tropical storm or hurricane (A5). | Settled in M1 |
| O4 | Whether tool calls and a structured final answer combine in one request the way the Claude API reference describes. | M3 spike |
| O5 | The size of the committed raw responses. Measured: 7.8 MB on disk; the whole repository is about 1.4 MB in git (point 10). Kept in full. | Settled in M1 |
| O6 | Station ids for the eleven hubs other than Denver, and whether each has near-complete snowfall records. All resolve; the least complete is Miami, with 2.9% of snowfall days missing (point 6). By the thresholds in plan section 5.6 a snowfall statistic for Miami over the whole period would be labelled medium confidence, not high. | Settled in M1 |
| O7 | The warning figures quoted so far were computed in UTC at city-centre points. The build uses the hub's time zone and airport points, so they will move somewhat. | M2 |
| O8 | Model prices in the plan come from a reference cached on 2026-11-03. Re-check against the live pricing page before they appear in the README. | M5 |
| O9 | How far the `.env` deny rule in `.claude/settings.json` reaches. Tested 2026-11-24 on a placeholder file: the file-reading tool was refused, and so was `cat .env` in the shell. An indirect read, such as a script that opens the file, was not tested and is not claimed to be blocked. | Settled for direct reads |
| O10 | How long Coastal Flood Warnings last. Measured: 24 and 46 hours, but only two in ten years, both at Houston (point 7). They cannot dominate. Whether they stay in the flood group is decided with the bands. | Measured in M1; decision at the M2 review |
| O11 | What the score does where FEMA gives a county no hurricane figure (Minneapolis, Denver) or its floor of 0.01 a year (point 4). Proposed: no figure counts as zero and the answer says FEMA rates hurricanes as not applicable there; a floor figure is used as given and the explanation names it as FEMA's minimum. | M2 |
