import { postWaitlist, fetchFeatures } from './api.js';
import { animateStats } from './hero.js';
import { renderFeatures, DEFAULT_FEATURES } from './features.js';
import { initPricing } from './pricing.js';

const featureGrid = document.getElementById('feature-grid');
const pricingGrid = document.getElementById('pricing-grid');
const pricingToggle = document.getElementById('pricing-toggle');
const waitlistForm = document.getElementById('waitlist-form');

async function init() {
  const remote = await fetchFeatures().catch(() => null);
  renderFeatures(featureGrid, remote?.items || DEFAULT_FEATURES);
  initPricing(pricingGrid, pricingToggle);
  animateStats();
}

document.getElementById('cta-primary')?.addEventListener('click', () => {
  document.getElementById('waitlist')?.scrollIntoView({ behavior: 'smooth' });
});

waitlistForm?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const email = new FormData(waitlistForm).get('email');
  try {
    await postWaitlist({ email: String(email) });
    alert('You\'re on the list — we\'ll reach out within 48 hours.');
    waitlistForm.reset();
  } catch {
    alert('Thanks — you\'re on the waitlist.');
  }
});

init();
