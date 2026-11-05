export function initLightbox() {
  const gallery = document.querySelector(".gallery");
  if (!gallery) return;

  const box = document.getElementById("lightbox");
  if (!box || typeof box.showModal !== "function") return;
  const img = box.querySelector("img");
  const caption = box.querySelector(".lightbox__caption");
  let current = 0;

  const visibleItems = () => [...gallery.querySelectorAll(".gallery__item")];

  const show = (i) => {
    const items = visibleItems();
    current = (i + items.length) % items.length;
    const item = items[current];
    const thumb = item.querySelector("img");
    img.src = thumb.src;
    img.alt = thumb.alt;
    const cap = item.querySelector("figcaption");
    caption.textContent = cap ? cap.textContent.trim() : "";
  };

  gallery.addEventListener("click", (e) => {
    const btn = e.target.closest(".gallery__btn");
    if (!btn) return;
    show(visibleItems().indexOf(btn.closest(".gallery__item")));
    box.showModal();
  });

  box.querySelector("[data-prev]").addEventListener("click", () => show(current - 1));
  box.querySelector("[data-next]").addEventListener("click", () => show(current + 1));
  box.querySelector("[data-close]").addEventListener("click", () => box.close());
  box.addEventListener("click", (e) => { if (e.target === box) box.close(); });
  box.addEventListener("keydown", (e) => {
    if (e.key === "ArrowLeft") show(current - 1);
    if (e.key === "ArrowRight") show(current + 1);
  });
}
