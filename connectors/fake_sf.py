"""A local fake of the slice of Salesforce this repo needs. No real org, no real secret.

Endpoints: POST /services/oauth2/token (client_credentials and JWT bearer),
GET /services/data/v60.0/sobjects/Case/{id}. Expired or unknown tokens get 401 INVALID_SESSION_ID.
"""
import os
import secrets
import time

import jwt
from fastapi import FastAPI, Form, Header, HTTPException

CLIENT_ID = os.environ.get("FAKE_SF_CLIENT_ID", "fake-connected-app")
CLIENT_SECRET = os.environ.get("FAKE_SF_CLIENT_SECRET", "local-fake-secret-not-real")
LOGIN_URL = "https://login.fake-salesforce.local"

CASES = {
    "500FAKE0001": {"Id": "500FAKE0001", "CaseNumber": "00001001", "Status": "New", "Origin": "Web", "Priority": "Medium",
                    "Subject": "Approved refund", "SuppliedEmail": "thandi.m@example.com",
                    "Description": "How long does it take for an approved refund to be paid back to the original payment method?"},
    "500FAKE0002": {"Id": "500FAKE0002", "CaseNumber": "00001002", "Status": "New", "Origin": "Email", "Priority": "Low",
                    "Subject": "Locked out", "SuppliedEmail": "sipho.k@example.com",
                    "Description": "My LMS account is locked after too many failed login attempts. Call me on 082 555 0101."},
}


def create_app(token_ttl: int = 3600, clock=time.time, jwt_public_keys: dict | None = None) -> FastAPI:
    app = FastAPI(title="fake-salesforce")
    app.state.tokens = {}          # token -> expiry
    app.state.issued = 0
    app.state.jwt_keys = jwt_public_keys or {}  # client_id -> PEM public key

    def issue():
        tok = "00DFAKE!" + secrets.token_urlsafe(24)
        app.state.tokens[tok] = clock() + token_ttl
        app.state.issued += 1
        return {"access_token": tok, "instance_url": "http://fake-sf", "token_type": "Bearer",
                "issued_at": str(int(clock() * 1000)), "expires_in": token_ttl}

    @app.post("/services/oauth2/token")
    def token(grant_type: str = Form(...), client_id: str = Form(None), client_secret: str = Form(None), assertion: str = Form(None)):
        if grant_type == "client_credentials":
            if client_id != CLIENT_ID or client_secret != CLIENT_SECRET:
                raise HTTPException(400, {"error": "invalid_client"})
            return issue()
        if grant_type == "urn:ietf:params:oauth:grant-type:jwt-bearer":
            try:
                iss = jwt.decode(assertion, options={"verify_signature": False})["iss"]
                jwt.decode(assertion, app.state.jwt_keys[iss], algorithms=["RS256"], audience=LOGIN_URL)
            except Exception:
                raise HTTPException(400, {"error": "invalid_grant"})
            return issue()
        raise HTTPException(400, {"error": "unsupported_grant_type"})

    @app.get("/services/data/v60.0/sobjects/Case/{case_id}")
    def get_case(case_id: str, authorization: str = Header("")):
        tok = authorization.removeprefix("Bearer ")
        if app.state.tokens.get(tok, 0) <= clock():
            raise HTTPException(401, [{"errorCode": "INVALID_SESSION_ID", "message": "Session expired or invalid"}])
        if case_id not in CASES:
            raise HTTPException(404, [{"errorCode": "NOT_FOUND"}])
        return CASES[case_id]

    return app


app = create_app()
