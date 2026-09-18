# Submarket screening tool

A screen that ranks municipalities inside a market on demand, rent, supply
pressure, location and municipal attitude to rental housing, built entirely
from free public data, with every figure traceable to its source and vintage.

It is a screen, not an underwriting. It tells you which five municipalities are
worth a week of work. It does not tell you what to pay for a site.

Markets configured: **Madison WI**, **Grand Rapids MI**, **Lexington KY**,
**Savannah GA**.

---

## Running it without installing anything

The whole pull runs in GitHub Actions, so you do not need Python or a terminal.

1. Add `CENSUS_API_KEY` at **Settings > Secrets and variables > Actions > New
   repository secret**. It is free and instant, and without it the demand
   pillar is blank: see the key table below. `BLS_API_KEY` and `HUD_API_KEY`
   are genuinely optional.
2. Go to **Actions > Submarket screener data pull > Run workflow**, choose a
   market, press the green button.
3. When it finishes, scroll to **Artifacts** at the bottom of the run page and
   download the zip. It holds the workbook, the one-pager, `raw.json` and the
   full run log.

The workflow also runs monthly on its own, so the screen does not go stale.

Two things it will not do for you. The Streamlit app needs somewhere to run,
so that is still local or Streamlit Community Cloud. And the municipal
attitude column is your own research either way.

**This repository is public.** Put keys in repository Secrets and nowhere else.
GitHub masks a secret value in logs; it does not mask a fragment of one, which
is why the diagnostic prints only key lengths when it runs in CI.

## Quick start (local)

```bash
cd submarket-screener
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# Optional, only needed for the school proxy columns. It pulls GDAL and is the
# slow part of the install. Without it those columns read MISSING, by design.
.venv/bin/pip install -r requirements-optional.txt

# Set the three free keys. This prompts for each one and writes .env for you,
# which is safer than pasting a long token at a shell prompt.
.venv/bin/python setup_keys.py                   # Windows: .venv\Scripts\python setup_keys.py

.venv/bin/python -m screener.cli check           # confirms keys and weights

.venv/bin/python -m screener.cli run --market madison_wi   # fetch then report
.venv/bin/python -m screener.cli run --all

.venv/bin/streamlit run app/streamlit_app.py     # the interview demo
```

`fetch` is the only command that touches the network. Everything it downloads
is written to `data/cache/`, and `report` and the Streamlit app read only
`output/<market>/raw.json`. Once you have fetched once, the whole demo runs
with the wifi off.

## The API keys

One matters, two are optional.

| Key | What it costs you to skip | Where to get it |
| --- | --- | --- |
| `CENSUS_API_KEY` | **The whole demand pillar (30%)** and the per-household supply columns | https://api.census.gov/data/key_signup.html (instant, click the activation link in the email) |
| `BLS_API_KEY` | County unemployment, 6% of the demand pillar | https://data.bls.gov/registrationEngine/ (instant, key by email) |
| `HUD_API_KEY` | The Fair Market Rent cross-check columns, which are not scored | https://www.huduser.gov/portal/dataset/fmr-api.html (free account, generate a token on your account page) |

Put them in `.env`, which is gitignored, or add them as repository secrets to
run in Actions.

**On the Census key.** Census used to serve the Data API unauthenticated below
a daily quota. On 12 May 2026 it made a key mandatory on every request, and it
signals a missing one with HTTP 200 and an HTML page titled "Missing Key", so
anything that checks only the status code will read an error page as data. This
tool checks for the key before it calls, reports every ACS column MISSING when
there is none, and says why in one line instead of probing five vintages that
cannot answer.

Everything else still runs without any key at all: the Census Gazetteer,
the Building Permits Survey, the Population Estimates Program (which is why the
shortlist is still ranked on real population when ACS is absent), BLS QCEW,
Zillow ZORI and the NCES district files.

If a key is absent, the columns that need it come through as MISSING with the
key named as the reason, and the rest of that source still loads. A missing key
never takes down a source that does not need it, and the tool never substitutes
a different endpoint that returns different numbers.

