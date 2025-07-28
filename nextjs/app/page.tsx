import { useState } from 'react';

interface Question {
  id: string;
  text: string;
}

interface Message {
  sender: 'system' | 'user';
  text: string;
}

export default function Home() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [current, setCurrent] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [qIndex, setQIndex] = useState(0);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [taken, setTaken] = useState<string[]>([]);

  async function callApi(data: any) {
    const res = await fetch('/api/domain', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.error || 'API error');
    return json;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const input = current.trim();
    if (!input) return;
    setMessages(m => [...m, { sender: 'user', text: input }]);
    setCurrent('');

    try {
      if (!sessionId) {
        const data = await callApi({ action: 'start', brief: input });
        setSessionId(data.session_id);
        setQuestions(data.questions);
        setMessages(m => [
          ...m,
          ...data.questions.map((q: Question) => ({
            sender: 'system',
            text: q.text,
          })),
        ]);
      } else if (qIndex < questions.length) {
        const q = questions[qIndex];
        setAnswers(a => ({ ...a, [q.id]: input }));
        const nextIndex = qIndex + 1;
        if (nextIndex < questions.length) {
          setQIndex(nextIndex);
        } else {
          const promptRes = await callApi({
            action: 'answers',
            sessionId,
            payload: { answers: { ...answers, [q.id]: input } },
          });
          await handleGenerate(promptRes);
        }
      }
    } catch (err: any) {
      console.error(err);
    }
  }

  async function handleGenerate(promptRes?: any) {
    try {
      const gen = await callApi({ action: 'generate', sessionId });
      setSuggestions(gen.available);
      setTaken(gen.taken);
      setMessages(m => [
        ...m,
        { sender: 'system', text: 'Available: ' + gen.available.join(', ') },
        { sender: 'system', text: 'Taken: ' + gen.taken.join(', ') },
      ]);
    } catch (err: any) {
      console.error(err);
    }
  }

  return (
    <main style={{ maxWidth: 600, margin: '0 auto', padding: 20 }}>
      <h1>Domain Chat Test</h1>
      <div style={{ border: '1px solid #ccc', padding: 10, minHeight: 200 }}>
        {messages.map((m, i) => (
          <div key={i} style={{ textAlign: m.sender === 'user' ? 'right' : 'left' }}>
            <b>{m.sender === 'user' ? 'You' : 'System'}: </b>
            {m.text}
          </div>
        ))}
      </div>
      {suggestions.length > 0 && (
        <div style={{ marginTop: 10 }}>
          <h3>Available</h3>
          <ul>
            {suggestions.map(s => (
              <li key={s}>{s}</li>
            ))}
          </ul>
          <h3>Taken</h3>
          <ul>
            {taken.map(s => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        </div>
      )}
      <form onSubmit={handleSubmit} style={{ marginTop: 10 }}>
        <input
          value={current}
          onChange={e => setCurrent(e.target.value)}
          style={{ width: '100%', padding: 8 }}
          placeholder={sessionId ? 'Answer the question...' : 'Enter initial brief'}
        />
      </form>
    </main>
  );
}

