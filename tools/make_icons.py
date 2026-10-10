"""Generates the app icon (assets/icon.png, .ico, .icns). Requires Pillow: pip install pillow

    python tools/make_icons.py

Każdy rozmiar jest rysowany osobno, z krawędziami wyrównanymi do pikseli: zmniejszona duża ikona
była przy 16–32 px rozmyta (cienkie, półprzezroczyste słupki zlewały się w plamę).
"""
import os

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
SS = 8  # rysujemy w 8× większej skali i zmniejszamy — gładkie zaokrąglenia
# rozmiary dla skalowania ekranu 100–200% (pasek tytułu: 16·skala, pasek zadań / Alt+Tab: 32·skala)
ICO_SIZES = (16, 20, 24, 28, 32, 40, 48, 56, 64, 72, 80, 96, 128, 256)
# słupki fali dźwięku (wysokość względem pola fali) — mniej i grubsze w małych ikonach
BARS = {
    "small": [0.45, 0.8, 1.0, 0.7, 0.4],
    "medium": [0.35, 0.65, 0.9, 1.0, 0.75, 0.5, 0.3],
    "large": [0.25, 0.5, 0.8, 0.6, 1.0, 0.7, 0.45, 0.65, 0.3],
}


def lerp(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def draw(size):
    """Ikona w rozmiarze size×size. Współrzędne liczone w pikselach docelowych i zaokrąglane."""
    n = size * SS
    px = lambda v: round(v) * SS  # wyrównanie do siatki pikseli docelowego rozmiaru
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))

    # tło: zaokrąglony kwadrat z pionowym gradientem
    grad = Image.new("RGBA", (n, n))
    top, bottom = (72, 140, 255), (37, 89, 214)
    gd = ImageDraw.Draw(grad)
    for y in range(n):
        gd.line([(0, y), (n, y)], fill=lerp(top, bottom, y / n) + (255,))
    mask = Image.new("L", (n, n), 0)
    margin = round(size * 0.06) if size >= 48 else (1 if size >= 20 else 0)
    ImageDraw.Draw(mask).rounded_rectangle([margin * SS, margin * SS, n - margin * SS - 1, n - margin * SS - 1],
                                           radius=round(n * 0.2), fill=255)
    img.paste(grad, (0, 0), mask)

    # symbole na osobnej warstwie i alpha_composite — ImageDraw nadpisuje kanał alfa zamiast mieszać kolory
    layer = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    white = (255, 255, 255, 255)
    wave = (255, 255, 255, 255 if size < 96 else 200)
    inner = size - 2 * margin

    # fala dźwięku (mowa) w górnej części
    bars = BARS["small" if size < 40 else "medium" if size < 96 else "large"]
    bw = max(1, round(inner * (0.09 if size < 40 else 0.06 if size < 96 else 0.045)))
    gap = max(1, round(bw * (0.8 if size < 40 else 0.7)))
    total = len(bars) * bw + (len(bars) - 1) * gap
    x = (size - total) // 2
    cy, wave_h = margin + inner * 0.36, inner * (0.38 if size < 40 else 0.34)
    for h in bars:
        hh = max(bw, round(wave_h * h))
        y0 = round(cy - hh / 2)
        d.rounded_rectangle([px(x), px(y0), px(x + bw) - 1, px(y0 + hh) - 1], radius=bw * SS / 2, fill=wave)
        x += bw + gap

    # dwie linijki napisów na dole
    lh = max(2, round(inner * 0.085))
    step = lh + max(1, round(inner * 0.06))
    y = round(margin + inner * 0.63)
    for w in (0.66, 0.46):
        lw = round(inner * w)
        x0 = (size - lw) // 2
        d.rounded_rectangle([px(x0), px(y), px(x0 + lw) - 1, px(y + lh) - 1], radius=lh * SS / 2, fill=white)
        y += step

    return Image.alpha_composite(img, layer).resize((size, size), Image.LANCZOS)


def main():
    os.makedirs(ASSETS, exist_ok=True)
    frames = {s: draw(s) for s in ICO_SIZES + (512, 1024)}
    frames[512].save(os.path.join(ASSETS, "icon.png"))
    # każda klatka ICO narysowana osobno (append_images), a nie zmniejszona z dużej
    frames[256].save(os.path.join(ASSETS, "icon.ico"), sizes=[(s, s) for s in ICO_SIZES],
                     append_images=[frames[s] for s in ICO_SIZES if s != 256])
    frames[1024].save(os.path.join(ASSETS, "icon.icns"))
    print("assets/icon.png, icon.ico, icon.icns")


if __name__ == "__main__":
    main()
