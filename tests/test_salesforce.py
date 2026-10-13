import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from connectors.fake_sf import CLIENT_ID, CLIENT_SECRET, LOGIN_URL, create_app
from connectors.salesforce import SalesforceClient, build_jwt_assertion, case_to_ticket


class Clock:
    def __init__(self):
        self.t = 1_000_000.0

    def __call__(self):
        return self.t


def test_token_is_cached_then_refreshed_on_expiry_and_on_401():
    clock = Clock()
    fake = create_app(token_ttl=120, clock=clock)
    sf = SalesforceClient(TestClient(fake), CLIENT_ID, CLIENT_SECRET, skew=30, clock=clock)
    first = sf.token()
    assert sf.token() == first and fake.state.issued == 1          # cached
    clock.t += 95                                                  # past expires_in - skew
    assert sf.get_case("500FAKE0001")["CaseNumber"] == "00001001"
    assert sf._token != first and fake.state.issued == 2           # refreshed early
    fake.state.tokens.clear()                                      # server-side revoke
    assert sf.get_case("500FAKE0002")["Subject"] == "Locked out"
    assert fake.state.issued == 3                                  # refreshed on 401, retried once


def test_case_becomes_ticket_without_supplied_email():
    sf = SalesforceClient(TestClient(create_app()), CLIENT_ID, CLIENT_SECRET)
    t = case_to_ticket(sf.get_case("500FAKE0001"))
    assert t == {"ticket": "Approved refund. How long does it take for an approved refund to be paid back to the original payment method?",
                 "role": "public", "ticket_id": "sf-00001001"}
    assert "@" not in t["ticket"]


def test_wrong_secret_is_rejected():
    r = TestClient(create_app()).post("/services/oauth2/token", data={"grant_type": "client_credentials", "client_id": CLIENT_ID, "client_secret": "nope"})
    assert r.status_code == 400


def test_jwt_bearer_flow_against_fake_org():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    pub = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    fake = create_app(jwt_public_keys={CLIENT_ID: pub})
    sf = SalesforceClient(TestClient(fake), CLIENT_ID, jwt_assertion_fn=lambda: build_jwt_assertion(CLIENT_ID, "integration@fake", LOGIN_URL, priv))
    assert sf.get_case("500FAKE0001")["Id"] == "500FAKE0001"
    claims = jwt.decode(build_jwt_assertion(CLIENT_ID, "u", LOGIN_URL, priv), pub, algorithms=["RS256"], audience=LOGIN_URL)
    assert claims["iss"] == CLIENT_ID and claims["exp"] > 0
