# Domain Checker API

This project exposes the domain generation logic via a FastAPI service.

## Setup

1. Copy `.env.example` to `.env` and fill in the API keys.
2. Install dependencies with `pip install -r requirements.txt`.
3. Start the server:

```bash
uvicorn api_server:app
```

The service requires `DOMAIN_API_KEY` for all requests using the `X-API-Key` header.

## Next.js Client

The `nextjs/` directory contains a minimal client example. Configure
`nextjs/.env.local` with:

```
DOMAIN_API_URL=http://localhost:8000
DOMAIN_API_KEY=<same key as server>
```

Use the helpers in `nextjs/lib/domainClient.ts` to interact with the API.