---

## What it does, step by step

**1. Build the universe.** The Census Gazetteer gives every municipality in the
market's counties, with an internal point and a land area.

**2. Filter to the trade area.** Great-circle distance from each centroid to the
nearest employment centre; anything beyond `max_distance_miles` drops out.

**3. Pull ACS for everything left.** The call is a county or state wildcard, so
fifty municipalities cost the same as ten.

**4. Pick the shortlist.** The `target_submarkets` largest survivors above
`min_population`, plus anything in `always_include`, minus anything in
`always_exclude`. Selection is rule-based and reproducible, not hand-picked.
Population comes from ACS where it is available and from the Census Population
Estimates Program otherwise, so losing one of them does not change the rule.
Only if both are unavailable does the tool fall back to the closest
municipalities by distance; `always_include` and `always_exclude` are still
honoured, and `raw.json` records which rule produced the set in
`shortlist_method` so the run is never silently different.

**5. Pull the rest for the shortlist**: rents, permits, county jobs, the school
proxy, and your manual municipal attitude column.

**6. Score and rank.** See the scoring section below.

**7. Write the outputs**: a four-tab workbook, a one-page HTML summary, and a
frozen JSON snapshot the Streamlit app reads.

---

## Why submarkets are defined the way they are

| Market | Unit | Why |
| --- | --- | --- |
| Madison WI, Grand Rapids MI | County subdivision (MCD) | Wisconsin and Michigan MCDs (towns, townships, villages, cities) cover the whole state with no gaps and no overlaps, and they are the bodies that issue permits and set zoning. Gaines Township, where Continental broke ground on its fifth Grand Rapids community, is a township and not a Census place, so a place-based screen would miss it entirely. |
| Lexington KY, Savannah GA | Census place | Kentucky and Georgia MCDs are non-functional statistical divisions with no government. Incorporated places are the real jurisdictions. |

This matters for one reason above all: **the municipal attitude column and the
permits data have to describe the same jurisdiction**. A ZIP code cuts across
municipal boundaries, so neither can be attributed to it cleanly.

Rent is the exception. Zillow publishes it by ZIP, so ZIP-level rent is mapped
onto municipalities using the Census 2020 ZCTA relationship files, weighted by
the land area of the overlap.

---

## Every data source

| Column group | Source | Vintage handling | Key |
| --- | --- | --- | --- |
| Population, households, growth, renter share, income, age profile | Census ACS 5-Year Estimates API | Probes backwards for the newest release. Growth compares two **non-overlapping** 5-year samples (for example ACS 2020-2024 against ACS 2015-2019) | Yes |
| County employment and growth | BLS QCEW open data CSVs | Probes backwards for the latest annual file | No |
| County unemployment rate and labour force | BLS LAUS public API v2, annual averages | Probes backwards | Yes |
| Rent level and rent growth | Zillow Observed Rent Index, ZIP level, smoothed, all homes plus multifamily | Latest month in the published file | No |
| Rent cross-check | HUD Fair Market Rents API, 2 bedroom, county | Probes fiscal years backwards | Yes |
| Multifamily permits, 5+ unit buildings, last 3 years | Census Building Permits Survey, place and county annual files | Probes backwards for the latest complete calendar year | No |
| Distance to employment | Great-circle from Gazetteer centroids to operator-set employment centres. Optional drive distance from the public OSRM demo server with `--osrm` | Current | No |
| School proxy | NCES Common Core of Data district files, joined by point-in-polygon against Census TIGER school district boundaries | Latest available | No |
| Municipal attitude | You, in `config/municipal_attitude.csv` | Whatever date you record | No |

The workbook's "Sources and gaps" tab lists the source, vintage, retrieval
timestamp and URL for every single column, and how many submarkets have data
for it. The "Raw data" tab carries the same metadata in rows 2 to 7 above each
column, and every cell has a hover comment with either its methodological note
or its reason for being missing.

---

## How the scoring works, in plain English

