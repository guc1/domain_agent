export const DOMAIN_API_URL = process.env.DOMAIN_API_URL!;
export const DOMAIN_API_KEY = process.env.DOMAIN_API_KEY!;

export interface AnswerPayload {
  answers: Record<string, string>;
  liked_domains?: Record<string, string>;
  dislike_reason?: string;
}

export async function startSession(brief: string) {
  const res = await fetch(`${DOMAIN_API_URL}/session/start`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': DOMAIN_API_KEY,
    },
    body: JSON.stringify({ brief }),
  });
  if (!res.ok) throw new Error('startSession failed');
  return res.json();
}

export async function answerSession(sessionId: string, payload: AnswerPayload) {
  const res = await fetch(`${DOMAIN_API_URL}/session/${sessionId}/answer`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': DOMAIN_API_KEY,
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('answerSession failed');
  return res.json();
}
