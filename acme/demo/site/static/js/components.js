/** UI components */
export const DEFAULT_SERVICES = [
  { title: 'Strategy', desc: 'Market entry & portfolio bets' },
  { title: 'Ops', desc: 'Process design & automation' },
  { title: 'Data', desc: 'Analytics roadmaps & governance' },
];

export function renderServices(grid, items) {
  grid.innerHTML = items
    .map(
      (s) => `<article class="card"><h3>${s.title}</h3><p>${s.desc}</p></article>`
    )
    .join('');
}
