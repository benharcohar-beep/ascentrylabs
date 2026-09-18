# Contract every module in `screener/sources/` must satisfy

Read `screener/provenance.py`, `screener/cache.py`, `screener/config.py` and
`screener/context.py` before writing anything. Do not modify them.

## Required module surface

```python
SOURCE_NAME: str          # human label, e.g. "Census Building Permits Survey"
METRICS: list[MetricSpec] # every metric key this module can produce
CONTEXT_COLUMNS: list[MetricSpec]  # unscored columns it also produces (scored=False)

def collect(ctx: Context, units: list[Unit]) -> dict[str, dict[str, Value]]:
    """Return {unit.geoid: {metric_key: Value}} for every unit passed in."""
```

## Hard rules

1. **Never invent or estimate a figure.** If a value cannot be obtained, return
   `provenance.missing("<specific reason>")`. Zero is a real number and must
   never be used to stand in for "not reported". A permit-issuing place that
   genuinely reported zero 5+ unit permits is different from a place that did
   not report, and the module must distinguish them.
2. **Every `Value` carries `source`, `vintage`, `url` and `retrieved_at`.**
   `retrieved_at` comes from `CachedResponse.retrieved_at`, not from
   `datetime.now()`.
3. **All network access goes through `ctx.cache.get(...)`.** Never call
   `requests` directly. Pass a stable `key=` that excludes any API key.
4. **Every unit in `units` must appear in the returned dict**, even if all its
   values are missing.
5. **Raise, do not guess, on a layout change.** If a downloaded file does not
   have the columns you expect, raise `FetchError` with a message naming the
   file and what was expected. A silently mis-parsed column is the worst
   possible outcome for this project.
6. **Missing free API key**: call `cache.require_key(ENV_NAME, how_to_get)`
   which raises `MissingCredential` with instructions. Do not fall back to an
   unauthenticated endpoint that returns different numbers.
7. **No em dashes or en dashes** anywhere, including comments and docstrings.
   Use commas, full stops or brackets.
8. **Comment the awkward bits.** A finance student has to explain this code
   line by line in an interview. Where a source has a real methodological
   catch (imputed months, suppressed small cells, boundary vintages), say so
   in a comment and put it in the `notes` field of the `Value`.
9. Write a short `# LIMITATIONS` block at the top of the module listing what
   this source cannot tell you. It gets pulled into the README.

## Units

`Unit` (see `screener/provenance.py`) has:
- `geoid`  7 chars for a place (state 2 + place 5), 10 chars for a county
  subdivision (state 2 + county 3 + cousub 5)
- `geo_type`  "place" or "county_subdivision"
- `state_fips` (2), `county_fips` (5), `county_name`
- `lat`, `lon`, `land_area_sqmi`
- `zctas`: list of `(zcta5, weight)` where weights sum to 1.0. Populated by
  `screener/sources/census_relationship.py` from the Census ZCTA relationship
  files, weighted by land area of overlap.

## Testing

Put a small, clearly synthetic fixture under `tests/fixtures/` and a test under
`tests/` that exercises your parser offline. Name fixture files
`*_SYNTHETIC_*` so nobody mistakes them for real data. Tests must not hit the
network. Run them with `python -m pytest tests/ -q` from
`submarket-screener/`.

## Environment note

The machine this is being written on blocks outbound access to every data host
(`api.census.gov`, `api.bls.gov`, `files.zillowstatic.com`, `www.huduser.gov`,
`www2.census.gov`, `nces.ed.gov` all return 403 at the egress proxy). You
therefore cannot validate a URL by calling it. Do not try, and do not work
around the proxy. Write the fetcher from documented layouts, be explicit in
comments about which URL patterns you are confident in and which the user must
confirm on first run, and make failures loud.
