/** ACME project site — mobile nav */
(function () {
  const btn = document.getElementById("nav-menu-btn");
  const links = document.querySelector(".nav-links");
  if (!btn || !links) return;

  const setOpen = (open) => {
    links.classList.toggle("open", open);
    btn.setAttribute("aria-expanded", open ? "true" : "false");
  };

  btn.addEventListener("click", () => setOpen(!links.classList.contains("open")));

  links.querySelectorAll("a").forEach((a) => {
    a.addEventListener("click", () => setOpen(false));
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") setOpen(false);
  });
})();
