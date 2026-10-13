"""End to end against agentops-loop in-process. Runs when the core repo is on PYTHONPATH (CI checks it out)."""
import pytest
from fastapi.testclient import TestClient

from connectors.app import create_app
from connectors.fake_sf import CLIENT_ID, CLIENT_SECRET
from connectors.fake_sf import create_app as fake_sf
from connectors.salesforce import SalesforceClient

core_api = pytest.importorskip("app.api", reason="agentops-loop not on PYTHONPATH")


def _app():
    core = TestClient(core_api.app)
    sf = SalesforceClient(TestClient(fake_sf()), CLIENT_ID, CLIENT_SECRET)
    return TestClient(create_app(core=core, sf=sf))


def test_salesforce_case_is_answered_by_core_with_citations():
    r = _app().post("/hooks/salesforce/case", json={"case_id": "500FAKE0001"})
    body = r.json()
    assert r.status_code == 202 and body["ticket_id"] == "sf-00001001"
    assert body["route"] == "refund" and not body["refused"] and body["citations"]
    assert body["slack_text"].startswith("*Ticket sf-00001001*")


def test_phone_number_in_case_never_reaches_core_trace_or_answer():
    body = _app().post("/hooks/salesforce/case", json={"case_id": "500FAKE0002"}).json()
    assert "082 555 0101" not in str(body)


def test_lms_hook_ingests_into_core():
    r = _app().post("/hooks/lms", json={"event": "page.created", "course_id": "BUS101", "page_id": "p1", "title": "Library",
                                        "body_html": "<p>The e-library is open 24 hours.</p>", "visibility": "students"})
    assert r.status_code == 202 and len(r.json()["chunk_ids"]) == 1
