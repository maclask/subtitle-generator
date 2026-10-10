"""Generates the app icon (assets/icon.png, .ico, .icns). Requires Pillow: pip install pillow

    python tools/make_icons.py
"""
import os

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
S = 1024  # base size; drawn at 4x and downscaled for smooth edges
SS = 4


def lerp(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def draw():
    n = S * SS
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))

    # tło: zaokrąglony kwadrat z pionowym gradientem
    grad = Image.new("RGBA", (n, n))
    top, bottom = (72, 140, 255), (37, 89, 214)
    gd = ImageDraw.Draw(grad)
    for y in range(n):
        gd.line([(0, y), (n, y)], fill=lerp(top, bottom, y / n) + (255,))
    mask = Image.new("L", (n, n), 0)
    margin = round(n * 0.06)
    ImageDraw.Draw(mask).rounded_rectangle([margin, margin, n - margin, n - margin], radius=round(n * 0.2), fill=255)
    img.paste(grad, (0, 0), mask)

    # symbole na osobnej warstwie i alpha_composite — ImageDraw nadpisuje kanał alfa zamiast mieszać kolory,
    # więc półprzezroczyste słupki „dziurawiłyby” ikonę
    layer = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    white = (255, 255, 255, 255)
    soft = (255, 255, 255, 165)

    # fala dźwięku (mowa) w górnej części
    bars = [0.10, 0.22, 0.36, 0.26, 0.42, 0.30, 0.18, 0.28, 0.12]
    bw, gap = n * 0.045, n * 0.03
    total = len(bars) * bw + (len(bars) - 1) * gap
    x, cy = (n - total) / 2, n * 0.37
    for h in bars:
        hh = n * h * 0.55
        d.rounded_rectangle([x, cy - hh / 2, x + bw, cy + hh / 2], radius=bw / 2, fill=soft)
        x += bw + gap

    # dwie linijki napisów na dole
    lh = n * 0.075
    for i, (w, y) in enumerate([(0.62, 0.62), (0.44, 0.74)]):
        x0 = (n - n * w) / 2
        d.rounded_rectangle([x0, n * y, x0 + n * w, n * y + lh], radius=lh / 2, fill=white)

    return Image.alpha_composite(img, layer).resize((S, S), Image.LANCZOS)


def main():
    os.makedirs(ASSETS, exist_ok=True)
    icon = draw()
    icon.resize((512, 512), Image.LANCZOS).save(os.path.join(ASSETS, "icon.png"))
    icon.save(os.path.join(ASSETS, "icon.ico"), sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    icon.save(os.path.join(ASSETS, "icon.icns"))
    print("assets/icon.png, icon.ico, icon.icns")


if __name__ == "__main__":
    main()
