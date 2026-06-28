/** Interactive pricing toggle */
const PLANS = {
  monthly: [
    { name: 'Starter', price: 49, features: ['5 seats', 'CRM sync', 'Weekly forecasts'] },
    { name: 'Pro', price: 149, featured: true, features: ['25 seats', 'Churn radar', 'Board packs', 'API access'] },
    { name: 'Enterprise', price: null, features: ['Unlimited seats', 'SSO / SCIM', 'Dedicated CSM', 'Custom models'] },
  ],
  annual: [
    { name: 'Starter', price: 39, features: ['5 seats', 'CRM sync', 'Weekly forecasts'] },
    { name: 'Pro', price: 119, featured: true, features: ['25 seats', 'Churn radar', 'Board packs', 'API access'] },
    { name: 'Enterprise', price: null, features: ['Unlimited seats', 'SSO / SCIM', 'Dedicated CSM', 'Custom models'] },
  ],
};

export function initPricing(container, toggle) {
  let period = 'monthly';

  const render = () => {
    const plans = PLANS[period] || PLANS.monthly;
    container.innerHTML = plans
      .map(
        (p) => `
      <article class="price-card ${p.featured ? 'featured' : ''}">
        <h3>${p.name}</h3>
        <div class="amount">${p.price == null ? 'Custom' : `$${p.price}`}${p.price != null ? '<small>/mo</small>' : ''}</div>
        <ul>${p.features.map((f) => `<li>${f}</li>`).join('')}</ul>
        <button class="btn ${p.featured ? 'btn-primary' : 'btn-ghost'}">Get started</button>
      </article>`
      )
      .join('');
  };

  toggle?.querySelectorAll('button').forEach((btn) => {
    btn.addEventListener('click', () => {
      period = btn.dataset.period || 'monthly';
      toggle.querySelectorAll('button').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      render();
    });
  });

  render();
}
