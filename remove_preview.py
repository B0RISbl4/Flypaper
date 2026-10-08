"""
Лабораторная работа (задание со звёздочкой): удаление водяного знака PREVIEW,
когда положение плашки (поворот, сдвиг), её цвета и сама картинка меняются.

Что считаем известным (одинаково на всех картинках)
----------------------------------------------------
* плашка — прямая полупрозрачная полоса шириной ~150 px, идущая
  примерно по диагонали снизу-слева вверх-вправо;
* внутри неё — полупрозрачная надпись PREVIEW одним и тем же шрифтом
  (Arial Bold, 50 px) и размером. Её форма лежит в файле-шаблоне
  preview_template.png (как он получен — см. make_template.py).

Что неизвестно и оценивается по каждой картинке
-----------------------------------------------
* угол и положение полосы (с субпиксельной точностью);
* цвет и непрозрачность полосы;
* сдвиг надписи вдоль полосы, её цвет и непрозрачность.

Модель
------
Работаем в premultiplied RGBA: X = (R*A, G*A, B*A, A), значения в [0, 1].
Для картинок без прозрачности A = 1. Полупрозрачный слой с цветом W и
непрозрачностью a накладывается оператором "over":

    X_obs = k + s * X,   где k = a * (W, 1),  s = 1 - a.

Это одна и та же формула и для непрозрачных пикселей, и для прозрачного
фона. Обратное преобразование: X = (X_obs - k) / s. Если слой покрывает
пиксель лишь частично (сглаженный край, доля покрытия c):

    X = (X_obs - c * k) / (1 - c * a).

Алгоритм
--------
1. Грубый поиск полосы. Перебираем углы; для каждого поворачиваем
   картинку так, чтобы полоса шла вертикально, и для каждой прямой
   считаем, на какой доле своей длины она пересекает перепад яркости.
   Края полосы — это две параллельные прямые на расстоянии ~150 px,
   перепад на которых есть почти по всей длине (полоса пересекает и фон,
   и рисунок). Обычные края рисунка так себя не ведут.
2. Оценка слоя полосы (k, s). Берём пары пикселей "внутри / снаружи"
   полосы у её краёв, только там, где фон с обеих сторон однородный.
   Решаем in = k + s * out методом наименьших квадратов с отбрасыванием
   выбросов. Пары на разных цветах фона делают задачу однозначной.
3. Субпиксельное уточнение краёв. Для пикселей у краёв вычисляем долю
   покрытия полосой и подгоняем к ней точную модель сглаживания
   (площадь пикселя по одну сторону прямой) через scipy least_squares.
4. Снимаем полосу обратным смешиванием.
5. Надпись. Грубо совмещаем шаблон PREVIEW с картинкой: нормированная
   корреляция карт градиентов в системе координат полосы.
6. Цвет и непрозрачность надписи — тот же RANSAC/МНК, что для полосы,
   по парам "в 3 px внутри буквы / в 3 px снаружи" у контуров букв.
7. Субпиксельное совмещение шаблона — как для краёв полосы: в пикселях
   контура считаем по цветам долю покрытия буквой и подгоняем под неё
   сдвиг шаблона (scipy least_squares).
8. Снимаем надпись обратным смешиванием с долей покрытия из шаблона.
   На сглаженных краях букв уточняем долю покрытия m попиксельно: берём
   m, при котором восстановленный цвет совпадает с одним из надёжных
   соседей (шаблон отрисован другим растеризатором, чем исходный знак,
   и на краях может немного отличаться).

Запуск:
    python remove_preview.py input.png output.png [--debug]
Зависимости: numpy, opencv-python, scipy.
"""

import argparse
from pathlib import Path

import cv2
import numpy as np
from scipy.ndimage import maximum_filter1d
from scipy.optimize import least_squares

BAND_WIDTH = 150.0                  # ширина полосы, px
ANGLE_RANGE = (25.0, 65.0)          # где искать угол полосы, градусы
TEMPLATE_FILE = Path(__file__).with_name("preview_template.png")

