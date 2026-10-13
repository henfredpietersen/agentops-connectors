"""LMS webhook: a course page was created or updated -> governed chunk with source=lms."""
from pydantic import BaseModel

from connectors.governed import to_ingest


class LmsPageEvent(BaseModel):
    event: str               # page.created | page.updated
    course_id: str
    page_id: str
    title: str
    body_html: str
    visibility: str          # students | staff


def lms_to_ingest(e: LmsPageEvent) -> dict:
    return to_ingest("lms", f"lms-{e.course_id}-{e.page_id}", e.title, e.body_html, e.visibility)
