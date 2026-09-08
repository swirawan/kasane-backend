# Frontend patch for Phase 5.1 backend

These four files are based on the current GitHub-ready KASANE frontend and add:

- `turnstileSiteKey` / `turnstileAction` config
- dynamically loaded Cloudflare Turnstile
- CAPTCHA token in the API payload
- hidden honeypot field
- better handling for API 400 / 403 / 429 responses
- CAPTCHA reset after submission attempts

Do **not** fill in `turnstileSiteKey` until the Cloudflare Turnstile widget exists.

After the backend deploys, set `briefEndpoint` in `config.js` to the CloudFormation/SAM output.
