import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from connectors.app import create_app
from connectors.finance import FinancePolicyEvent, finance_to_ingest
from connectors.lms import LmsPageEvent, lms_to_ingest

ROOT = Path(__file__).resolve().parent.parent


def test_lms_staff_page_becomes_internal_staff_chunk_with_source_tag():
    body = lms_to_ingest(LmsPageEvent(event="page.updated", course_id="BUS101", page_id="p7", title="Marking guide",
                                      body_html="<p>Use the <b>rubric</b>.</p>", visibility="staff"))
    assert body == {"source": "lms", "doc_id": "lms-BUS101-p7", "text": "# Marking guide\n\nUse the rubric.",
                    "classification": "internal", "acl": "staff"}


def test_finance_public_policy_and_unknown_visibility_refused():
    body = finance_to_ingest(FinancePolicyEvent(policy_id="fees-2026", title="Fees", body="R12 500", audience="public"))
    assert (body["source"], body["classification"], body["acl"]) == ("finance", "public", "public")
    with pytest.raises(ValueError):
        finance_to_ingest(FinancePolicyEvent(policy_id="x", title="x", body="x", audience="everyone"))


def test_hooks_forward_to_core_ingest():
    seen = []

    def core_handler(req: httpx.Request):
        seen.append((req.url.path, json.loads(req.content)))
        return httpx.Response(202, json={"doc_id": "d", "chunk_ids": ["abc"]})

    core = httpx.Client(base_url="http://core", transport=httpx.MockTransport(core_handler))
    c = TestClient(create_app(core=core))
    r = c.post("/hooks/finance", json={"policy_id": "p1", "title": "Refunds", "body": "30 days", "audience": "internal"})
    assert r.status_code == 202 and r.json()["chunk_ids"] == ["abc"]
    assert seen[0][0] == "/ingest" and seen[0][1]["acl"] == "staff"


def test_n8n_flow_posts_to_hooks_ticket_and_reads_slack_text():
    flow = json.loads((ROOT / "n8n" / "ticket.flow.json").read_text())
    nodes = {n["name"]: n for n in flow["nodes"]}
    http = next(n for n in nodes.values() if n["type"] == "n8n-nodes-base.httpRequest")
    assert http["parameters"]["url"].endswith("/hooks/ticket") and http["parameters"]["method"] == "POST"
    setn = next(n for n in nodes.values() if n["type"] == "n8n-nodes-base.set")
    assert any("$json.slack_text" in a["value"] for a in setn["parameters"]["assignments"]["assignments"])
    for src, out in flow["connections"].items():
        assert src in nodes and all(t["node"] in nodes for branch in out["main"] for t in branch)
