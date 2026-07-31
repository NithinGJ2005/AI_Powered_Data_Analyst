import { useState } from 'react';

export default function App() {
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState('');
  const [analysis, setAnalysis] = useState<{answer: string, reasoning: string} | null>(null);

  const handleUpload = async () => {
    if (!file) return;
    const formData = new FormData();
    formData.append('file', file);
    await fetch('/api/upload', { method: 'POST', body: formData });
    alert('File uploaded');
  };

  const handleChat = async () => {
    const res = await fetch('/api/chat', { 
      method: 'POST', 
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: message }) 
    });
    const data = await res.json();
    setAnalysis(data);
  };

  return (
    <div className="p-4">
      <h1 className="text-2xl font-bold mb-4">AI Data Analyst</h1>
      
      <div className="mb-4">
        <input type="file" onChange={(e) => setFile(e.target.files?.[0] || null)} />
        <button className="bg-blue-500 text-white p-2 rounded" onClick={handleUpload}>Upload</button>
      </div>

      <div className="mb-4">
        <input className="border p-2 w-full" value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Ask a question..." />
        <button className="bg-green-500 text-white p-2 rounded mt-2" onClick={handleChat}>Analyze</button>
      </div>

      {analysis && (
        <div className="border p-4">
          <p><strong>Answer:</strong> {analysis.answer}</p>
          <p><strong>Reasoning:</strong> {analysis.reasoning}</p>
        </div>
      )}
    </div>
  );
}
