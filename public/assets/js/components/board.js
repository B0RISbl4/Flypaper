import { DEMO_BOARD } from "../data/board-demo.js";
import { flap } from "./flap.js";
import { setTail } from "./tail.js";

const BOARD_API = new URL("../../../api/board", import.meta.url);
const SHOW = 7;
const KEEP_MIN = 40;
const FINAL = new Set(["departed", "landed", "canceled", "diverted"]);

const hhmm = new Intl.DateTimeFormat("ru-RU", { timeZone: "Europe/Moscow", hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
const fmt = (ts) => hhmm.format(ts * 1000);

export function initBoard() {
  const list = document.getElementById("board-list");
  if (!list) return;
  const clock = document.getElementById("board-clock");
  const note = document.querySelector(".board__note");
  const tabs = document.querySelectorAll(".board__tab");
  let mode = "dep";
  let live = null;
  let shown = [];
  let shownClock = "";

  const liveStatus = (r) => {
    const at = r.event ? ` ${fmt(r.event)}` : "";
    switch (r.status) {
      case "estimated": return [`Ожидается${at}`, "soon"];
      case "delayed":   return [`Задержан${at ? " до" + at : ""}`, "bad"];
      case "departed":  return [`Вылетел${at}`, "done"];
      case "landed":    return [`Прибыл${at}`, "done"];
      case "canceled":  return ["Отменён", "bad"];
      case "diverted":  return ["Перенаправлен", "bad"];
      case "scheduled": return ["По расписанию", ""];
      default:          return ["—", ""];
    }
  };
  const liveRows = () => {
    const now = Date.now() / 1000;
    return live[mode === "dep" ? "departures" : "arrivals"]
      .filter((r) => !FINAL.has(r.status) || Math.max(r.time, r.event || 0) >= now - KEEP_MIN * 60)
      .slice(0, SHOW)
      .map((r) => ({ time: fmt(r.time), code: r.airline, flight: r.flight, city: r.city, airport: r.airport, status: liveStatus(r) }));
  };

  const moscowMinutes = () => {
    const [h, m] = hhmm.format(new Date()).split(":").map(Number);
    return h * 60 + m;
  };
  const demoStatus = (diff) => mode === "dep"
    ? diff < 0 ? ["Вылетел", "done"] : diff <= 30 ? ["Посадка", "go"] : diff <= 120 ? ["Регистрация", "soon"] : ["По расписанию", ""]
    : diff < 0 ? ["Прибыл", "done"] : diff <= 20 ? ["Заходит на посадку", "go"] : diff <= 60 ? ["Ожидается", "soon"] : ["По расписанию", ""];
  const demoRows = () => {
    const now = moscowMinutes();
    return DEMO_BOARD[mode].map(([time, code, flight, city]) => {
      const [h, m] = time.split(":").map(Number);
      const diff = ((h * 60 + m - now + 1440 + 720) % 1440) - 720;   // ближайшее вхождение, ±12 часов
      return { time, code, flight, city, airport: "", diff };
    }).filter((r) => r.diff >= -KEEP_MIN).sort((a, b) => a.diff - b.diff).slice(0, SHOW)
      .map((r) => ({ ...r, status: demoStatus(r.diff) }));
  };

  const render = () => {
    const rows = live ? liveRows() : demoRows();
    note.textContent = live
      ? `Flightradar24 · обновлено в ${fmt(live.updated)} · время московское`
      : "Демо-расписание · время московское";

    list.innerHTML = "";
    if (!rows.length) list.innerHTML = '<li class="board__empty">Рейсов нет</li>';
    rows.forEach((r, i) => {
      const [text, kind] = r.status;
      const before = shown[i] || {};
      const li = document.createElement("li");
      li.className = "board__row";
      li.innerHTML = `<span class="board__time"></span><span class="board__flight"><img alt="" width="22" height="22"><span></span></span>
        <span class="board__city"><span></span><small></small></span><span class="board__status"></span>`;
      flap(li.querySelector(".board__time"), r.time, before.time);
      setTail(li.querySelector("img"), r.code || "");
      flap(li.querySelector(".board__flight span"), r.flight, before.flight);
      li.querySelector(".board__city span").textContent = r.city;
      li.querySelector(".board__city small").textContent = r.airport;
      const st = li.querySelector(".board__status");
      flap(st, text, before.status);
      if (kind) st.classList.add(`board__status--${kind}`);
      list.append(li);
    });
    shown = rows.map((r) => ({ time: r.time, flight: r.flight, status: r.status[0] }));
  };

  const load = async () => {
    try {
      const response = await fetch(BOARD_API, { cache: "no-store" });
      if (!response.ok) throw new Error(`board: ${response.status}`);
      const data = await response.json();
      if (!Array.isArray(data.departures) || !Array.isArray(data.arrivals)) throw new Error("board: bad data");
      live = data;
    } catch {
      live = null;
    }
    render();
  };

  const tick = () => {
    const now = moscowMinutes();
    const text = `${String(Math.floor(now / 60)).padStart(2, "0")}:${String(now % 60).padStart(2, "0")}`;
    if (text === shownClock) return;
    flap(clock, text, shownClock);
    shownClock = text;
  };

  tabs.forEach((tab) => tab.addEventListener("click", () => {
    mode = tab.dataset.board;
    tabs.forEach((t) => {
      t.classList.toggle("is-active", t === tab);
      t.setAttribute("aria-selected", String(t === tab));
    });
    render();
  }));

  tick();
  setInterval(tick, 15000);
  load();
  setInterval(load, 60000);
}
