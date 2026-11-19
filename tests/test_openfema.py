from datetime import date

import pandas as pd
import pytest
import requests

from ingest import openfema


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


class FakeSession:
    """Plays back prepared responses and records the parameters of every call."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append(params)
        nxt = self.responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


def make_rows(start, n):
    return [
        {"id": i, "asOfDate": "2026-11-16T00:00:00.000Z", "state": "NC"}
        for i in range(start, start + n)
    ]


def page(rows):
    return FakeResponse({"metadata": {}, "NfipClaims": rows})


def run_extract(session, tmp_path):
    return openfema.extract(
        "NfipClaims", "x", "id,asOfDate,state",
        out_root=tmp_path, page_size=2, session=session,
    )


def test_pages_until_a_short_page(tmp_path):
    s = FakeSession([page(make_rows(0, 2)), page(make_rows(2, 1))])
    total, out_dir = run_extract(s, tmp_path)
    assert total == 3
    assert [c["$skip"] for c in s.calls] == [0, 2]
    assert all(c["$orderby"] == "id" for c in s.calls)
    assert len(pd.read_parquet(out_dir)) == 3


def test_rerun_replaces_instead_of_duplicating(tmp_path):
    for _ in range(2):
        _, out_dir = run_extract(FakeSession([page(make_rows(0, 1))]), tmp_path)
    assert len(list(out_dir.glob("*.parquet"))) == 1


def test_retries_timeouts_and_server_errors(monkeypatch):
    monkeypatch.setattr(openfema.time, "sleep", lambda s: None)
    s = FakeSession([requests.Timeout(), FakeResponse({}, 503), page(make_rows(0, 1))])
    rows = openfema.fetch_page(s, "NfipClaims", {})
    assert len(rows) == 1
    assert len(s.calls) == 3


def test_client_errors_are_not_retried(monkeypatch):
    monkeypatch.setattr(openfema.time, "sleep", lambda s: None)
    s = FakeSession([FakeResponse({}, 400)])
    with pytest.raises(requests.HTTPError):
        openfema.fetch_page(s, "NfipClaims", {})
    assert len(s.calls) == 1
    
    
def test_retries_broken_connections(monkeypatch):
    monkeypatch.setattr(openfema.time, "sleep", lambda s: None)
    s = FakeSession([requests.exceptions.ChunkedEncodingError(), page(make_rows(0, 1))])
    rows = openfema.fetch_page(s, "NfipClaims", {})
    assert len(rows) == 1
    assert len(s.calls) == 2


def test_month_windows_cover_a_year_boundary():
    windows = list(openfema.month_windows(date(2019, 11, 15), date(2020, 2, 1)))
    assert windows == [
        (date(2019, 11, 1), date(2019, 12, 1)),
        (date(2019, 12, 1), date(2020, 1, 1)),
        (date(2020, 1, 1), date(2020, 2, 1)),
    ]


def test_extract_queries_one_month_at_a_time(tmp_path):
    s = FakeSession([page(make_rows(0, 1)), page(make_rows(1, 1))])
    total, _ = openfema.extract(
        "NfipClaims", "state eq 'NC'", "id,asOfDate,state", out_root=tmp_path,
        page_size=2, session=s, date_field="dateOfLoss",
        start=date(2019, 1, 1), end=date(2019, 3, 1),
    )
    assert total == 2
    assert "ge '2019-01-01" in s.calls[0]["$filter"]
    assert "lt '2019-02-01" in s.calls[0]["$filter"]
    assert "ge '2019-02-01" in s.calls[1]["$filter"]