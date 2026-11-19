"""Extract NFIP data from the OpenFEMA API into Parquet files, one file per page."""

from __future__ import annotations

import logging
import shutil
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests

BASE_URL = "https://www.fema.gov/api/open/v3"
log = logging.getLogger(__name__)

# Errors where trying again can help: slow server, dropped or cut-off connection.
RETRYABLE = (
    requests.Timeout,
    requests.ConnectionError,
    requests.exceptions.ChunkedEncodingError,  # response cut off halfway
    requests.exceptions.JSONDecodeError,  # response arrived incomplete
)

CLAIMS_COLS = (
    "id,asOfDate,dateOfLoss,yearOfLoss,state,countyCode,censusGeoid,ratedFloodZone,"
    "occupancyType,elevatedBuildingIndicator,floodEvent,causeOfDamage,"
    "amountPaidOnBuildingClaim,amountPaidOnContentsClaim,buildingDamageAmount,"
    "totalBuildingInsuranceCoverage"
)
POLICY_COLS = (
    "id,asOfDate,policyEffectiveDate,policyTerminationDate,propertyState,censusGeoid,"
    "ratedFloodZone,totalInsurancePremiumOfThePolicy,totalBuildingInsuranceCoverage,"
    "policyCount,occupancyType,elevatedBuildingIndicator"
)


def fetch_page(session, entity, params, retries=3, backoff=2.0, timeout=60):
    """Fetch one page. Retry timeouts and broken connections, but not our own mistakes (4xx)."""
    url = f"{BASE_URL}/{entity}"
    for attempt in range(1, retries + 1):
        try:
            r = session.get(url, params=params, timeout=timeout)
            if r.status_code < 500:
                r.raise_for_status()  # a 4xx means the request is wrong: fail now
                return r.json()[entity]
            error = requests.HTTPError(f"server error {r.status_code}")
        except RETRYABLE as exc:
            error = exc
        if attempt == retries:
            raise error
        wait = backoff**attempt
        log.warning("%s (attempt %d/%d), retrying in %.0fs", error, attempt, retries, wait)
        time.sleep(wait)


def month_windows(start, end):
    """Yield (first day of month, first day of next month) from start's month until end."""
    cur = date(start.year, start.month, 1)
    while cur < end:
        nxt = date(cur.year + cur.month // 12, cur.month % 12 + 1, 1)
        yield cur, nxt
        cur = nxt


def iso(d):
    return f"'{d.isoformat()}T00:00:00.000Z'"


def extract(entity, filter_, select, out_root="data/raw", page_size=5000, session=None,
            timeout=60, retries=3, date_field=None, start=None, end=None):
    """Page through the API sorted by id and write each page to data/raw/<entity>/asof=<date>/.

    With date_field and start, the query is split into one-month windows, so the server
    only has to sort one month of rows at a time.
    """
    session = session or requests.Session()
    if date_field:
        windows = [
            f"{filter_} and {date_field} ge {iso(a)} and {date_field} lt {iso(b)}"
            for a, b in month_windows(start, end or date.today())
        ]
    else:
        windows = [filter_]

    params = {"$select": select, "$orderby": "id", "$top": page_size}
    page_no, total = 0, 0
    out_dir, asof = None, None

    for window in windows:
        skip = 0
        while True:
            rows = fetch_page(session, entity, {**params, "$filter": window, "$skip": skip},
                              retries=retries, timeout=timeout)
            if not rows:
                break
            if out_dir is None:
                asof = rows[0]["asOfDate"][:10]
                out_dir = Path(out_root) / entity / f"asof={asof}"
                if out_dir.exists():
                    shutil.rmtree(out_dir)  # a rerun of the same month replaces it
                out_dir.mkdir(parents=True)
            if any(row["asOfDate"][:10] != asof for row in rows):
                raise RuntimeError("Source was refreshed during the extract. Run it again.")

            pd.DataFrame(rows).to_parquet(out_dir / f"page_{page_no:05d}.parquet", index=False)
            total += len(rows)
            page_no += 1
            log.info("%s page %d: %d rows (total %d)", entity, page_no, len(rows), total)

            if len(rows) < page_size:
                break
            skip += page_size

    return total, out_dir


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    extract("NfipClaims", "state eq 'NC' and yearOfLoss ge 2019", CLAIMS_COLS)
    extract(
        "NfipPolicies",
        "propertyState eq 'NC'",
        POLICY_COLS,
        date_field="policyEffectiveDate",
        start=date(2019, 1, 1),
        timeout=120,
        retries=5,
    )