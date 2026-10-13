"""Webhook in, governed chunk out. Each source maps its own visibility flag to classification + acl."""
import html
import re

import httpx

VISIBILITY = {"students": ("public", "public"), "public": ("public", "public"),
              "staff": ("internal", "staff"), "internal": ("internal", "staff")}


def strip_html(s: str) -> str:
    s = re.sub(r"<(br|/p|/li|/h\d)\s*/?>", "\n", s, flags=re.I)
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def to_ingest(source: str, doc_id: str, title: str, body: str, visibility: str) -> dict:
    if visibility not in VISIBILITY:
        raise ValueError(f"unknown visibility {visibility!r}; refusing to guess an acl")
    classification, acl = VISIBILITY[visibility]
    return {"source": source, "doc_id": doc_id, "text": f"# {title}\n\n{strip_html(body)}",
            "classification": classification, "acl": acl}


def forward(core: httpx.Client, body: dict) -> httpx.Response:
    return core.post("/ingest", json=body)
