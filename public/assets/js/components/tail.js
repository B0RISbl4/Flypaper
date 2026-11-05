const TAILS_DIR = new URL("../../img/tails/", import.meta.url);
const FALLBACK = new URL("default.svg", TAILS_DIR).href;

export function setTail(img, code) {
  const sources = /^[A-Z0-9]{2}$/.test(code) ? [new URL(`${code}.png`, TAILS_DIR).href] : [];
  sources.push(FALLBACK);
  let i = 0;
  img.classList.add("is-loading");
  img.onload = () => img.classList.remove("is-loading");
  img.onerror = () => {
    if (++i < sources.length) img.src = sources[i];
    else { img.onerror = null; img.classList.remove("is-loading"); }
  };
  img.src = sources[0];
}