def tol(levels):
    """Порог в долях [0, 1] по числу уровней яркости 0..255. Пороги рассчитаны
    на "чистые" PNG без шума сжатия (как в задании)."""
    return levels / 255.0


# =========================================================== ввод / вывод

def load_image(path):
    """Читает PNG/JPG в premultiplied RGBA float64 [0, 1]."""
    im = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if im is None:
        raise SystemExit(f"не удалось открыть {path}")
    dtype = im.dtype
    scale = float(np.iinfo(dtype).max) if np.issubdtype(dtype, np.integer) else 1.0
    im = im.astype(np.float64) / scale
    if im.ndim == 2:
        im = np.dstack([im] * 3)
    has_alpha = im.shape[2] == 4
    rgb = im[..., 2::-1]                               # BGR(A) -> RGB
    alpha = im[..., 3] if has_alpha else np.ones(im.shape[:2])
    X = np.dstack([rgb * alpha[..., None], alpha])
    return X, has_alpha, dtype


def save_image(path, X, has_alpha, dtype):
    X = np.clip(X, 0, 1)
    a = X[..., 3:]
    rgb = np.where(a > 1e-6, X[..., :3] / np.maximum(a, 1e-6), 0.0)
    rgb = np.clip(rgb, 0, 1)[..., ::-1]                # RGB -> BGR
    out = np.dstack([rgb, a]) if has_alpha else rgb
    scale = float(np.iinfo(dtype).max) if np.issubdtype(dtype, np.integer) else 1.0
    cv2.imwrite(str(path), np.round(out * scale).astype(dtype))


def to_display(X, bg=1.0):
    """Premultiplied RGBA -> 8-bit BGR, прозрачное поверх белого (для отладки)."""
    rgb = X[..., :3] + (1 - X[..., 3:]) * bg
    return np.round(np.clip(rgb, 0, 1) * 255).astype(np.uint8)[..., ::-1]


# ======================================================= геометрия полосы
#
# Угол phi — наклон полосы к горизонтали. В координатах картинки (y вниз):
#   d = ( cos phi, -sin phi)  — вдоль полосы (вправо-вверх),
#   n = ( sin phi,  cos phi)  — нормаль (вправо-вниз).
# Точка P (непрерывные координаты, центр пикселя (x, y) = (x+0.5, y+0.5))
# имеет "поперечную" координату u = n·P и "продольную" v = d·P.
# Полоса: rho_L <= u <= rho_R.

def frame_vectors(phi):
    return np.array([np.sin(phi), np.cos(phi)]), np.array([np.cos(phi), -np.sin(phi)])


def sample_frame(img, n, d, u_vals, v_vals, interp=cv2.INTER_LINEAR):
    """Значения img в точках u*n + v*d. Результат: строки = u, столбцы = v."""
    uu, vv = np.meshgrid(u_vals, v_vals, indexing="ij")
    mx = (uu * n[0] + vv * d[0] - 0.5).astype(np.float32)
    my = (uu * n[1] + vv * d[1] - 0.5).astype(np.float32)
    return cv2.remap(img.astype(np.float32), mx, my, interp,
                     borderMode=cv2.BORDER_CONSTANT, borderValue=0)


def frame_ranges(shape, n, d):
    h, w = shape
    corners = np.array([[0, 0], [w, 0], [0, h], [w, h]], float)
    pu, pv = corners @ n, corners @ d
    return (np.floor(pu.min()), np.ceil(pu.max())), (np.floor(pv.min()), np.ceil(pv.max()))


def edge_scores(X, phi, step_thr=None):
    """Для угла phi: доля длины каждой прямой u = const, где есть перепад."""
    step_thr = step_thr or tol(3)
    n, d = frame_vectors(phi)
    (u0, u1), (v0, v1) = frame_ranges(X.shape[:2], n, d)
    u_vals, v_vals = np.arange(u0, u1), np.arange(v0, v1)
    Y = sample_frame(X, n, d, u_vals, v_vals)
    inside = sample_frame(np.ones(X.shape[:2]), n, d, u_vals, v_vals,
                          cv2.INTER_NEAREST) > 0.5
    step = np.abs(Y[4:] - Y[:-4]).max(-1)               # перепад между u+2 и u-2
    valid = inside[4:] & inside[:-4]
    cnt = valid.sum(1)
    score = ((step > step_thr) & valid).sum(1) / np.maximum(cnt, 1)
    score[cnt < 0.25 * max(X.shape[:2])] = 0            # слишком короткие прямые
    return u_vals[2:-2], score


