import { clamp, mix, rgb, rgba } from "./color.js";
import { skyAt, solarPosition } from "./sky.js";
import { bank, CLOUD_LAYERS } from "./clouds.js";
import { DEMO_FLIGHTS } from "./demo.js";

const LAT = 59.9343, LON = 30.3351;
const VIEW = 285, FOV = 110, HOR = .78;

const API = new URL("../../../api/aircraft", import.meta.url);
const SHAPE_DIR = new URL("../../img/shapes/", import.meta.url);
const SHAPES = { default: "B738.svg" };
const LIVERY_DIR = new URL("../../img/liveries/", import.meta.url);
const EMPTY_TAIL = new URL("empty.png", LIVERY_DIR).href;
const F = { airline: "airline_name", originCity: "origin_city", destCity: "dest_city", heading: "heading" };

const $ = id => document.getElementById(id);
const poster = $("poster");
let warnedAboutSunCalc = false;

$("stars").innerHTML = Array.from({ length: 90 }, () =>
  `<i style="left:${Math.random() * 100}%;top:${Math.random() * 100}%;opacity:${.3 + Math.random() * .7}"></i>`
).join("");

function toXY(az, alt) {
  const dx = ((az - VIEW + 540) % 360) - 180;
  return [50 + dx / FOV * 100, poster.clientHeight * HOR * (1 - alt / 60)];
}

for (const [id, [seed, heads, r0]] of Object.entries(CLOUD_LAYERS)) $(id).innerHTML = bank(seed, heads, r0);

let themeKey = "";
function applyTheme(alt, horizon) {
  const day = clamp((alt + 4) / 16);
  const glow = clamp(1 - Math.abs(alt - 2) / 14);
  const lit = mix(mix([40, 52, 90], [243, 230, 203], day), [255, 176, 128], glow * .35);
  const shade = mix(mix([18, 26, 56], [96, 138, 198], day), [120, 80, 120], glow * .25);
  const paints = { cf: mix(shade, horizon, .8), cm: mix(shade, horizon, .5), cc: lit, cn: shade };
  const plane = mix([74, 88, 126], [244, 234, 212], day);
  const bright = (.28 + .72 * day).toFixed(2);
  const key = [plane, ...Object.values(paints)].map(c => c.map(Math.round)).join("|") + bright;
  if (key === themeKey) return;
  themeKey = key;
  for (const [id, c] of Object.entries(paints)) $(id).style.setProperty("--c", rgb(c));
  poster.style.setProperty("--plane", rgb(plane));
  $("tail").style.filter = `brightness(${bright})`;
}

function render(date) {
  if (!window.SunCalc && !warnedAboutSunCalc) {
    console.warn("SunCalc did not load; moon rendering is unavailable, using calculated solar position.");
    warnedAboutSunCalc = true;
  }
  const position = window.SunCalc ? SunCalc.getPosition(date, LAT, LON) : solarPosition(date, LAT, LON);
  const alt = window.SunCalc ? position.altitude * 180 / Math.PI : position.altitude;
  const az = window.SunCalc ? (position.azimuth * 180 / Math.PI + 180) % 360 : position.azimuth;
  const [top, horizon] = skyAt(alt);
  const [sunX, sunY] = toXY(az, alt);
  const glow = clamp(1 - Math.abs(alt - 2) / 14);
  $("sky").style.background =
    `radial-gradient(ellipse 70% 55% at ${clamp(sunX, -20, 120)}% ${sunY}px,rgba(255,140,60,${glow * .7}),transparent 70%),` +
    `linear-gradient(${rgba(top)} 0%,${rgba(horizon)} ${HOR * 100}%,${rgba(horizon)} 100%)`;
  const sunColor = mix([255, 110, 40], [255, 246, 220], clamp(alt / 14));
  $("sun").style.cssText = `left:${sunX}%;top:${sunY}px;background:${rgba(sunColor)};box-shadow:0 0 ${50 + glow * 60}px ${12 + glow * 20}px ${rgba(sunColor, .55)};display:${alt > -1.5 && sunX > -5 && sunX < 105 ? "block" : "none"}`;
  if (window.SunCalc) {
    const moonPosition = SunCalc.getMoonPosition(date, LAT, LON);
    const moonAlt = moonPosition.altitude * 180 / Math.PI;
    const moonAz = (moonPosition.azimuth * 180 / Math.PI + 180) % 360;
    const moonIllumination = SunCalc.getMoonIllumination(date).fraction;
    const [moonX, moonY] = toXY(moonAz, moonAlt);
    $("moon").style.cssText = `left:${moonX}%;top:${moonY}px;opacity:${(.25 + .75 * moonIllumination) * clamp((8 - alt) / 12)};display:${moonAlt > -1.5 && moonX > -5 && moonX < 105 ? "block" : "none"}`;
  } else {
    $("moon").style.display = "none";
  }
  $("stars").style.opacity = clamp((-alt - 6) / 8);
  applyTheme(alt, horizon);
}

