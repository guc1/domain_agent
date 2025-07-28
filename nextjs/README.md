# Next.js Client

These files demonstrate how to call the FastAPI domain service from a Next.js app.

1. Copy `.env.local.example` to `.env.local` and provide the API values.
2. Use the helper functions in `lib/domainClient.ts` to start a session and submit answers.
3. The API route under `app/api/domain/route.ts` proxies requests from the UI.
