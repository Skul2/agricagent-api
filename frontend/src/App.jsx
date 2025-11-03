import React, {useEffect, useState} from 'react';

export default function App(){
  const [messages, setMessages] = useState([]);
  const [secret, setSecret] = useState('');
  const [loading, setLoading] = useState(false);

  async function fetchMessages(){
    if(!secret) return;
    setLoading(true);
    try{
      const res = await fetch(`/admin/messages?secret=${encodeURIComponent(secret)}`);
      if(!res.ok) throw new Error('Forbidden or bad secret');
      const data = await res.json();
      setMessages(data);
    }catch(e){
      alert('Failed to fetch messages: ' + e.message);
    }finally{ setLoading(false); }
  }

  async function triggerAlert(){
    if(!secret) { alert('Enter secret'); return; }
    const res = await fetch(`/admin/send_alert?secret=${encodeURIComponent(secret)}`, {method:'POST'});
    if(res.ok) alert('Alert triggered'); else alert('Failed to trigger');
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-4xl mx-auto bg-white p-6 rounded shadow">
        <h1 className="text-2xl font-bold mb-4">AgriAgent Admin</h1>
        <div className="mb-4">
          <input className="border p-2 mr-2" placeholder="ADMIN_SECRET" value={secret} onChange={e=>setSecret(e.target.value)} />
          <button className="px-3 py-2 bg-blue-600 text-white rounded" onClick={fetchMessages} disabled={loading}>Fetch Messages</button>
          <button className="ml-2 px-3 py-2 bg-green-600 text-white rounded" onClick={triggerAlert}>Send Weather Alert</button>
        </div>
        <div>
          {messages.length===0 ? <p className="text-sm text-gray-500">No messages loaded.</p> :
            <ul>
              {messages.map(m=>(
                <li key={m.id} className="mb-2 border-b pb-2">
                  <div className="text-sm text-gray-600">User ID: {m.user_id} — Role: {m.role}</div>
                  <div className="mt-1">{m.text}</div>
                </li>
              ))}
            </ul>
          }
        </div>
      </div>
    </div>
  );
}
