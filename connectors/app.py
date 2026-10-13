"""Connector service. Forwards to agentops-loop at CORE_URL (default http://localhost:8080)."""
import os

import httpx
from fastapi import FastAPI
from pydantic import BaseModel

from connectors.finance import FinancePolicyEvent, finance_to_ingest
from connectors.lms import LmsPageEvent, lms_to_ingest
from connectors.salesforce import SalesforceClient, case_to_ticket


def create_app(core: httpx.Client | None = None, sf: SalesforceClient | None = None) -> FastAPI:
    app = FastAPI(title="agentops-connectors")
    core = core or httpx.Client(base_url=os.environ.get("CORE_URL", "http://localhost:8080"), timeout=30)
    if sf is None and os.environ.get("SF_CLIENT_SECRET"):
        sf = SalesforceClient(httpx.Client(base_url=os.environ["SF_LOGIN_URL"]),
                              os.environ["SF_CLIENT_ID"], os.environ["SF_CLIENT_SECRET"])

    class CaseRef(BaseModel):
        case_id: str

    @app.post("/hooks/lms", status_code=202)
    def lms(e: LmsPageEvent):
        return core.post("/ingest", json=lms_to_ingest(e)).json()

    @app.post("/hooks/finance", status_code=202)
    def finance(e: FinancePolicyEvent):
        return core.post("/ingest", json=finance_to_ingest(e)).json()

    @app.post("/hooks/salesforce/case", status_code=202)
    def salesforce_case(ref: CaseRef):
        return core.post("/hooks/ticket", json=case_to_ticket(sf.get_case(ref.case_id))).json()

    return app