def find_band_coarse(X, width=BAND_WIDTH, angle_range=ANGLE_RANGE):
    """Перебор угла: ищем две параллельные прямые на расстоянии width,
    на которых перепад есть почти по всей длине."""
    def search(angles):
        best = (-1, None, None)
        wi = int(round(width))
        for phi_deg in angles:
            u, score = edge_scores(X, np.radians(phi_deg))
            partner = maximum_filter1d(score, 7)        # допуск на ширину +-3 px
            pair = np.minimum(score[:-wi], partner[wi:])
            j = int(pair.argmax())
            if pair[j] > best[0]:
                # уточняем положение второго края в окне +-3 px
                jr = j + wi - 3 + int(score[j + wi - 3:j + wi + 4].argmax())
                best = (pair[j], phi_deg, (u[j], u[jr]))
        return best

    sc, phi, _ = search(np.arange(angle_range[0], angle_range[1] + 1e-9, 0.5))
    sc, phi, (rL, rR) = search(np.arange(phi - 0.6, phi + 0.6 + 1e-9, 0.05))
    return np.radians(phi), rL, rR, sc


# ============================================= оценка параметров слоя (k, s)

def _solve_overlay(inner, outer, s_prior):
    """МНК для inner = k + s * outer (premultiplied RGBA), где k_alpha = 1 - s.
    Неизвестные: s и k_rgb. Слабая регуляризация к s_prior действует только
    тогда, когда данные s не определяют (весь фон одного цвета)."""
    m = len(inner)
    A = np.zeros((4 * m + 1, 4))
    rhs = np.zeros(4 * m + 1)
    for c in range(3):                             # i_c = k_c + s * o_c
        A[c:4 * m:4, 0] = outer[:, c]
        A[c:4 * m:4, 1 + c] = 1.0
        rhs[c:4 * m:4] = inner[:, c]
    A[3:4 * m:4, 0] = outer[:, 3] - 1.0            # i_a - 1 = s * (o_a - 1)
    rhs[3:4 * m:4] = inner[:, 3] - 1.0
    lam = 1e-3 * np.sqrt(max(m, 1))
    A[-1, 0], rhs[-1] = lam, lam * s_prior
    sol, *_ = np.linalg.lstsq(A, rhs, rcond=None)
    s = sol[0]
    return np.r_[sol[1:], 1.0 - s], s


def fit_overlay(inner, outer, s_prior=0.7, tol_fit=None, iters=400, seed=0):
    """Робастная оценка слоя по парам (inner, outer): RANSAC + МНК.

    Гипотезу строим по двум парам с заметно разным фоном (иначе s не
    определяется), считаем, сколько пар согласуется с ней с точностью tol,
    лучшую уточняем МНК по согласным парам. Простое отбрасывание пар по
    невязке тут не годится: если фон под краем в основном одного цвета,
    оно "съедает" редкие пары на другом фоне — а только они и определяют s.

    Если весь фон одного цвета, s не определяется, но и не важен: обратное
    смешивание всё равно вернёт правильный цвет этого фона.
    """
    tol_fit = tol_fit or tol(4)
    N = len(inner)
    rng = np.random.default_rng(seed)
    best = None
    for _ in range(iters if N >= 2 else 0):
        i, j = rng.choice(N, 2, replace=False)
        if np.abs(outer[i] - outer[j]).max() < 0.1:
            continue
        k, s = _solve_overlay(inner[[i, j]], outer[[i, j]], s_prior)
        if not 0.02 < s < 0.999:
            continue
        inl = np.abs(inner - (k + s * outer)).max(1) < tol_fit
        if best is None or inl.sum() > best.sum():
            best = inl
    if best is None or best.sum() < 4:
        best = np.ones(N, bool)                    # вырожденный случай
    for _ in range(2):
        k, s = _solve_overlay(inner[best], outer[best], s_prior)
        new = np.abs(inner - (k + s * outer)).max(1) < tol_fit
        if new.sum() >= 4:
            best = new
    return k, s, best


