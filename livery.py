import argparse
import sys
from pathlib import Path

import cv2
import numpy as np


def silhouette(img, tol=25):
    """Маска объекта 0..1. Берёт альфу, если она есть, иначе заливает фон от углов."""
    if img.shape[2] == 4 and img[..., 3].min() < 255:
        return img[..., 3].astype(np.float32) / 255
    g = cv2.cvtColor(img[..., :3], cv2.COLOR_BGR2GRAY)
    h, w = g.shape
    bg = np.zeros((h + 2, w + 2), np.uint8)
    flags = 4 | cv2.FLOODFILL_MASK_ONLY | cv2.FLOODFILL_FIXED_RANGE | (255 << 8)
    for x, y in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
        cv2.floodFill(g, bg, (x, y), 0, tol, tol, flags)
    return 1 - bg[1:-1, 1:-1].astype(np.float32) / 255


def order_quad(p):
    """-> TL, TR, BR, BL (хвост стоит килем вверх)."""
    p = p[np.argsort(p[:, 1])]
    top = p[:2][np.argsort(p[:2, 0])]
    bot = p[2:][np.argsort(p[2:, 0])]
    return np.array([top[0], top[1], bot[1], bot[0]], np.float32)


def refine_quad(pts, quad, tol):
    """Уточняет углы: фитит прямую по каждой стороне и пересекает соседние.
    Нужно, т.к. у лайвери обычно скруглён верхний угол."""
    lines = []
    for i in range(4):
        a, b = quad[i], quad[(i + 1) % 4]
        ab, ap = b - a, pts - a
        t = (ap @ ab) / (ab @ ab)
        d = np.abs(ab[0] * ap[:, 1] - ab[1] * ap[:, 0]) / np.linalg.norm(ab)
        sel = pts[(t > .1) & (t < .7) & (d < tol)]
        vx, vy, x0, y0 = cv2.fitLine(sel, cv2.DIST_L2, 0, .01, .01).ravel()
        lines.append((np.array([x0, y0]), np.array([vx, vy])))
    out = []
    for i in range(4):
        (p1, d1), (p2, d2) = lines[i - 1], lines[i]
        s = np.linalg.solve(np.array([d1, -d2]).T, p2 - p1)
        out.append(p1 + s[0] * d1)
    return np.array(out, np.float32)


def livery_quad(alpha):
    m = (alpha > .5).astype(np.uint8)
    cnt = max(cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)[0],
              key=cv2.contourArea)
    hull = cv2.convexHull(cnt)
    eps = .005 * cv2.arcLength(hull, True)
    approx = hull
    while len(approx) > 4:
        eps *= 1.25
        approx = cv2.approxPolyDP(hull, eps, True)
    quad = order_quad(approx.reshape(-1, 2).astype(np.float32))
    return refine_quad(cnt.reshape(-1, 2).astype(np.float32), quad, .01 * max(m.shape))


def bg_color(rgb, inside):
    """Доминирующий цвет ливреи (мода по квантованным цветам)."""
    px = rgb[inside].astype(np.uint8)
    key = ((px[:, 0] >> 3).astype(np.int32) << 10) | ((px[:, 1] >> 3).astype(np.int32) << 5) | (px[:, 2] >> 3)
    k = np.bincount(key).argmax()
    return px[key == k].mean(0)


# Бумажный тон постера: «белое» на киле становится кремовым, как на концепте
PAPER = np.float32([203, 232, 245]) / 255   # BGR


