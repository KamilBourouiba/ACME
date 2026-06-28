import { postLead, fetchServices } from './api.js';
import { DEFAULT_SERVICES, renderServices } from './components.js';

const grid = document.querySelector('#services');

async function init() {
  const remote = await fetchServices().catch(() => null);
  renderServices(grid, remote?.items || DEFAULT_SERVICES);
}

document.getElementById('cta')?.addEventListener('click', async () => {
  const email = prompt('Work email for discovery call');
  if (!email) return;
  const company = prompt('Company name') || 'Unknown';
  try {
    await postLead({ email, company, message: 'Discovery call from homepage CTA' });
    alert('Thanks — we will reach out within 1 business day.');
  } catch {
    alert('Thanks — we will reach out within 1 business day.');
  }
});

init();
