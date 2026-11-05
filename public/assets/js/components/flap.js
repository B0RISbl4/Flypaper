const DRUM = " ABCDEFGHIJKLMNOPQRSTUVWXYZАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ0123456789:.-()—";
const STEP_MS = 55;
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

const rolling = new Map();
let timer = null;

function step() {
  for (const [tile, roll] of rolling) {
    if (!tile.isConnected || --roll.steps <= 0) {
      tile.textContent = roll.final;
      tile.classList.remove("is-rolling");
      rolling.delete(tile);
    } else {
      roll.index = (roll.index + 1) % DRUM.length;
      tile.textContent = DRUM[roll.index];
    }
  }
  if (!rolling.size) {
    clearInterval(timer);
    timer = null;
  }
}

function roll(tile, final) {
  const target = DRUM.indexOf(final);
  if (reduceMotion.matches || target < 0) {
    tile.textContent = final;
    return;
  }
  const steps = 3 + Math.floor(Math.random() * 7);
  const index = (target - steps + DRUM.length) % DRUM.length;
  tile.textContent = DRUM[index];
  tile.classList.add("is-rolling");
  rolling.set(tile, { final, index, steps });
  timer ??= setInterval(step, STEP_MS);
}

export function flap(el, text, previous = "") {
  const chars = [...String(text).toUpperCase()];
  const before = [...String(previous).toUpperCase()];
  el.textContent = "";
  const label = document.createElement("span");              // скринридер читает текст целиком,
  label.className = "visually-hidden";                       // а не по плиткам
  label.textContent = text;
  el.append(label);

  let word = null;
  chars.forEach((char, i) => {
    if (char === " ") {
      word = null;
      el.append(" ");
      return;
    }
    if (!word) {
      word = document.createElement("span");
      word.className = "flap-word";
      word.setAttribute("aria-hidden", "true");
      el.append(word);
    }
    const tile = document.createElement("span");
    tile.className = "flap";
    word.append(tile);
    if (before[i] === char) tile.textContent = char;
    else roll(tile, char);
  });
}
