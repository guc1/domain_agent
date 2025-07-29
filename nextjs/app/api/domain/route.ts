import { NextRequest, NextResponse } from 'next/server';
import {
  startSession,
  submitAnswers,
  generateSuggestions,
  sendFeedback,
  getState,
  setSettings,
  getSettings,
} from '@/lib/domainClient';

export async function POST(req: NextRequest) {
  const body = await req.json();
  try {
    if (body.action === 'start') {
      return NextResponse.json(await startSession(body.brief));
    }
    if (body.action === 'answers') {
      return NextResponse.json(
        await submitAnswers(body.sessionId, body.payload)
      );
    }
    if (body.action === 'generate') {
      return NextResponse.json(await generateSuggestions(body.sessionId));
    }
    if (body.action === 'feedback') {
      return NextResponse.json(
        await sendFeedback(body.sessionId, body.payload)
      );
    }
    if (body.action === 'state') {
      return NextResponse.json(await getState(body.sessionId));
    }
    if (body.action === 'settings') {
      return NextResponse.json(
        await setSettings(body.sessionId, body.payload)
      );
    }
    if (body.action === 'get_settings') {
      return NextResponse.json(await getSettings(body.sessionId));
    }
    return NextResponse.json({ error: 'Invalid action' }, { status: 400 });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
