const CLOUD_H = .68;
const EDGE = 50;       // высота нижнего края постера в координатах viewBox — её не трогаем

export function bank(seed, heads, r0) {
  const random = () => (seed = seed * 16807 % 2147483647) / 2147483647;
  const B = 1000, f = n => n.toFixed(1);
  const dome = x => Math.max(0, ...heads.map(([cx, h, hw]) => h * Math.sqrt(Math.max(0, 1 - ((x - cx) / hw) ** 2))));
  const height = x => { const v = dome(x); return v > EDGE ? EDGE + (v - EDGE) * CLOUD_H : v; };
  const x0 = Math.min(...heads.map(([cx, , hw]) => cx - hw)), x1 = Math.max(...heads.map(([cx, , hw]) => cx + hw));
  let out = "";
  const lobe = (x, y, r, dir, depth) => {
    out += `<circle cx="${f(x)}" cy="${f(y)}" r="${f(r)}"/>`;
    if (!depth) return;
    for (let i = 0, n = 3 + (random() < .5); i < n; i++) {
      const a = dir + (random() - .5) * 2.6, rc = r * (.36 + .22 * random()), d = r - rc * .55;
      lobe(x + Math.cos(a) * d, y + Math.sin(a) * d, rc, a, depth - 1);
    }
  };
  for (let x = x0; x <= x1; x += r0 * (.8 + .5 * random())) {
    const h = height(x);
    if (h < 8) continue;
    const slope = (height(x + 4) - height(x - 4)) / 8, r = r0 * (.75 + .6 * random());
    lobe(x, B - h + r * .7, r, Math.atan2(-1, -slope), 2);
  }
  for (let x = x0; x <= x1; x += r0 * .6) {
    const h = height(x);
    if (h >= 8) out += `<circle cx="${f(x)}" cy="${f(B - h + r0)}" r="${f(r0 * .9)}"/>`;
  }
  let d = `M${f(x0)} ${B + 100}`;
  for (let x = x0; x <= x1; x += 8) d += `L${f(x)} ${f(B - Math.max(0, height(x) - r0 * .6))}`;
  return `<path d="${d}L${f(x1)} ${B + 100}Z"/>` + out;
}

export const CLOUD_LAYERS = {
  cf: [11, [[70, 395, 70], [130, 335, 60], [470, 265, 90], [620, 205, 80], [800, 170, 90]], 22],
  cm: [23, [[320, 375, 110], [450, 300, 100], [580, 235, 110], [700, 170, 110], [850, 130, 100], [1000, 100, 110]], 32],
  cc: [5, [[120, 330, 150], [270, 290, 100], [370, 225, 120], [510, 215, 110], [640, 140, 100], [780, 105, 100], [900, 75, 80]], 42],
  cn: [17, [[90, 215, 90], [230, 285, 95], [340, 135, 90], [460, 130, 110], [570, 90, 90], [660, 75, 80]], 38],
};
