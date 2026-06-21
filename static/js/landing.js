document.addEventListener('DOMContentLoaded', function () {
  // Animate counters when visible
  const counters = document.querySelectorAll('.stat-value');
  const runCounter = (el) => {
    const target = parseInt(el.getAttribute('data-target')) || 0;
    let current = 0;
    const duration = 900;
    const stepTime = Math.max(12, Math.floor(duration / Math.max(1, target)));
    const step = Math.max(1, Math.floor(target / (duration / stepTime)));
    const t = setInterval(() => {
      current += step;
      if (current >= target) {
        el.textContent = target;
        clearInterval(t);
      } else {
        el.textContent = current;
      }
    }, stepTime);
  };

  if ('IntersectionObserver' in window) {
    const obs = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          runCounter(entry.target);
          obs.unobserve(entry.target);
        }
      });
    }, { threshold: 0.4 });
    counters.forEach(c => obs.observe(c));
  } else {
    counters.forEach(c => runCounter(c));
  }

  // Simple fade-in for cards
  const observers = document.querySelectorAll('.card');
  if ('IntersectionObserver' in window) {
    const obs2 = new IntersectionObserver(entries => {
      entries.forEach(e => {
        if (e.isIntersecting) {
          e.target.classList.add('fade-in-up');
          obs2.unobserve(e.target);
        }
      });
    }, { threshold: 0.15 });
    observers.forEach(n => obs2.observe(n));
  }
});
