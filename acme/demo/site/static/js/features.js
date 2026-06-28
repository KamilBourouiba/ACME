/** Feature grid renderer */
export function renderFeatures(grid, items) {
  grid.innerHTML = items
    .map(
      (f) => `
    <article class="feature-card">
      <div class="feature-icon">${f.icon || '◆'}</div>
      <h3>${f.title}</h3>
      <p>${f.desc}</p>
    </article>`
    )
    .join('');
}

export const DEFAULT_FEATURES = [
  { icon: '⚡', title: 'Signal ingestion', desc: 'Unify CRM, product, and billing events into one revenue graph.' },
  { icon: '🎯', title: 'Forecast AI', desc: 'ML models trained on your pipeline history — not generic benchmarks.' },
  { icon: '🔔', title: 'Churn radar', desc: 'Early warnings when accounts show expansion or contraction patterns.' },
  { icon: '📊', title: 'Board packs', desc: 'One-click exports for QBRs with narrative + chart auto-generation.' },
  { icon: '🔗', title: 'RevOps sync', desc: 'Bi-directional Salesforce & HubSpot with field-level mapping.' },
  { icon: '🛡️', title: 'Enterprise SSO', desc: 'SAML, SCIM, and audit logs for regulated industries.' },
];