**Step 1: make the columns comparable.** Median household income is in dollars,
rent growth is in percent, distance is in miles. You cannot add them together.
So each column becomes a 0 to 100 sub-score saying where a submarket sits
relative to the other submarkets in the same market.

- `percentile` (default): the same calculation as Excel's `PERCENTRANK.INC`.
  0 is the worst of the group, 100 the best, and the number in between is the
  share of the group this submarket beats.
- `zscore`: 50 plus 15 points per standard deviation above the group average,
  clipped to 0 and 100. This rewards being far ahead rather than just ahead.

For a column where low is good (permits per household, miles to work,
unemployment) the sub-score is flipped, so **100 always means good for us**.

**Step 2: average the sub-scores inside each pillar**, weighted by the metric
weights in `config/weights.yml`. If a figure is missing for a submarket it is
dropped and the remaining weights inside that pillar are rescaled so they still
add to 100%. Nothing is filled in with a zero or a group average.

**Step 3: average the pillars into one score**, weighted by the pillar weights.
If a whole pillar has no data for a submarket, its weight is redistributed
across the pillars that do.

**Data coverage** reports what share of the intended weighting actually backed
the score. A pillar that was dropped for thin data contributed nothing to the
total, so it contributes nothing to coverage either.

**Thin rows cannot win.** This is the trap the tool is most careful about. Every
sub-score is relative and a missing pillar's weight is redistributed, so a
submarket with one figure out of thirteen can score 100 on that one figure and
take rank 1. It is a real number, but it is a ranking of different things. Any
submarket whose coverage falls below 60% is therefore marked thin and ranked
beneath every submarket that could be measured properly, in the Python scorer,
in the workbook (through the sort key) and in the one-pager. It never gets a
"TOP 3" badge, and if it still leads the explanation says so in the first two
sentences.

Default weights: Demand 30, Rent 25, Supply pressure 25, Location 10, Municipal
10. They do not have to sum to 100; they are normalised at run time.

`winsorize_pct` in `weights.yml` clips the top and bottom tail of a column back
to the surviving extremes before scoring. It only applies to the `zscore`
method, where one runaway value drags the mean and flattens everyone else. The
raw figure in the workbook is untouched.

The Python scorer and the workbook's live formulas are held to the same answer
by tests in `tests/test_pipeline_end_to_end.py`, which recalculate the saved
`.xlsx` with an independent formula engine and compare the ranking row by row.
They cover both scoring methods, a raised `min_metrics_per_pillar`, a column
with one number in it, an entirely empty column, and a starved row. If they
ever drift, the tests fail.

One gap in that check, stated because it matters: the test engine returns the
mid-rank for a tied value in `PERCENTRANK.INC`, where Excel returns the lowest
tied rank. `screener/score.py` implements Excel's behaviour and pins it in its
own test, but the cross-engine comparison is run on tie-free data. County-level
columns are identical for every submarket in a county by construction, so real
runs do contain ties. If you want to be certain before an interview, put
`=PERCENTRANK.INC({10,10,30,40},10)` in a cell; Excel should return 0.

---

## The municipal attitude column

This is the one input that cannot be automated honestly. Whether a village
board will entertain a 300-unit garden-style community is a function of who
sits on the plan commission, what happened at the last rezoning hearing, and
whether the comprehensive plan has a multifamily land use category with any
land actually mapped to it. No API returns that.

So it is manual. `config/municipal_attitude.csv` is created and extended
automatically with a row per submarket. Fill in:

- `rating`: one of `supportive`, `leaning_supportive`, `neutral`,
  `leaning_hostile`, `hostile`
- `notes`, `evidence_url`, `researched_by`, `researched_on`

**A blank rating scores as MISSING, not as neutral.** That is deliberate. An
unresearched municipality can never quietly prop up a ranking.

The `unverified_ai_draft` column exists for a web-search draft note. It is
labelled unverified everywhere it appears, and it is a starting point for your
own reading, never a citation.

---

## Known limitations

Read this section before you show anyone the output.

**Geography**