def sample_points(img, P):
    """Билинейная выборка img в точках P (N, 2) в непрерывных координатах."""
    mx = (P[:, 0] - 0.5).astype(np.float32).reshape(1, -1)
    my = (P[:, 1] - 0.5).astype(np.float32).reshape(1, -1)
    out = cv2.remap(img.astype(np.float32), mx, my, cv2.INTER_LINEAR,
                    borderMode=cv2.BORDER_CONSTANT, borderValue=-1)
    return out.reshape(P.shape[0], -1).astype(np.float64)


def edge_pairs(X, phi, rho_L, rho_R, offs=(5.0, 8.0)):
    """Пары пикселей внутри/снаружи полосы у обоих краёв на однородном фоне."""
    n, d = frame_vectors(phi)
    _, (v0, v1) = frame_ranges(X.shape[:2], n, d)
    v = np.arange(v0, v1, 1.0)
    ins, outs = [], []
    for rho, out_sign in ((rho_L, -1), (rho_R, +1)):
        def at(off):
            u = rho + out_sign * off
            P = np.c_[u * n[0] + v * d[0], u * n[1] + v * d[1]]
            return sample_points(X, P)
        o1, o2, i1, i2 = at(offs[0]), at(offs[1]), at(-offs[0]), at(-offs[1])
        ok = (o1.min(1) >= 0) & (o2.min(1) >= 0) & (i1.min(1) >= 0) & (i2.min(1) >= 0)
        ok &= (np.abs(o1 - o2).max(1) < tol(2)) & (np.abs(i1 - i2).max(1) < tol(2))
        ins.append(i1[ok]); outs.append(o1[ok])
    return np.vstack(ins), np.vstack(outs)


# =================================================== точное покрытие пикселя

def coverage_cdf(t, n):
    """Доля площади пикселя с центром на расстоянии t от прямой (с её
    "отрицательной" стороны), для нормали n. Проекция квадрата 1x1 на n —
    сумма двух равномерных величин, её функция распределения — кусочно-
    квадратичная (трапециевидная плотность)."""
    a, b = np.abs(n[0]), np.abs(n[1])
    a, b = max(a, b), min(a, b)
    t = np.asarray(t, float)
    if b < 1e-9:
        return np.clip(t / a + 0.5, 0, 1)
    h, g = (a + b) / 2, (a - b) / 2
    out = np.empty_like(t)
    m1 = t <= -h
    m2 = (t > -h) & (t <= -g)
    m3 = (t > -g) & (t <= g)
    m4 = (t > g) & (t < h)
    m5 = t >= h
    out[m1] = 0
    out[m2] = (t[m2] + h) ** 2 / (2 * a * b)
    out[m3] = b / (2 * a) + (t[m3] + g) / a
    out[m4] = 1 - (h - t[m4]) ** 2 / (2 * a * b)
    out[m5] = 1
    return out


def band_coverage_at(P, phi, rho_L, rho_R):
    n, _ = frame_vectors(phi)
    u = P @ n
    return coverage_cdf(rho_R - u, n) - coverage_cdf(rho_L - u, n)


