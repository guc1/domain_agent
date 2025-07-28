# Domain Checker API

This project exposes the domain generation logic via a FastAPI service.

## Setup

1. Copy `.env.example` to `.env` and fill in the API keys.
2. Install dependencies with `pip install -r requirements.txt`.
3. Start the server:

```bash
uvicorn api_server:app
```

All requests must include `X-API-Key` set to the value of `DOMAIN_API_KEY`.

## API Overview

The service mirrors the interactive CLI in four small steps:

1. **Start a session** – `POST /sessions` with `{ "initial_brief": "..." }`.
   Returns the `session_id` and first clarification questions.
2. **Submit answers** – `POST /sessions/{id}/answers` with the question/answer map.
   Returns the synthesized prompt used for generation.
3. **Generate suggestions** – `POST /sessions/{id}/generate`.
   Returns lists of available and taken domains.
4. **Provide feedback** – `POST /sessions/{id}/feedback` with liked domains and/or a dislike reason.
   Returns the refined brief and the next set of questions.

`GET /sessions/{id}/state` can be used for debugging or resuming a UI.

## Next.js Client

The `nextjs/` directory contains a minimal client example. Configure
`nextjs/.env.local` with:

```
DOMAIN_API_URL=http://localhost:8000
DOMAIN_API_KEY=<same key as server>
```

Use the helpers in `nextjs/lib/domainClient.ts` to interact with the API.
