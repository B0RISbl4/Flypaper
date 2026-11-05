import { hex, mix } from "./color.js";

const COLORS = [
  [-18, "#04060d", "#0a1024"], [-8, "#0d1733", "#2a2f5a"],
  [-3, "#25356b", "#c76a6a"], [2, "#2f4f92", "#e0a070"],
  [10, "#1d4a8c", "#b9a98f"], [30, "#15407c", "#2a62a6"]
].map(([alt, top, horizon]) => [alt, hex(top), hex(horizon)]);

export function skyAt(alt) {
  if (alt <= COLORS[0][0]) return [COLORS[0][1], COLORS[0][2]];
  for (let i = 1; i < COLORS.length; i++) {
    if (alt <= COLORS[i][0]) {
      const t = (alt - COLORS[i - 1][0]) / (COLORS[i][0] - COLORS[i - 1][0]);
      return [mix(COLORS[i - 1][1], COLORS[i][1], t), mix(COLORS[i - 1][2], COLORS[i][2], t)];
    }
  }
  const last = COLORS[COLORS.length - 1];
  return [last[1], last[2]];
}

export function solarPosition(date, lat, lon) {
  const jd = date.getTime() / 86400000 + 2440587.5;
  const century = (jd - 2451545) / 36525;
  const meanLongitude = ((280.46646 + century * (36000.76983 + century * .0003032)) % 360 + 360) % 360;
  const meanAnomaly = (357.52911 + century * (35999.05029 - .0001537 * century)) * Math.PI / 180;
  const center = Math.sin(meanAnomaly) * (1.914602 - century * (.004817 + .000014 * century)) +
    Math.sin(2 * meanAnomaly) * (.019993 - .000101 * century) +
    Math.sin(3 * meanAnomaly) * .000289;
  const omega = (125.04 - 1934.136 * century) * Math.PI / 180;
  const longitude = (meanLongitude + center - .00569 - .00478 * Math.sin(omega)) * Math.PI / 180;
  const obliquity = (23 + (26 + (21.448 - century * (46.815 + century * (.00059 - century * .001813))) / 60) / 60 +
    .00256 * Math.cos(omega)) * Math.PI / 180;
  const declination = Math.asin(Math.sin(obliquity) * Math.sin(longitude));
  const rightAscension = Math.atan2(Math.cos(obliquity) * Math.sin(longitude), Math.cos(longitude));
  const gmst = (280.46061837 + 360.98564736629 * (jd - 2451545) +
    .000387933 * century * century - century * century * century / 38710000) * Math.PI / 180;
  const hourAngle = ((gmst + lon * Math.PI / 180 - rightAscension + Math.PI) % (2 * Math.PI) + 2 * Math.PI) %
    (2 * Math.PI) - Math.PI;
  const latitude = lat * Math.PI / 180;
  const altitude = Math.asin(Math.sin(latitude) * Math.sin(declination) +
    Math.cos(latitude) * Math.cos(declination) * Math.cos(hourAngle));
  const azimuth = (Math.atan2(Math.sin(hourAngle),
    Math.cos(hourAngle) * Math.sin(latitude) - Math.tan(declination) * Math.cos(latitude)) * 180 / Math.PI + 180) % 360;
  return { altitude: altitude * 180 / Math.PI, azimuth };
}
