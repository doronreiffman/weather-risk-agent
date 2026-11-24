# Hub weather exposure: summary for the hand-over

**The question.** Which of the twelve distribution hubs are most exposed to weather disruption? The system ranks the hubs, explains the ranking and says what the records cannot show, to support this year's choice of hubs for resilience investment. It does not say where to invest.

## The ranking today

The score is **expected disruption days a year**: the days a hub spent under the official weather warnings listed below in an average year of 2016 to 2025, plus 5 days for each hurricane or tropical storm it can expect in a year. Bands are fixed labels: Low below 1 day a year, Moderate from 1, High from 2, Very high from 3.

| Rank | Hub | Expected disruption days a year | Band | Main hazard |
|---|---|---|---|---|
| 1 | Minneapolis | 2.90 | High | Winter |
| 2 | Memphis | 2.44 | High | Winter |
| 3 | Denver | 2.21 | High | Winter |
| 4 | Kansas City | 2.20 | High | Winter |
| 5 | Chicago | 2.03 | High | Winter |
| 6 | Dallas | 2.02 | High | Winter |
| 7 | Houston | 1.96 | Moderate | Hurricanes |
| 8 | Miami | 1.85 | Moderate | Hurricanes |
| 9 | Indianapolis | 1.56 | Moderate | Winter |
| 10 | Atlanta | 1.24 | Moderate | Flooding |
| 11 | Columbus | 0.99 | Low | Winter |
| 12 | Phoenix | 0.42 | Low | Severe storms |

**Read it as groups, not as an exact order.** The system rates this ranking low confidence, for two reasons:

- For 10 of the 11 pairs of neighbouring hubs, the gap is too small to settle their order, given how much each hub's figure changes from year to year. Only Columbus and Phoenix are clearly apart.
- First place depends on how much each hazard counts. With hurricanes counted double, or winter counted half, Miami comes first; with floods counted double, Memphis does. With winter counted double, the same three hubs stay on top.

The band lines are round numbers, not natural breaks. Dallas is only 0.02 days above the High line, and the data cannot tell it apart from Houston, the first hub below that line.

## What the score counts

- **Winter:** winter storm, blizzard, ice storm and lake-effect snow warnings.
- **Flooding:** flash flood warnings.
- **Severe storms:** tornado and severe thunderstorm warnings.
- **Hurricanes:** the hurricanes and tropical storms a year the hub's county can expect, from the Federal Emergency Management Agency (FEMA).

Time is what counts: a day under any of these warnings is one disruption day, so a long warning weighs more than a short one. Each expected hurricane counts as 5 days, a figure checked against the warning records at Miami and Houston.

## What it cannot tell you

- **Whether a hub closed.** A warning forecasts dangerous weather; it is not a closure record.
- **What happens after a warning ends,** such as closed roads or power cuts. Winter's effect on roads lasts longest, so the score may understate winter.
- **The future.** It describes 2016 to 2025 and is not a forecast.
- **Flood risk at the exact site.** The score sees only each hub's county and an assumed location: its city's main airport (Love Field for Dallas).
- **Heat, cold snaps, wildfire and earthquakes,** which it does not cover.

## What the investment decision still needs

- How much each hub matters to the business.
- What each upgrade would cost.
- Flood risk at each hub's real address.
- The company's own closure records, to show how long weather really shuts each hub.

## Data and period

Weather warnings for 2016 to 2025 come from the National Weather Service, through Iowa State University's Iowa Environmental Mesonet archive. Hurricane figures come from FEMA's National Risk Index (December 2025 release, records from 1851 to 2024). Daily snowfall and rainfall for 2016 to 2025 come from NOAA airport weather stations, through ACIS, the data service of NOAA's Regional Climate Centers. They answer questions such as how many days had snow, and are not part of the score. All data was collected on 24 November 2026.

## Asking the agent

Once the system is installed, someone on the team starts the chat page with the command `uv run wra serve` and opens http://127.0.0.1:8000/ in a browser on the same computer. Questions are typed in plain English, for example "Which hubs in the Midwest are most exposed to winter disruption?" or "What if a hurricane counted double?". A what-if is labelled as such and leaves the official ranking unchanged.

An AI model, Anthropic's Claude, writes only a short verdict. Every number in it must match a figure the system computed, or the answer is sent back once for correction; the check cannot tell which hub a figure belongs to, and can miss a wrong small whole number such as a rank, so the tables beside the verdict, which are built without the AI, always show the true figures. Each answer with figures shows its sources, period and confidence. If an answer fails the checks twice, the page shows a plain error instead. Follow-up questions keep the context. Questions the data cannot answer, such as a city with no hub or next week's weather, are marked Out of scope. In the latest test an answer took about four and a half seconds, and never more than eight. Each question is a paid request to Anthropic, at well under a cent.

**How it was tested.** On 24 November 2026, 14 test questions were each asked three times, 42 in all, on Claude Haiku 5.5, the model the system uses. 41 passed every automatic check: the expected status, the right lookup, the right hubs in the right order, and tables matching the system's own figures. The one miss was a right answer that wrote a weight as a word ("five days"), which the check cannot verify. No answer was refused. The larger Claude Opus 5.5 passed all 42 but costs about 27 times as much per answer.

---

This product uses the Federal Emergency Management Agency's National Risk Index dataset API or downloadable datasets but is not endorsed by FEMA. The Federal Government or FEMA cannot vouch for the data or analyses derived from these data after the data have been retrieved from the Agency's website(s).
