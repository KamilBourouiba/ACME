/** Hero stat counters */
export function animateStats() {
  document.querySelectorAll('.stat-num[data-target]').forEach((el) => {
    const target = parseFloat(el.dataset.target || '0');
    const isDecimal = String(target).includes('.');
    let current = 0;
    const step = target / 40;
    const tick = () => {
      current += step;
      if (current >= target) {
        el.textContent = isDecimal ? target.toFixed(1) : Math.round(target) + (target >= 100 ? '+' : '×');
        return;
      }
      el.textContent = isDecimal ? current.toFixed(1) : Math.round(current);
      requestAnimationFrame(tick);
    };
    tick();
  });
}
