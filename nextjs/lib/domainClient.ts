export const DOMAIN_API_URL = process.env.DOMAIN_API_URL!;
export const DOMAIN_API_KEY = process.env.DOMAIN_API_KEY!;

export interface AnswerPayload {
  answers: Record<string, string>;
}

export interface FeedbackPayload {
  liked?: Record<string, string>;
  dislike_reason?: string;
}

async function callApi(path: string, method: string, body?: any) {
  const res = await fetch(`${DOMAIN_API_URL}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': DOMAIN_API_KEY,
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`API ${path} failed`);
  return res.json();
}

export function startSession(initialBrief: string) {
  return callApi('/sessions', 'POST', { initial_brief: initialBrief });
}

export function submitAnswers(sessionId: string, payload: AnswerPayload) {
  return callApi(`/sessions/${sessionId}/answers`, 'POST', payload);
}

export function generateSuggestions(sessionId: string) {
  return callApi(`/sessions/${sessionId}/generate`, 'POST');
}

export function sendFeedback(sessionId: string, payload: FeedbackPayload) {
  return callApi(`/sessions/${sessionId}/feedback`, 'POST', payload);
}

export function getState(sessionId: string) {
  return callApi(`/sessions/${sessionId}/state`, 'GET');
}