- Centroids are Gazetteer internal points, not population-weighted. For a long
  thin township the point can sit somewhere nobody lives.
- Straight-line distance understates travel where water or a single river
  crossing forces a detour. Savannah is the obvious case.
- Employment centres are operator-set coordinates in the market YAML files.
  They are an input to the model, not an output of it. The Port of Savannah
  coordinate in particular is approximate and is flagged as such in the config.
- In Lexington and Savannah, **unincorporated county land is outside the screen
  entirely**, because it has no municipal government. In Savannah a large share
  of new rooftops sit in unincorporated Chatham and Bryan, which is the single
  biggest coverage gap in this tool.
- The place-to-county crosswalk assigns a multi-county place to the first
  county listed, not the one holding most of its population.

**Demographics**

- ACS 5-year estimates have wide margins of error in small places. The tool
  reports whether each growth figure clears its own 90% margin of error, in the
  `pop_growth_significant` and `hh_growth_significant` columns. A growth rate
  flagged `no` is inside sampling noise and should not be leaned on.
- ACS boundaries change. A place that annexed land between the two vintages
  shows growth that is partly annexation, not new households.
- 5-year estimates lag. A 2020-2024 release is centred on 2022.
- Median household income is place-wide and says nothing about the income of
  renter households specifically, which is what actually underwrites a rent
  roll.

**Jobs**

- QCEW and LAUS are **county-level**. Two submarkets in the same county will
  always score identically on them. These columns separate counties, not
  neighbourhoods, and every cell says so in its note.
- QCEW suppresses figures for confidentiality. A suppressed figure comes
  through as MISSING, never as a zero.

**Rents**

- ZORI is a repeat-rent index of **asking rents on Zillow listings**. It is
  smoothed, it is not a survey of the whole stock, and it skews to
  professionally managed and listed units. It is not the same thing as
  achieved rent on new garden-style product.
- Zillow drops small ZIPs for sample reasons. Where ZORI covers less than 25%
  of a submarket by area, the rent columns come through as MISSING rather than
  reporting a number from one unrepresentative ZIP.
- ZCTAs are Census approximations of ZIP codes built from blocks; Zillow keys
  on the postal ZIP. They agree for most residential ZIPs but not all, and
  there is no free exact crosswalk.
- HUD FMR is an administrative figure set for the housing choice voucher
  programme at roughly the 40th percentile of standard-quality rents. It is a
  floor-ish cross-check, not a market rent.

**Supply**

- This is the one to be most careful with. The Building Permits Survey reports
  by **permit-issuing place**. Many small municipalities do not issue their own
  permits; the county does. A jurisdiction that is genuinely building can show
  zero. The tool distinguishes four cases: a reported zero (value 0, with a
  note saying it was reported), a jurisdiction absent from the file (MISSING,
  "not a permit-issuing place in BPS"), a failed download (MISSING, with the
  error), and a **short window**, where the jurisdiction filed in only one or
  two of the three years. The last one matters because supply pressure is
  scored low is good, so a permit office that failed to file would otherwise
  look like a quiet, undersupplied submarket and climb the ranking on the
  strength of its own missing data. The raw counts still appear as context with
  the years listed; the scored per-1,000-household metrics go MISSING.
- It also reports each county's total and what share of it the screened
  jurisdictions actually capture, so you can see how much permitting the screen
  is not seeing.
- Permits are permits, not starts and not completions. Some never get built.

**Schools**

- The school proxy is **not a quality measure**. It is free and reduced price
  lunch share (inverted) and student-teacher ratio (inverted). FRPL is a
  measure of student poverty, and it correlates with test scores mostly because
  it proxies household income, which this screen already scores under the
  demand pillar. The two are therefore not independent evidence.
- A real underwriting process buys GreatSchools or Niche data, or pulls state
  assessment results. NCES EDFacts publishes district proficiency free, but in
  coarse bins that make small differences unusable.
- A submarket is assigned the district containing its centroid. Large
  municipalities split across several districts get only one of them.
