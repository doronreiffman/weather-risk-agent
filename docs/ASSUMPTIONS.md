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

Figures come from `uv run wra data-report` on the data fetched that day, or from SQL on the same database where a point needs more detail than the report prints (points 7, 9 and 12). Warning rows were requested by issue date from 25 December 2015 up to 2 January 2026 (point 11). The report's counts include the few rows issued in the last week of 2015; point 12 counts only warnings issued in 2016 to 2025.

1. **Every hub resolved.** All twelve station ids exist at the station service, and FEMA's map and the Weather Service's map name the same county for every hub. Dallas Love Field is in Dallas County, as the plan expected.
2. **Two hubs sit in a different county than their city's name suggests.** The O'Hare station's coordinates are in DuPage County and Atlanta's are in Clayton County, on both maps. The station service labels them Cook and Fulton. The hub's county is the one that contains its coordinates (decision log, 2026-11-24).
3. **FEMA's hurricane figure counts tropical storms too.** Its technical documentation (December 2025, section 13) says: "The Hurricane data also includes tropical storms for which wind speeds range from 39 to 74 mph." The county figure is an area-weighted average built from a 49 km grid (section 13.5).
4. **FEMA gives reachable land with no recorded hurricane a default of 0.01 a year** (section 13.5.1: "set at 0.01 (1 in 100 years)"). It is a default, not a minimum. Land with one storm on record in 174 years gets about 0.006 (one divided by 173.86, section 13.5), so a county can average below 0.01, as Indianapolis (0.0077) and Columbus (0.0058) do. The Chicago hub's county shows exactly 0.0100, and FEMA's own count of storms reaching that county is zero (its field `HRCN_EVNTS`, read in the day's first fetch and not kept). So Chicago's hurricane figure is FEMA's default, not a record of storms. Whether the small figures at other inland hubs (Dallas and Phoenix, 0.0115 each) come from the default or from real storms was not worked out.
5. **FEMA gives two hub counties no hurricane figure at all** (Hennepin for Minneapolis, Denver) and gives Platte (Kansas City) zero.
6. **Station records are nearly complete.** Snowfall is missing on 106 of 3,653 days at Miami (2.9%) and on 0.7% or less at every other hub. Rainfall is missing on one day at Dallas and none elsewhere. Denver 2025 reads 26 days of measurable snowfall, 19 trace days and 1 missing day, the same as the hand check in session 01.
7. **Coastal Flood Warnings barely occur.** One hub (Houston) had two, both in 2016, lasting 24 and 46 hours: 2.9 days in ten years.
8. **Area Flood Warnings (code FA) are typically short, but have a long tail.** Matched by drawn area: 158 at 11 hubs, median 5.9 hours, longest 143.9 hours, 53.3 days in total. Flash Flood Warnings by comparison: 298 at 12 hubs, median 3.0 hours, longest 8.0, 42.1 days in total. These lengths are the warnings as first drawn (point 12). Area Flood Warnings stay excluded (A3); the milestone 2 review should confirm that with these figures in view.
9. **750 source records were left out** because their expiry is not after their start: 560 watches, 84 advisories, 1 statement and 105 warnings. Three of the warnings are of a type the score counts, all Winter Storm Warnings. In each case the data holds a Blizzard or Ice Storm Warning for the same storm. At Chicago (2018) it began exactly when the skipped warning was due, and at Memphis (2022) it began 3 hours 44 minutes earlier and was still in force. At Minneapolis (2023) it began 2 hours after the skipped warning's due time.
10. **The raw responses take 7.9 MB on disk** in 49 files. The whole repository is 2.15 MiB as git stores it (`git count-objects -vH`, end of milestone 1). That includes both fetches of the warning files, since git keeps the first one in its history.
11. **The warning archive selects by issue date, and its end date is excluded.** Measured with narrow requests around two known Dallas warnings: a request ending on a warning's issue date does not return it, and a request starting the day after does not return a warning still in force then. The first fetch asked for 2016-01-01 to 2025-12-31, so it missed every warning issued on 31 December 2025, the evening of New Year's Eve 2025 at every hub, and warnings issued in late December 2015 that ran into 2016. The request now runs from 25 December 2015 to 2 January 2026 (end excluded), and scoring keeps only the hours inside the period. In this data the fix changed no counted warning: the 4 warnings running into 2016 are river flood warnings, which are not scored, and nothing counted was issued on 31 December 2025. Every row issued inside the old window is unchanged.
12. **A drawn-area warning row keeps its first planned end.** If the warning was cancelled early or extended for the hub's county, only the county's zone row for the same event shows it. Measured by joining each drawn-area warning issued in 2016 to 2025 to the county row of the same event (same office, year, type and event number). Every drawn-area row has such a county row, with the same start. The ends differ:

| Type | Drawn-area rows | County row ended first | Hours counted after the county row ended | County row extended | Longest extension |
|---|---|---|---|---|---|
| Severe Thunderstorm | 920 | 104 | 29.7 of 650.8 (4.6%) | 0 | - |
| Tornado | 36 | 4 | 1.3 of 17.4 | 0 | - |
| Flash Flood | 296 | 20 | 23.8 of 1,001.0 | 52 | 9.0 hours |

   Settled in milestone 2 as open point O12.

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
| O5 | The size of the committed raw responses. Measured: 7.9 MB on disk; the whole repository is 2.15 MiB in git (point 10). Kept in full. | Settled in M1 |
| O6 | Station ids for the eleven hubs other than Denver, and whether each has near-complete snowfall records. All resolve; the least complete is Miami, with 2.9% of snowfall days missing (point 6). By the thresholds in plan section 5.6 a snowfall statistic for Miami over the whole period would be labelled medium confidence, not high. | Settled in M1 |
| O7 | The warning figures quoted so far were computed in UTC at city-centre points. The build uses the hub's time zone and airport points, so they will move somewhat. | M2 |
| O8 | Model prices in the plan come from a reference cached on 2026-11-03. Re-check against the live pricing page before they appear in the README. | M5 |
| O9 | How far the `.env` deny rule in `.claude/settings.json` reaches. Tested 2026-11-24 on a placeholder file: the file-reading tool was refused, and so was `cat .env` in the shell. An indirect read, such as a script that opens the file, was not tested and is not claimed to be blocked. | Settled for direct reads |
| O10 | How long Coastal Flood Warnings last. Measured: 24 and 46 hours, but only two in ten years, both at Houston (point 7). They cannot dominate. Whether they stay in the flood group is decided with the bands. | Measured in M1; decision at the M2 review |
| O11 | What the score does where FEMA gives a county no hurricane figure (Minneapolis, Denver) or its default of 0.01 a year (point 4). Proposed: no figure counts as zero and the answer says FEMA rates hurricanes as not applicable there; a figure of exactly 0.01 is used as given and the explanation names it as FEMA's default for land with no recorded storm. | M2 |
| O12 | How to count a drawn-area warning whose county row ended earlier or later (point 12). Proposed: it ends at the earlier of its own end and the county row's last end, because once the county is cancelled the hub cannot still be under the warning. A county extension is not added, because the redrawn area may no longer have covered the hub. The effect is small: severe thunderstorm time falls about 5%. | M2 |
