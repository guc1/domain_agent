# Deployment Guide

This project provides a small FastAPI service that generates domain ideas and checks their availability.

## Build the Docker image

```bash
docker build -t domain-checker .
```

## Run the container

Set the required API keys in an `.env` file or as environment variables:

- `OPENAI_API_KEY`
- `GOOGLE_API_KEY`
- `DOMAIN_AGENT_API_KEY` – key required for requests

Then start the service:

```bash
docker run -p 8000:8000 --env-file .env domain-checker
```

The service listens on `http://localhost:8000` and exposes a single endpoint.

## Endpoint

`POST /generate-domains`

Headers:
- `X-API-Key: <DOMAIN_AGENT_API_KEY>`

Body:
```json
{
  "brief": "short project description",
  "answers": { "q1": "...", "q2": "..." }
}
```

The response contains two maps – `available` and `taken` – listing domain names.

