# agentops-connectors

![ci](https://github.com/henfredpietersen/agentops-connectors/actions/workflows/ci.yml/badge.svg)

These are the integrations for [agentops-loop](https://github.com/henfredpietersen/agentops-loop). Each one takes data from an outside system and gives it to the core service in a governed shape. Salesforce Cases become tickets, LMS pages and finance policies become ACL-tagged chunks, and an n8n flow posts a ticket and reads back `slack_text`. Everything runs locally, and no paid account is needed.

| File | What it does |
|---|---|
| `connectors/fake_sf.py` | A local fake Salesforce org: an OAuth token endpoint (client credentials and JWT bearer) and Case reads. It returns `401 INVALID_SESSION_ID` when a token has expired or been revoked. |
| `connectors/salesforce.py` | The OAuth2 client-credentials client. It caches the token, refreshes it before it expires, and refreshes once more on a 401. The JWT bearer flow is documented and implemented in the same module. `case_to_ticket` maps a Case to the core ticket body and leaves out `SuppliedEmail`. |
| `connectors/lms.py`, `connectors/finance.py` | Webhook in, governed chunk out. The source tag is set, and visibility maps to `classification` and `acl`. An unknown visibility value is refused rather than guessed. |
| `connectors/app.py` | `POST /hooks/lms`, `/hooks/finance` and `/hooks/salesforce/case`. Each forwards to the core service at `CORE_URL` and returns 202. |
| `n8n/ticket.flow.json` | Webhook → `POST /hooks/ticket` → read `slack_text` → respond. |

## Run it

```bash
pip install -r requirements.txt
python -m pytest -q                                   # 8 tests here + 3 end-to-end tests that need the core repo

# with agentops-loop running on :8080
uvicorn connectors.fake_sf:app --port 8091 &
cp .env.example .env && set -a && . ./.env && set +a
uvicorn connectors.app:create_app --factory --port 8090 &
curl -s -X POST localhost:8090/hooks/salesforce/case -H 'content-type: application/json' -d '{"case_id":"500FAKE0001"}'
# HTTP 202, route "refund", cited answer:
# "Approved refunds are paid back to the original payment method within 10 business days."
```

**Importing the n8n flow:** in n8n, go to **Workflows → Add workflow → ⋯ menu (top right) → Import from File...**, pick `n8n/ticket.flow.json`, and save. Set `AGENTOPS_URL` if the core service is not at `http://host.docker.internal:8080`. Then activate the flow and POST `{"ticket": "...", "role": "public"}` to the webhook URL that n8n shows.

## Honesty block

**Built and runnable:** the commands above. CI runs the unit tests. It also runs a second job that checks out agentops-loop and puts a fake Salesforce Case through the real core service in-process: a Case becomes a ticket, the core service answers with a citation, and a phone number from the Case never appears in the response.

**Stand-ins:**
- Salesforce is a local fake. It has invented Cases, and the client secret is a placeholder that only works against the fake.
- The JWT flow is tested with an RSA key generated during the test.
- The client uses one base URL for both the token call and the API calls. A real org returns an `instance_url` for API calls, and this client does not switch to it yet.
- The n8n flow is valid JSON and is checked by a structure test, but it has not been imported into a running n8n instance.

**Not claimed:** a real Salesforce org, real LMS or finance systems, production traffic.

**How it was built:** AI-assisted. Henfred Pietersen set the spec, directed the build, reviewed the output and ran the checks. The code was generated with Claude.
