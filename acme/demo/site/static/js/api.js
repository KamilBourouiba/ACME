/** Lumen API client */
export async function postWaitlist({ email, company = '', role = '' }) {
  const res = await fetch('/api/waitlist', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, company, role }),
  });
  if (!res.ok) throw new Error(`Waitlist ${res.status}`);
  return res.json();
}

export async function fetchFeatures() {
  const res = await fetch('/api/features');
  if (!res.ok) return null;
  return res.json();
}

export async function fetchPricing() {
  const res = await fetch('/api/pricing');
  if (!res.ok) return null;
  return res.json();
}

export async function fetchMetrics() {
  const res = await fetch('/api/metrics');
  if (!res.ok) return null;
  return res.json();
}
