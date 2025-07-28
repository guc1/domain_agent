import { NextRequest, NextResponse } from 'next/server';
import { startSession, answerSession } from '@/lib/domainClient';

export async function POST(req: NextRequest) {
  const body = await req.json();
  try {
    if (body.action === 'start') {
      return NextResponse.json(await startSession(body.brief));
    }
    if (body.action === 'answer') {
      return NextResponse.json(
        await answerSession(body.sessionId, body.payload)
      );
    }
    return NextResponse.json({ error: 'Invalid action' }, { status: 400 });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
