"""Finance webhook: a fee or policy document was published -> governed chunk with source=finance."""
from pydantic import BaseModel

from connectors.governed import to_ingest


class FinancePolicyEvent(BaseModel):
    policy_id: str
    title: str
    body: str
    audience: str            # public | internal


def finance_to_ingest(e: FinancePolicyEvent) -> dict:
    return to_ingest("finance", f"fin-{e.policy_id}", e.title, e.body, e.audience)
