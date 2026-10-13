"""Salesforce connector: OAuth2 client-credentials with a cached, refreshed token; Case -> ticket.

Client credentials
    POST {login}/services/oauth2/token  grant_type=client_credentials&client_id=..&client_secret=..
    The token is cached until `expires_in - skew` seconds, refreshed early, and refreshed once more
    if the API answers 401 INVALID_SESSION_ID (revoked or expired server-side).

JWT bearer (server-to-server, no secret on the wire)
    1. Create a connected app with "Use digital signatures" and upload the X.509 cert.
    2. Sign a JWT with RS256 using the private key: iss=consumer key, sub=integration username,
       aud=https://login.salesforce.com (or test.salesforce.com), exp=now+3 minutes.
    3. POST grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer&assertion=<jwt>.
    `build_jwt_assertion` and `token_via_jwt` below do this; the fake org verifies it with a test key.

Secrets come from the environment. Nothing in this repo is a real connected-app secret.
"""
import time

import httpx
import jwt

API = "/services/data/v60.0"


def build_jwt_assertion(client_id: str, username: str, audience: str, private_key_pem: str, lifetime: int = 180,
                        clock=time.time) -> str:
    now = int(clock())
    return jwt.encode({"iss": client_id, "sub": username, "aud": audience, "exp": now + lifetime}, private_key_pem, algorithm="RS256")


class SalesforceClient:
    def __init__(self, http: httpx.Client, client_id: str, client_secret: str | None = None,
                 jwt_assertion_fn=None, skew: int = 30, clock=time.time):
        self.http, self.client_id, self.client_secret = http, client_id, client_secret
        self.jwt_assertion_fn, self.skew, self.clock = jwt_assertion_fn, skew, clock
        self._token, self._expires_at = None, 0.0
        self.refreshes = 0

    def _fetch_token(self) -> None:
        if self.jwt_assertion_fn:
            data = {"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": self.jwt_assertion_fn()}
        else:
            data = {"grant_type": "client_credentials", "client_id": self.client_id, "client_secret": self.client_secret}
        r = self.http.post("/services/oauth2/token", data=data)
        r.raise_for_status()
        body = r.json()
        self._token = body["access_token"]
        self._expires_at = self.clock() + int(body.get("expires_in", 3600)) - self.skew
        self.refreshes += 1

    def token(self) -> str:
        if not self._token or self.clock() >= self._expires_at:
            self._fetch_token()
        return self._token

    def _get(self, path: str) -> dict:
        r = self.http.get(path, headers={"Authorization": f"Bearer {self.token()}"})
        if r.status_code == 401:  # revoked server-side: refresh once and retry
            self._fetch_token()
            r = self.http.get(path, headers={"Authorization": f"Bearer {self._token}"})
        r.raise_for_status()
        return r.json()

    def get_case(self, case_id: str) -> dict:
        return self._get(f"{API}/sobjects/Case/{case_id}")


def case_to_ticket(case: dict) -> dict:
    """Map a Case to the agentops-loop ticket body. The caller is a student, so role is public.
    PII (SuppliedEmail) is not copied; the core service redacts anything left in the text."""
    return {"ticket": f"{case['Subject']}. {case['Description']}", "role": "public", "ticket_id": f"sf-{case['CaseNumber']}"}
