/** Nexus Advisory API client */
export async function postLead({ email, company, message = '' }) {
  const res = await fetch('/api/lead', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, company, message }),
  });
  if (!res.ok) throw new Error(`Lead API ${res.status}`);
  return res.json();
}

export async function fetchServices() {
  const res = await fetch('/api/services');
  if (!res.ok) return null;
  return res.json();
}