- The composite uses only the components present for **every** submarket that
  has any school data. An average of two percentile ranks regresses toward 50
  while a single rank can sit at 5 or 95, so mixing the two shapes in one
  scored column would compare different things. If neither component covers the
  whole set, the column is not scored at all.
- The lookup needs `geopandas`, which is in `requirements-optional.txt` rather
  than the main install. Without it the school columns come through as MISSING
  rather than guessing, and CI runs without it on purpose so that degradation
  stays tested.

**Scoring**

- All scores are relative to the other submarkets in the same market. A 100 on
  rent growth means best of this group, not good in absolute terms. Scores are
  not comparable across markets.
- Some columns legitimately mix vintages across rows. ZORI takes each
  submarket's own latest month, and QCEW and LAUS probe back per county to the
  newest year that is not suppressed, so two counties can be compared over
  slightly different windows. Where that happens the workbook's vintage header
  says MIXED and lists them rather than printing one row's vintage over the
  whole column.
- Weighting is a judgement. That is why it lives in one editable file and one
  set of sliders.

---

## Project layout

```
config/
  weights.yml              pillar and metric weights, scoring method
  municipal_attitude.csv   your manual column, auto-created
  markets/*.yml            one per market: counties, geography, employment centres
screener/
  cli.py                   command line entry point
  cache.py                 on-disk HTTP cache, the thing that makes it work offline
  provenance.py            Value, MetricSpec, Unit. Nothing returns a bare float
  config.py, context.py    config loading
  assemble.py              builds the raw table for a market
  score.py                 the scoring maths
  excel.py                 the four-tab workbook with live formulas
  onepager.py              self-contained HTML, no CDN, no tile server
  metrics.py               registry, and the check that weights.yml is consistent
  sources/
    census_gazetteer.py    geographic spine
    census_place_county.py place to county crosswalk
    census_relationship.py ZCTA to submarket weights
    census_acs.py          demand
    bls_jobs.py            QCEW and LAUS
    rents.py               ZORI and HUD FMR
    census_bps.py          building permits
    schools.py             school proxy
    geo.py                 distance
    attitude.py            the manual column
app/streamlit_app.py       the interview demo
data/cache/                everything downloaded, gitignored
output/<market>/           raw.json, the workbook, the one-pager, gitignored
tests/                     run with .venv/bin/python -m pytest tests/ -q
```

CI runs the same suite on every push touching `submarket-screener/`, via
`.github/workflows/submarket-screener.yml`. It installs no API keys and has no
access to the data hosts, because every test here is offline by design: a test
that starts reaching the network is a bug and should fail in CI rather than
pass quietly on one machine.

## Outputs

`output/<market>/` gets three files:

- `<market>_submarket_screen.xlsx` with four tabs. **Ranking** is live and
  reorders when you change a weight. **Scoring** holds the editable weights and
  the `PERCENTRANK.INC` formulas. **Raw data** has source, vintage, retrieval
  date, URL, direction and metric key above every column, with MISSING cells
  shaded and a hover comment giving the reason. **Sources and gaps** lists
  every source and everything that is missing.
- `<market>_one_pager.html`, self-contained, prints to PDF from the browser.
  It carries the ranking, a position map drawn as inline SVG from the Gazetteer
  coordinates, three to four plain sentences on why the top submarket ranks
  first, what is missing, and the source list.
- `raw.json`, the frozen snapshot everything downstream reads.

The map is a position diagram, not a basemap. There is no free map tile
service that works offline, and a wrong basemap would be worse than none.

## Rules this code follows

1. No figure is ever invented or estimated. A value that cannot be obtained is
   MISSING with a specific reason, shown as MISSING in every output.
2. Zero is a real number. A reported zero and a non-report are different things
   and are never conflated.
3. Every figure carries its source, vintage, URL and retrieval timestamp.
4. A file layout that does not match expectations raises an error naming the
   file and what was expected. It never mis-parses quietly.
5. Free public sources only.
6. Downloads are cached so the demo works offline.
