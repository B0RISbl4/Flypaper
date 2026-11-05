export const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
export const hex = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
export const mix = (a, b, t) => a.map((v, i) => v + (b[i] - v) * t);
export const rgb = c => `rgb(${c.map(Math.round)})`;
export const rgba = (c, a = 1) => `rgba(${c.map(Math.round)},${a})`;