const layers = [[$("cf"), 10], [$("far"), 12], [$("cm"), 15], [$("cc"), 21], [$("cn"), 28], [$("tail"), 44]];
let targetX = 0, targetY = 0, currentX = 0, currentY = 0;
addEventListener("pointermove", e => {
  targetX = e.clientX / innerWidth * 2 - 1;
  targetY = e.clientY / innerHeight * 2 - 1;
});
addEventListener("deviceorientation", e => {
  if (e.gamma != null) {
    targetX = clamp(e.gamma / 30, -1, 1);
    targetY = clamp((e.beta - 45) / 30, -1, 1);
  }
});
let planeFlight = null;
let planeFlightStarted = null;
const PLANE_FLIGHT_MS = 90000;
(function animate() {
  currentX += (targetX - currentX) * .07;
  currentY += (targetY - currentY) * .07;
  layers.forEach(([el, d]) => {
    el.style.transform = `translate3d(${-currentX * d}px,${-currentY * d * .4}px,0)`;
  });
  if (planeFlight) {
    const progress = ((performance.now() - planeFlightStarted) % PLANE_FLIGHT_MS) / PLANE_FLIGHT_MS;
    const x = planeFlight.startX + planeFlight.horizontalTravel * progress;
    const y = planeFlight.startY - planeFlight.horizontalTravel * Math.tan(planeFlight.trajectoryAngle * Math.PI / 180) * progress;
    const { bounds, group, scale, angle } = planeFlight;
    group.setAttribute("transform",
      `translate(${x} ${y}) rotate(${angle}) scale(${scale}) translate(${-(bounds.x + bounds.width / 2)} ${-(bounds.y + bounds.height / 2)})`);
  }
  requestAnimationFrame(animate);
})();

const NS = "http://www.w3.org/2000/svg";
const shapeCache = {};
const shapeFile = a => {
  const type = typeof a.type === "string" ? a.type.toUpperCase() : "";
  return /^[A-Z0-9]{1,4}$/.test(type) ? `${type}.svg` : SHAPES.default;
};
function shapeDoc(file) {
  return shapeCache[file] ||= fetch(new URL(file, SHAPE_DIR)).then(r => {
    if (!r.ok) throw new Error(file + ": " + r.status);
    return r.text();
  }).then(t => new DOMParser().parseFromString(t, "image/svg+xml").documentElement);
}

let drawId = 0, lastAircraft = null;
async function drawPlane(a) {
  const id = ++drawId, svg = $("planeSvg");
  const W = poster.clientWidth, H = poster.clientHeight;
  planeFlight = null;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.innerHTML = "";
  if (!a) return;
  if (planeFlightStarted === null) planeFlightStarted = performance.now();

  const span = W * .015;
  const trajectoryAngle = 55;
  const ang = 90 - trajectoryAngle;                             // SVG изначально направлен вверх

  const g = document.createElementNS(NS, "g");
  g.setAttribute("class", "plane");
  svg.appendChild(g);
  let b = { x: -span / 2, y: -span / 2, width: span, height: span };
  try {
    const file = shapeFile(a);
    let doc;
    try {
      doc = await shapeDoc(file);
    } catch (error) {
      if (file === SHAPES.default) throw error;
      doc = await shapeDoc(SHAPES.default);
    }
    if (id !== drawId) return;
    [...doc.children].filter(n => /^(g|path)$/.test(n.localName))
      .forEach(n => g.appendChild(document.importNode(n, true)));
    g.querySelectorAll("path").forEach(p =>
      p.setAttribute("style", "fill:currentColor;stroke:currentColor;stroke-width:.35;stroke-linejoin:round"));
    b = g.getBBox();
  } catch (e) { console.warn("silhouette:", e.message); }
  const startX = W * .28;
  const startY = H * 0.95;
  const horizontalTravel = W + span - startX;
  planeFlight = {
    group: g,
    bounds: b,
    scale: span / b.width,
    angle: ang,
    trajectoryAngle,
    startX,
    startY,
    horizontalTravel,
  };
}

