"""Tests for CSV lead import (Salesbot.io / Bowtie export)."""

import pytest
from fastapi.testclient import TestClient

from app.leads import (
    clear_imported_leads,
    get_lead,
    import_leads_from_csv,
    list_leads,
    parse_leads_csv,
)
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _isolate_leads():
    """Keep imported-lead state from leaking between tests."""
    clear_imported_leads()
    yield
    clear_imported_leads()


BOWTIE_CSV = (
    "First Name,Last Name,Title,Company,Industry,Email,Fit Reason,Fit Score\n"
    "Dana,Whitfield,Director of Demand Gen,Lumen Apparel,E-commerce,dana@lumen.example,Scaling paid social fast,91\n"
    "Rafael,Ortega,VP RevOps,Cobalt Freight,Logistics SaaS,rafael@cobalt.example,Expanded SDR team,86\n"
)

NAME_COL_CSV = (
    "Name,Job Title,Account,Work Email,Score\n"
    "Sam Rivera,Growth Lead,Acme Co,sam@acme.example,70\n"
)


def test_parse_first_last_and_fields():
    leads = parse_leads_csv(BOWTIE_CSV)
    assert len(leads) == 2
    assert leads[0].name == "Dana Whitfield"
    assert leads[0].title == "Director of Demand Gen"
    assert leads[0].company == "Lumen Apparel"
    assert leads[0].fit_score == 91
    assert "paid social" in leads[0].fit_reason


def test_parse_single_name_and_alias_headers():
    leads = parse_leads_csv(NAME_COL_CSV)
    assert len(leads) == 1
    assert leads[0].name == "Sam Rivera"
    assert leads[0].title == "Growth Lead"
    assert leads[0].company == "Acme Co"
    assert leads[0].email == "sam@acme.example"
    assert leads[0].fit_score == 70


def test_import_activates_leads():
    imported = import_leads_from_csv(BOWTIE_CSV)
    assert len(imported) == 2
    names = [l.name for l in list_leads()]
    assert "Dana Whitfield" in names
    # SDR uses get_lead; the first imported lead should be selectable
    assert get_lead(imported[0].id).company == "Lumen Apparel"


def test_import_rejects_empty_or_bad_csv():
    with pytest.raises(ValueError):
        import_leads_from_csv("not,really\n,\n")


def test_import_endpoint():
    resp = client.post(
        "/api/leads/import", content=BOWTIE_CSV, headers={"Content-Type": "text/csv"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["imported"] == 2
    assert body["leads"][0]["name"] == "Dana Whitfield"
    # GET now reflects imported leads
    listing = client.get("/api/leads").json()
    assert any(l["name"] == "Rafael Ortega" for l in listing)


def test_import_endpoint_rejects_empty():
    resp = client.post("/api/leads/import", content="   ", headers={"Content-Type": "text/csv"})
    assert resp.status_code == 400
