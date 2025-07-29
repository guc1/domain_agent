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
   Returns the `session_id` and a list of question objects:
   `[{"id": "q1", "text": "..."}, ...]`.
2. **Submit answers** – `POST /sessions/{id}/answers` with answers keyed by question ID,
   e.g. `{ "answers": {"q1": "yes"} }`.
   Returns the synthesized prompt used for generation.
3. **Generate suggestions** – `POST /sessions/{id}/generate`.
   Returns lists of available and taken domains along with a history of all names checked in the session.
4. **Provide feedback** – `POST /sessions/{id}/feedback` with optional `liked` and `disliked` maps.
   Each is a mapping of domain → reason. Returns the refined brief and another list of question objects.

`GET /sessions/{id}/state` returns the current loop info and the domain history for that session.

Additional helpers:

- `POST /clarify` with `{ "prompt": "..." }` returns two clarifying
  questions.
- `POST /combine` combines the previous prompt and user feedback
  into a new prompt. The payload is `{ "previous_prompt": "...",
  "answers": {...}, "question_map": {...}, "liked_domains": {...},
  "disliked_domains": {...}, "taken_domains": ["..."] }` and the
  response contains the refined `prompt`.

## Next.js Client

The `nextjs/` directory contains a minimal client example. Configure
`nextjs/.env.local` with:

```
DOMAIN_API_URL=http://localhost:8000
DOMAIN_API_KEY=<same key as server>
```

Use the helpers in `nextjs/lib/domainClient.ts` to interact with the API.
Questions are returned with stable `id` fields; use these IDs when sending answer payloads.
