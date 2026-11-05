import { setTail } from "../components/tail.js";

const API = new URL("../../../api/guestbook", import.meta.url);

async function load() {
  const response = await fetch(API, { cache: "no-store" });
  if (!response.ok) throw new Error(`guestbook: ${response.status}`);
  return (await response.json()).entries;
}

async function save(entry) {
  let response;
  try {
    response = await fetch(API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(entry),
    });
  } catch {
    throw new Error("Сервер недоступен — запись не отправлена.");
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || "Не удалось сохранить запись.");
}

const el = (tag, cls, text) => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text) node.textContent = text; // textContent — защита от вставки HTML
  return node;
};

function initGuestbook() {
  const form = document.getElementById("gb-form");
  const list = document.getElementById("gb-entries");
  if (!form || !list) return;

  const count = document.getElementById("gb-count");

  const render = async () => {
    let entries;
    try {
      entries = await load();
    } catch {
      list.replaceChildren(el("p", "gb-empty", "Записи хранятся на сервере сайта, а он сейчас недоступен."));
      count.textContent = "";
      return;
    }
    list.innerHTML = "";
    count.textContent = `(${entries.length})`;
    if (!entries.length) list.append(el("p", "gb-empty", "Пока никто ничего не написал — станьте первым."));

    entries.forEach((e) => {
      const card = el("article", "entry");

      const body = el("div", "entry__message");
      body.append(el("p", "entry__name", e.name), el("p", "entry__text", e.text));

      const post = el("div", "entry__post");
      const stamp = el("div", "entry__stamp");
      const avatar = el("img", "entry__tail");
      setTail(avatar, e.airline);
      avatar.alt = e.airline ? `Хвост авиакомпании ${e.airline}` : "Хвост самолёта";
      avatar.width = avatar.height = 72;
      avatar.loading = "lazy";
      stamp.append(avatar);

      const postmark = el("div", "entry__postmark");
      postmark.append(el("span", "entry__airport", e.airport || "✈"), el("span", "entry__date", e.date));

      post.append(stamp, postmark, el("span", "entry__airmail", "Par avion · Авиа"));
      card.append(body, post);
      list.append(card);
    });
  };

  const airport = form.elements.airport;
  const airline = form.elements.airline;
  const preview = document.getElementById("gb-preview");
  airport.addEventListener("input", () => { airport.value = airport.value.replace(/[^a-z]/gi, "").toUpperCase(); });
  airline.addEventListener("input", () => {
    airline.value = airline.value.replace(/[^a-z0-9]/gi, "").toUpperCase();
    setTail(preview, airline.value);
  });

  const error = document.getElementById("gb-error");

  const submit = form.querySelector('[type="submit"]');

  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const name = form.elements.name.value.trim();
    const text = form.elements.text.value.trim();
    const ap = airport.value.trim();
    const al = airline.value.trim();

    if (!name || !text) { error.textContent = "Заполните имя и сообщение."; return; }
    if (ap && ap.length !== 3) { error.textContent = "Код аэропорта — ровно 3 буквы, например LED."; return; }
    if (al && al.length !== 2) { error.textContent = "Код авиакомпании — ровно 2 символа, например S7."; return; }
    error.textContent = "";

    submit.disabled = true;
    try {
      await save({ name, airport: ap, airline: al, text });
    } catch (e) {
      error.textContent = e.message;
      return;
    } finally {
      submit.disabled = false;
    }
    form.reset();
    setTail(preview, "");
    render();
  });

  render();
}

initGuestbook();