def refine_band(X, phi, rho_L, rho_R, k, s):
    """Субпиксельное уточнение (phi, rho_L, rho_R) по долям покрытия."""
    a = 1 - s
    n, _ = frame_vectors(phi)
    h, w = X.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    P_all = np.c_[xx.ravel() + 0.5, yy.ravel() + 0.5]
    u_all = P_all @ n
    Xf = X.reshape(-1, 4)

    Ps, cs = [], []
    for rho, out_sign in ((rho_L, -1), (rho_R, +1)):
        sel = np.abs(u_all - rho) < 3.0
        P = P_all[sel]
        o = out_sign * n
        C = sample_points(X, P + 6 * o)          # фон снаружи
        C2 = sample_points(X, P + 9 * o)
        I = sample_points(X, P - 6 * o)          # внутри полосы
        ok = (C.min(1) >= 0) & (C2.min(1) >= 0) & (I.min(1) >= 0)
        ok &= np.abs(C - C2).max(1) < tol(2)
        ok &= np.abs(I - (k + s * C)).max(1) < tol(3)
        D = k - a * C
        den = (D ** 2).sum(1)
        ok &= den > (10 / 255) ** 2
        c = ((Xf[sel] - C) * D).sum(1) / np.maximum(den, 1e-12)
        Ps.append(P[ok]); cs.append(c[ok])
    P, c = np.vstack(Ps), np.concatenate(cs)

    def resid(p):
        return band_coverage_at(P, p[0], p[1], p[2]) - c

    r = least_squares(resid, [phi, rho_L, rho_R], loss="soft_l1", f_scale=0.05,
                      x_scale=[1e-3, 0.1, 0.1])
    rms = np.sqrt(np.median(r.fun ** 2))
    return r.x[0], r.x[1], r.x[2], rms, len(c)


def band_coverage_map(shape, phi, rho_L, rho_R):
    h, w = shape
    yy, xx = np.mgrid[0:h, 0:w]
    P = np.c_[xx.ravel() + 0.5, yy.ravel() + 0.5]
    return band_coverage_at(P, phi, rho_L, rho_R).reshape(h, w)


def remove_band(X, verbose=True):
    phi, rL, rR, sc = find_band_coarse(X)
    if verbose:
        print(f"[полоса] грубо: угол {np.degrees(phi):.2f}°, края u = {rL:.0f} / {rR:.0f},"
              f" перепад на {sc * 100:.0f}% длины")
    inner, outer = edge_pairs(X, phi, rL, rR)
    k, s, keep = fit_overlay(inner, outer)
    phi, rL, rR, rms, npx = refine_band(X, phi, rL, rR, k, s)
    # после уточнения геометрии — ещё раз оцениваем цвет по более точным парам
    inner, outer = edge_pairs(X, phi, rL, rR)
    k, s, keep = fit_overlay(inner, outer)
    a = 1 - s
    if verbose:
        W = k[:3] / max(a, 1e-6)
        spread = outer[keep][:, :3].std(0).max() * 255
        print(f"[полоса] угол {np.degrees(phi):.3f}°, ширина {rR - rL:.2f} px,"
              f" СКО подгонки краёв {rms:.3f} (по {npx} px)")
        print(f"[полоса] непрозрачность a = {a:.4f}, цвет W = {np.round(W * 255, 1)}"
              f"  (пар: {keep.sum()}, разброс фона {spread:.0f})")
    cov = band_coverage_map(X.shape[:2], phi, rL, rR)
    c = cov[..., None]
    # Не обрезаем результат до [0, 1]: под надписью промежуточные значения
    # могут законно выходить за диапазон (если надпись лежит поверх полосы,
    # то после снятия полосы её "эффективный цвет" бывает отрицательным).
    X1 = (X - c * k) / (1 - c * a)
    return X1, cov, (phi, rL, rR)


def clip_premult(X):
    X = np.clip(X, 0, 1)
    X[..., :3] = np.minimum(X[..., :3], X[..., 3:])
    return X


# ================================================================ надпись
#
# Шаблон хранится в 8 раз детальнее картинки (см. make_template.py).
# Координаты шаблона: s — вдоль полосы, t — поперёк, отсчитываются от его
# центра. Пиксель i низкого разрешения соответствует s = i - S/2.

TEMPLATE_SS = 8


def load_template():
    hi = cv2.imread(str(TEMPLATE_FILE), cv2.IMREAD_GRAYSCALE)
    if hi is None:
        raise SystemExit(f"нет файла шаблона {TEMPLATE_FILE}")
    hi = hi.astype(np.float32) / 255.0
    T, S = hi.shape[0] // TEMPLATE_SS, hi.shape[1] // TEMPLATE_SS
    lo = hi.reshape(T, TEMPLATE_SS, S, TEMPLATE_SS).mean((1, 3)).astype(np.float64)
    return hi, lo