def apply_livery(plane, livery, fin_poly, lead=None, plane_faces="left", livery_faces="right",
                 fin_quad=None):
    """
    Если задан fin_quad (углы киля шаблона TL, TR, BR, BL — продлённые до пересечения сторон),
    ливрея сажается по четырём углам (перспектива), как наклейка на киль в ракурсе снизу.
    Иначе — старый режим по lead (см. ниже).

    Жёсткая посадка ливреи: поворот + равномерный масштаб + сдвиг (никакого перекоса/перспективы).
    Передняя кромка ливреи совмещается с передней кромкой киля, остальное — «окно» киля.

    fin_poly : полигон, который можно красить (с запасом снаружи киля, нижняя сторона
               чуть выше линии стыка с фюзеляжем). Реальные края берутся из силуэта.
    lead     : ((x, y) верх, (x, y) низ) передней кромки киля — прямая, продлённая до верха и до линии корня.
    Если стороны не совпадают, самолёт разворачивается носом в сторону ливреи (текст не зеркалится).
    """
    fin_poly = np.float32(fin_poly)
    lead = None if lead is None else np.float32(lead)
    fin_quad = None if fin_quad is None else np.float32(fin_quad)
    if plane_faces != livery_faces:
        W0 = plane.shape[1]
        plane = np.ascontiguousarray(plane[:, ::-1])
        fin_poly[:, 0] = W0 - 1 - fin_poly[:, 0]
        if lead is not None:
            lead[:, 0] = W0 - 1 - lead[:, 0]
        if fin_quad is not None:
            fin_quad[:, 0] = W0 - 1 - fin_quad[:, 0]
            fin_quad = fin_quad[[1, 0, 3, 2]]       # после зеркала TL<->TR, BL<->BR
    H, W = plane.shape[:2]

    # 1. ливрея: убираем её контур, фон достраиваем доминирующим цветом
    a = silhouette(livery)
    quad = livery_quad(a)
    p1, p2 = (quad[1], quad[2]) if livery_faces == "right" else (quad[0], quad[3])
    rgb = livery[..., :3].astype(np.float32)
    inner = cv2.erode((a > .5).astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    col = bg_color(rgb, inner > 0)
    al = cv2.GaussianBlur(inner.astype(np.float32), (0, 0), 1.0)[..., None]
    field = rgb * al + col * (1 - al)

    # 2. посадка на киль
    if fin_quad is not None:                    # перспектива по 4 углам
        s = np.linalg.norm(fin_quad[1] - fin_quad[2]) / np.linalg.norm(quad[1] - quad[2])
        if s < 1:
            field = cv2.resize(field, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
            quad = quad * s
        M = cv2.getPerspectiveTransform(quad, fin_quad)
        warped = cv2.warpPerspective(field, M, (W, H), flags=cv2.INTER_CUBIC,
                                     borderMode=cv2.BORDER_CONSTANT, borderValue=tuple(map(float, col)))
    else:                                       # подобие по двум точкам передней кромки
        s = np.linalg.norm(lead[1] - lead[0]) / np.linalg.norm(p2 - p1)
        if s < 1:                               # сначала уменьшаем нормально (INTER_AREA)
            field = cv2.resize(field, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
            p1, p2 = p1 * s, p2 * s
        c = lambda p: complex(*p)
        r = (c(lead[1]) - c(lead[0])) / (c(p2) - c(p1))
        t = c(lead[0]) - r * c(p1)
        M = np.float32([[r.real, -r.imag, t.real], [r.imag, r.real, t.imag]])
        warped = cv2.warpAffine(field, M, (W, H), flags=cv2.INTER_CUBIC,
                                borderMode=cv2.BORDER_CONSTANT, borderValue=tuple(map(float, col)))

    # 3. маска: силуэт самолёта ∩ полигон киля
    poly = np.zeros((H, W), np.uint8)
    cv2.fillPoly(poly, [np.int32(np.round(fin_poly))], 255, lineType=cv2.LINE_AA)
    m = (silhouette(plane) * poly / 255.)[..., None]

    # 4. тени/контуры/линия руля из исходника (multiply)
    gray = cv2.cvtColor(plane[..., :3], cv2.COLOR_BGR2GRAY).astype(np.float32)
    base = np.percentile(gray[m[..., 0] > .5], 90)
    shade = np.clip(gray / base, 0, 1)[..., None]

    out = plane.copy()
    out[..., :3] = np.clip(plane[..., :3] * (1 - m) + np.clip(warped, 0, 255) * PAPER * shade * m, 0, 255).astype(np.uint8)
    return out


# Конфиги самолётов (координаты в пикселях шаблона)
PLANES = {
    # хвост «снизу-сзади», как на концепте. template_tail.png — RGBA, фон прозрачный.
    # fin_quad: TL, TR, BR, BL киля (углы продлены до пересечения прямых сторон)
    "tail": dict(
        template="template_tail.png",
        # основание киля — линия стыка с фюзеляжем (356,466) -> (755,367)
        fin_poly=[(224, 26), (392, -4), (763, 365), (354, 466)],
        fin_quad=[(233, 36), (390, 7), (755, 367), (356, 466)],
        faces="right"),
    "b738": dict(
        fin_poly=[(1816, 36), (1912, 36), (1812, 405), (1385, 390)],
        lead=[(1829, 45), (1532, 397)],
        faces="left"),
}

def imread(path):
    # cv2.imread не открывает пути с кириллицей на Windows, поэтому через numpy
    img = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_UNCHANGED)
    if img is None:
        sys.exit(f"Не удалось прочитать картинку: {path}")
    return img


def imwrite(path, img):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imencode(path.suffix or ".png", img)[1].tofile(str(path))


def main():
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description="Накладывает ливрею на хвост самолёта-шаблона")
    ap.add_argument("livery", help="картинка ливреи, например SU.png (путь или имя файла рядом со скриптом)")
    ap.add_argument("-o", "--out", help="куда сохранить (по умолчанию <ливрея>_out.png рядом со скриптом)")
    ap.add_argument("-t", "--template", help="шаблон (по умолчанию из конфига PLANES, рядом со скриптом)")
    ap.add_argument("-p", "--plane", default="tail", choices=PLANES, help="конфиг из PLANES")
    ap.add_argument("--livery-faces", default="right", choices=["left", "right"],
                    help="в какую сторону смотрит нос на картинке ливреи")
    a = ap.parse_args()

    def find(p):
        p = Path(p)
        return p if p.exists() else here / p

    cfg = PLANES[a.plane]
    livery_path, tpl_path = find(a.livery), find(a.template or cfg.get("template", "template.png"))
    for p in (livery_path, tpl_path):
        if not p.exists():
            sys.exit(f"Файл не найден: {p}")

    out = apply_livery(imread(tpl_path), imread(livery_path), cfg["fin_poly"], cfg.get("lead"),
                       cfg["faces"], a.livery_faces, cfg.get("fin_quad"))
    out_path = Path(a.out) if a.out else here / f"{livery_path.stem}_out.png"
    imwrite(out_path, out)
    print("Готово:", out_path)


if __name__ == "__main__":
    main()
