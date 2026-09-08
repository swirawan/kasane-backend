# KASANE Backend — Phase 5.1

Production-oriented AWS/Python backend for the KASANE COLLECTIVE event brief form.

## Architecture

`GitHub Pages frontend -> API Gateway HTTP API -> Python Lambda -> DynamoDB -> SES`

Cloudflare Turnstile is validated **server-side** by Lambda before a public brief is accepted. The Lambda never stores the CAPTCHA token or raw visitor IP.

### Implemented now

- `POST /v1/briefs`
- `GET /health`
- server-side validation matching the KASANE form
- preferred-contact rules:
  - WhatsApp / Call / SMS => phone required
  - Email => valid email required
- Cloudflare Turnstile integration, switchable on after keys are ready
- honeypot bot trap
- DynamoDB persistence with generated `KAS-YYMMDD-XXXXXX` references
- DynamoDB encryption, PITR and TTL
- SES notification email, switchable on after SES is ready
- API Gateway throttling
- CORS for `https://swirawan.github.io`
- no PII in normal logs
- unit tests

## Why a separate backend repo

Keep this code in a repository such as `kasane-backend`. Do not put AWS credentials, Turnstile secrets, or other server secrets in the public static website repo.

## Prerequisites

Install/configure:

1. AWS CLI v2
2. AWS SAM CLI
3. Python 3.13 locally (3.12 is also fine for local tests)
4. AWS credentials for the account you want to use

Suggested AWS region: choose the region you intend to keep for the business. `ap-southeast-1` (Singapore) is a sensible low-latency choice for Indonesia. If you use SES, verify that SES is configured in the same region as this stack.

## Local test

```bash
python -m venv .venv
source .venv/bin/activate  # Windows Git Bash: source .venv/Scripts/activate
pip install -r requirements-dev.txt
pytest -q
```

When SAM CLI is installed:

```bash
sam build
sam local invoke BriefFunction -e events/brief.json
```

## First AWS deployment: DEV, no CAPTCHA/email yet

This lets you prove API Gateway + Lambda + DynamoDB before adding external dependencies.

```bash
sam build
sam deploy --guided
```

Recommended answers:

- Stack name: `kasane-backend-dev`
- Region: `ap-southeast-1`
- StageName: `dev`
- AllowedOrigins: `https://swirawan.github.io`
- AllowedOriginsEnv: `https://swirawan.github.io`
- CaptchaRequired: `false`
- EmailEnabled: `false`
- TurnstileExpectedHostnames: `swirawan.github.io`
- Allow SAM to create IAM roles: `Y`
- Save arguments to config: `Y`

After deployment, copy the `BriefEndpoint` output.

## Connect the static frontend

In the KASANE frontend `config.js`:

```js
window.KASANE_CONFIG = Object.freeze({
  contactEmail: 'hello@kasanecollective.com',
  briefEndpoint: 'PASTE_BRIEF_ENDPOINT_HERE',
  requestTimeoutMs: 12000,
  turnstileSiteKey: '',
  turnstileAction: 'kasane_brief'
});
```

Use the included `frontend-patch/` files when you are ready for CAPTCHA. The patch keeps Turnstile hidden until a site key exists.

## Turnstile CAPTCHA

Create a Turnstile widget in Cloudflare and allow the staging hostname:

- `swirawan.github.io`

Later add:

- `kasanecollective.com`
- `www.kasanecollective.com`

After the stack is deployed, find the `TurnstileSecretArn` output and set the actual secret:

```bash
./scripts/set_turnstile_secret.sh '<TURNSTILE_SECRET_ARN>' '<YOUR_SECRET>'
```

Then redeploy with:

```text
CaptchaRequired=true
```

and place the public **site key** (not the secret) in frontend `config.js` as `turnstileSiteKey`.

Turnstile tokens must be validated on the server. They expire after a few minutes and are single-use, which is why the frontend resets the widget after a rejected submission.

## SES email notification

For the first test, you can verify an email address in Amazon SES. While SES is in sandbox, both sender and recipients may need to be verified.

Later, after you own `kasanecollective.com`, verify the **domain** in SES and publish the provided DNS records. Then use addresses such as:

- `hello@kasanecollective.com`
- `stanley@kasanecollective.com`
- `davin@kasanecollective.com`

Deploy with parameters similar to:

```text
EmailEnabled=true
FromEmail=hello@kasanecollective.com
NotificationEmails=stanley@kasanecollective.com,davin@kasanecollective.com
```

## Production later

For the custom domain, update both API CORS and Lambda origin validation:

```text
AllowedOrigins=https://kasanecollective.com,https://www.kasanecollective.com
AllowedOriginsEnv=https://kasanecollective.com,https://www.kasanecollective.com
TurnstileExpectedHostnames=kasanecollective.com,www.kasanecollective.com
```

You can keep the frontend on GitHub Pages initially. Later Phase 5.2 can move to:

`GitHub Actions -> S3 -> CloudFront -> kasanecollective.com`

and add an API custom domain such as `api.kasanecollective.com`.

## Future backend modules (not added yet)

Intentionally not included until needed:

- MUSUBI shared RSVP/wishes backend
- WhatsApp Business API delivery
- Instagram auto-feed
- internal lead dashboard
- CMS / case studies

Keeping them out now avoids unused code and keeps the first production stack small.