def remap_points(img, mx, my):
    """cv2.remap для произвольно длинных массивов координат (у OpenCV есть
    ограничение на размер карт, поэтому режем на строки по 4096)."""
    shp = mx.shape
    mx, my = mx.ravel().astype(np.float32), my.ravel().astype(np.float32)
    n = len(mx)
    pad = (-n) % 4096
    mx = np.r_[mx, np.zeros(pad, np.float32)].reshape(-1, 4096)
    my = np.r_[my, np.zeros(pad, np.float32)].reshape(-1, 4096)
    out = cv2.remap(img, mx, my, cv2.INTER_LINEAR,
                    borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    return out.ravel()[:n].reshape(shp).astype(np.float64)


def matte_at_points(P, hi, phi, rc, dt, vc, sub=4):
    """Доля площади пикселей с центрами P, покрытая буквами: усредняем
    шаблон высокого разрешения по sub x sub точкам внутри пикселя."""
    n, d = frame_vectors(phi)
    T, S = hi.shape[0] / TEMPLATE_SS, hi.shape[1] / TEMPLATE_SS
    o = (np.arange(sub) + 0.5) / sub - 0.5
    ox, oy = [a.ravel() for a in np.meshgrid(o, o)]
    Px = P[:, :1] + ox[None]
    Py = P[:, 1:2] + oy[None]
    s = Px * d[0] + Py * d[1] - vc
    t = Px * n[0] + Py * n[1] - rc - dt
    mx = (s + S / 2 + 0.5) * TEMPLATE_SS - 0.5
    my = (t + T / 2 + 0.5) * TEMPLATE_SS - 0.5
    return remap_points(hi, mx, my).mean(1)


def template_matte(shape, hi, phi, rc, dt, vc):
    """Матта надписи в координатах картинки (считаем только в окрестности надписи)."""
    n, d = frame_vectors(phi)
    T, S = hi.shape[0] / TEMPLATE_SS, hi.shape[1] / TEMPLATE_SS
    corners = np.array([[(rc + dt + t) * n[i] + (vc + s) * d[i] for i in (0, 1)]
                        for s in (-S / 2, S / 2) for t in (-T / 2, T / 2)])
    h, w = shape
    x0, y0 = np.clip(np.floor(corners.min(0)).astype(int) - 1, 0, [w, h])
    x1, y1 = np.clip(np.ceil(corners.max(0)).astype(int) + 1, 0, [w, h])
    m = np.zeros(shape)
    if x1 > x0 and y1 > y0:
        yy, xx = np.mgrid[y0:y1, x0:x1]
        P = np.c_[xx.ravel() + 0.5, yy.ravel() + 0.5]
        m[y0:y1, x0:x1] = matte_at_points(P, hi, phi, rc, dt, vc).reshape(y1 - y0, x1 - x0)
    return m


def grad_mag(img):
    if img.ndim == 2:
        img = img[..., None]
    g = np.zeros(img.shape[:2], np.float32)
    for c in range(img.shape[2]):
        ch = img[..., c].astype(np.float32)
        gx = cv2.Sobel(ch, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(ch, cv2.CV_32F, 0, 1, ksize=3)
        g = np.maximum(g, np.hypot(gx, gy))
    return g


def register_template(X1, lo, phi, rL, rR, max_across=20):
    """Грубое совмещение: ищем сдвиг шаблона вдоль полосы (и немного поперёк)
    по нормированной корреляции карт градиентов. Возвращает
    (dt — сдвиг центра шаблона поперёк от середины полосы, vc — координата
    центра шаблона вдоль полосы, значение корреляции)."""
    n, d = frame_vectors(phi)
    rc = (rL + rR) / 2
    T, S = lo.shape
    _, (v0, v1) = frame_ranges(X1.shape[:2], n, d)
    u_vals = rc + np.arange(T + 2 * max_across) - (T / 2 + max_across)
    v_vals = np.arange(v0, v1)
    G = grad_mag(sample_frame(X1, n, d, u_vals, v_vals))

    ys, xs = np.nonzero(lo > 0.05)
    y0, y1 = ys.min() - 4, ys.max() + 5
    x0, x1 = xs.min() - 4, xs.max() + 5
    Gt = grad_mag(lo)[y0:y1, x0:x1]
    res = cv2.matchTemplate(G, Gt, cv2.TM_CCORR_NORMED)
    _, peak, _, (px, py) = cv2.minMaxLoc(res)

    def parabola(fm, f0, fp):
        den = fm - 2 * f0 + fp
        return 0.0 if abs(den) < 1e-12 else 0.5 * (fm - fp) / den
    sx = parabola(*res[py, px - 1:px + 2]) if 0 < px < res.shape[1] - 1 else 0.0
    sy = parabola(*res[py - 1:py + 2, px]) if 0 < py < res.shape[0] - 1 else 0.0

    u_top = u_vals[0] + py + sy                   # u строки y0 шаблона
    dt = (u_top - y0 + T / 2) - rc
    vc = v_vals[0] + px + sx - x0 + S / 2
    return dt, vc, peak


def contour_samples(X1, m, band_cov, k, s):
    """Пиксели у контура букв, где фон с обеих сторон однородный.
    Для каждого: точка в 3 px снаружи (фон C) и в 3 px внутри буквы.
    Возвращает центры пикселей P, их цвета, C и цвета внутри."""
    gx = cv2.Sobel(m, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(m, cv2.CV_64F, 0, 1, ksize=3)
    mag = np.hypot(gx, gy)
    sel = (m > 0.02) & (m < 0.98) & (mag > 0.5) & (band_cov > 0.999)
    ys, xs = np.nonzero(sel)
    P = np.c_[xs + 0.5, ys + 0.5]
    g = -np.c_[gx[sel], gy[sel]] / mag[sel][:, None]      # наружу из буквы
    I1, I2 = sample_points(X1, P - 3 * g), sample_points(X1, P - 4 * g)
    O1, O2 = sample_points(X1, P + 3 * g), sample_points(X1, P + 4.5 * g)
    mi = sample_points(m[..., None], P - 3 * g)[:, 0]
    mo = sample_points(m[..., None], P + 3 * g)[:, 0]
    bo = sample_points(band_cov[..., None], P + 4.5 * g)[:, 0]
    ok = (mi > 0.95) & (mo < 0.02) & (bo > 0.999)
    ok &= (np.abs(I1 - I2).max(1) < tol(2)) & (np.abs(O1 - O2).max(1) < tol(2))
    if k is not None:
        ok &= np.abs(I1 - (k + s * O1)).max(1) < tol(4)     # внутри = буква на том же фоне
    return P[ok], X1[ys[ok], xs[ok]], O1[ok], I1[ok]


def refine_registration(X1, hi, phi, rc, dt, vc, m, band_cov, k, s):
    """Субпиксельное совмещение шаблона — как с краями полосы: в пикселях
    контура букв считаем долю покрытия по цветам и подгоняем под неё
    сдвиг шаблона (dt, vc)."""
    beta = 1 - s
    P, Xp, C, _ = contour_samples(X1, m, band_cov, k, s)
    D = k - beta * C
    den = (D ** 2).sum(1)
    ok = den > (12 / 255) ** 2
    P, m_data = P[ok], ((Xp[ok] - C[ok]) * D[ok]).sum(1) / den[ok]
    if len(P) < 20:
        return dt, vc, np.nan, len(P)

    def resid(p):
        return matte_at_points(P, hi, phi, rc, p[0], p[1]) - m_data

    r = least_squares(resid, [dt, vc], loss="soft_l1", f_scale=0.05, diff_step=1e-3)
    return r.x[0], r.x[1], np.sqrt(np.median(r.fun ** 2)), len(P)


def remove_text(X1, band_cov, geom, debug=None, verbose=True):
    phi, rL, rR = geom
    rc = (rL + rR) / 2
    hi, lo = load_template()

    # 1. грубое совмещение шаблона
    dt, vc, peak = register_template(X1, lo, phi, rL, rR)
    m = template_matte(X1.shape[:2], hi, phi, rc, dt, vc)

    # 2. цвет и непрозрачность надписи: пары "внутри буквы / снаружи"
    _, _, outer, inner = contour_samples(X1, m, band_cov, None, None)
    k, s, keep = fit_overlay(inner, outer, s_prior=0.5)

    # 3. субпиксельное совмещение, затем ещё раз уточняем цвет
    dt, vc, rms, npts = refine_registration(X1, hi, phi, rc, dt, vc, m, band_cov, k, s)
    m = template_matte(X1.shape[:2], hi, phi, rc, dt, vc)
    _, _, outer, inner = contour_samples(X1, m, band_cov, None, None)
    k, s, keep = fit_overlay(inner, outer, s_prior=0.5)
    beta = 1 - s
    if verbose:
        T = k[:3] / max(beta, 1e-6)
        print(f"[надпись] совмещение: корреляция {peak:.3f}, сдвиг поперёк {dt:+.3f} px,"
              f" невязка покрытия {rms:.3f} (по {npts} px)")
        print(f"[надпись] непрозрачность {beta:.4f}, эффективный цвет {np.round(T * 255, 1)}"
              f"  (пар: {keep.sum()} из {len(inner)})")

    # 4. обратное смешивание с долей покрытия из шаблона
    mm = m[..., None]
    out = clip_premult((X1 - mm * k) / (1 - mm * beta))

    # 5. Края букв. Шаблон отрисован шрифтом Liberation Sans, а знак — другим
    #    растеризатором, поэтому на сглаженных краях доля покрытия может
    #    отличаться на 0.1-0.3, и остаётся еле заметный контур. Уточняем m
    #    для каждого пикселя края: перебираем m и берём то, при котором
    #    восстановленный цвет совпадает с кем-то из надёжных соседей
    #    (внутренность букв и пиксели вне надписи). Значение из шаблона
    #    служит слабой подсказкой.
    k3 = np.ones((3, 3), np.uint8)
    edge = ((m > 0.01) & (m < 0.99)).astype(np.uint8)
    edge = cv2.dilate(edge, k3).astype(bool) & (band_cov > 0.999)
    reliable = ~edge
    ms = np.linspace(0, 1, 101)
    t6 = tol(6)
    r = 3
    h, w = edge.shape
    for y, x in zip(*np.nonzero(edge)):
        y0, y1, x0, x1 = max(0, y - r), min(h, y + r + 1), max(0, x - r), min(w, x + r + 1)
        nb = out[y0:y1, x0:x1][reliable[y0:y1, x0:x1]]
        if len(nb) == 0:
            continue
        cand = (X1[y, x] - ms[:, None] * k) / (1 - ms[:, None] * beta)
        dist = np.linalg.norm(cand[:, None, :] - nb[None, :, :], axis=2).min(1)
        dist += 0.03 * np.abs(ms - m[y, x])
        bad = ((cand < -t6).any(1) | (cand > 1 + t6).any(1)
               | (cand[:, :3] > cand[:, 3:] + t6).any(1))
        dist[bad] += 10
        out[y, x] = cand[dist.argmin()]
    out = clip_premult(out)

    if debug is not None:
        cv2.imwrite(str(debug / "debug_text_matte.png"), np.round(m * 255).astype(np.uint8))
        reg = to_display(X1)
        reg[cv2.Canny(np.round(m * 255).astype(np.uint8), 60, 160) > 0] = (0, 200, 0)
        cv2.imwrite(str(debug / "debug_template_registration.png"), reg)
    return out


# ================================================================== main

def main():
    ap = argparse.ArgumentParser(description="Удаление водяного знака PREVIEW (общий случай)")
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--debug", action="store_true",
                    help="сохранить промежуточные изображения рядом с output")
    args = ap.parse_args()

    X, has_alpha, dtype = load_image(args.input)
    debug = Path(args.output).resolve().parent if args.debug else None

    X1, cov, geom = remove_band(X)
    if debug is not None:
        cv2.imwrite(str(debug / "debug_band_cov.png"), np.round(cov * 255).astype(np.uint8))
        cv2.imwrite(str(debug / "debug_no_band.png"), to_display(X1))

    result = remove_text(X1, cov, geom, debug)
    save_image(args.output, result, has_alpha, dtype)
    print(f"готово: {args.output}")


if __name__ == "__main__":
    main()