const tail = $("tail");
let current;
let currentTailCode = null;
tail.onload = () => { tail.hidden = false; };
tail.onerror = () => {
  if (tail.getAttribute("src") === EMPTY_TAIL) {
    tail.hidden = true;
    return;
  }
  tail.src = EMPTY_TAIL;
};

const COMPASS = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"];
const fmt = n => Math.round(n).toLocaleString("ru-RU");
const dash = v => (v === undefined || v === null || v === "") ? "—" : v;

function show(a) {
  lastAircraft = a;
  poster.classList.toggle("empty", !a);
  drawPlane(a);
  const code = a && typeof a.airline_iata === "string" && /^[A-Z0-9]{2}$/i.test(a.airline_iata)
    ? a.airline_iata.toUpperCase() : null;
  if (code !== currentTailCode) {
    currentTailCode = code;
    tail.hidden = true;
    if (code) tail.src = new URL(`${code}.png`, LIVERY_DIR).href;
  }
  if (!code) tail.hidden = true;
  if (!a) return;

  $("airline").textContent = a.callsign || a[F.airline] || a.airline || a.airline_iata || "";
  $("from").textContent = a.origin || "—";
  $("to").textContent = a.dest || "—";
  $("fromCity").textContent = a[F.originCity] || "";
  $("toCity").textContent = a[F.destCity] || "";

  $("vModel").textContent = dash(a.model_name || a.type);
  $("registrationText").textContent = [a.registration, a.registration_country].filter(Boolean).join(" ") || "—";
  const countryCode = (a.registration_country_iso2 || "").toUpperCase();
  const countryFlag = $("countryFlag");
  if (/^[A-Z]{2}$/.test(countryCode)) {
    countryFlag.src = `https://flagcdn.com/w40/${countryCode.toLowerCase()}.png`;
    countryFlag.alt = `${a.registration_country || countryCode} flag`;
  } else {
    countryFlag.removeAttribute("src");
    countryFlag.alt = "";
  }
  $("vAlt").textContent = Number.isFinite(a.alt_m) ? `${fmt(a.alt_m / 0.3048)} ft` : "—";
  $("vSpd").textContent = Number.isFinite(a.speed_kt) ? `${fmt(a.speed_kt)} kt` : "—";
  const h = a[F.heading];
  $("vHdg").textContent = Number.isFinite(h) ? `${Math.round(h)}° (${COMPASS[Math.round(h / 22.5) % 16]})` : "—";
  $("vDst").textContent = Number.isFinite(a.dist_m) ? `${(a.dist_m / 1000).toFixed(a.dist_m < 10000 ? 1 : 0)} km` : "—";
}

let demo = false;

async function fetchAircraft() {
  if (!demo) {
    try {
      const response = await fetch(API, { cache: "no-store" });
      if (!response.ok) throw new Error(`api: ${response.status}`);
      return (await response.json()).aircraft;
    } catch (e) {
      if (current !== undefined) throw e;          // сервер был — это временный сбой
      demo = true;
      poster.classList.add("demo");
    }
  }
  return DEMO_FLIGHTS[Math.floor(Date.now() / 60000) % DEMO_FLIGHTS.length];
}

async function tick() {
  try {
    const aircraft = await fetchAircraft();
    const key = aircraft
      ? `${aircraft.callsign}:${aircraft.registration}:${aircraft.airline_iata || ""}`
      : null;
    if (key !== current) {
      poster.classList.add("swap");
      setTimeout(() => {
        if (aircraft) planeFlightStarted = performance.now();
        show(aircraft);
        poster.classList.remove("swap");
      }, current === undefined ? 0 : 1500);
      current = key;
    } else if (aircraft) {
      show(aircraft);
    }
  } catch (e) {}
}

addEventListener("resize", () => { render(new Date()); drawPlane(lastAircraft); });
render(new Date());
setInterval(() => render(new Date()), 1000);
tick(); setInterval(tick, 10000);
