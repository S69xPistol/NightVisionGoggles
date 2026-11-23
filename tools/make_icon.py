"""
Generates icon.png (256 px, used for the tray and the window) and icon.ico
(16-256 px, used for the .exe and the taskbar) in the project root.

Two drawings of the same quad-tube night-vision goggles:
  - detailed (strap, mount, glowing lenses) for 32 px and up
  - simplified (no strap/mount, bigger lenses) for 16 and 24 px
Coordinates are on a 64x64 grid, like the SVG mockup.

Run from the project root:  python tools/make_icon.py
"""
import os
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

STRAP = (91, 104, 83, 255)
BODY = (59, 70, 54, 255)
EDGE = (122, 138, 112, 255)
LENS_BG = (21, 27, 19, 255)
GLOW_IN = (217, 255, 201)
GLOW_MID = (111, 227, 79)
GLOW_OUT = (20, 97, 42)
GLOW_FLAT = (125, 255, 106, 255)

SS = 16  # supersampling factor


def _circle(d, cx, cy, r, k, fill, outline=None, width=0):
    d.ellipse([(cx - r) * k, (cy - r) * k, (cx + r) * k, (cy + r) * k], fill=fill,
              outline=outline, width=int(width * k) if outline else 0)


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _glow(d, cx, cy, r, k):
    """Radial gradient lens: light centre -> green -> dark rim."""
    steps = 24
    for i in range(steps, 0, -1):
        t = i / steps
        col = _lerp(GLOW_MID, GLOW_OUT, (t - 0.45) / 0.55) if t > 0.45 else _lerp(GLOW_IN, GLOW_MID, t / 0.45)
        _circle(d, cx, cy - r * 0.1 * (1 - t), r * t, k, col + (255,))


def draw_detailed(size):
    k = size * SS / 64
    img = Image.new("RGBA", (size * SS, size * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # head strap: a flat elliptical arc behind the housing
    d.arc([7 * k, 9 * k, 57 * k, 47 * k], 190, 350, fill=STRAP, width=int(4 * k))
    d.rounded_rectangle([27 * k, 18 * k, 37 * k, 28 * k], radius=2 * k, fill=BODY)
    d.rounded_rectangle([4 * k, 26 * k, 60 * k, 41 * k], radius=6 * k, fill=BODY, outline=EDGE, width=int(2 * k))
    for cx, cy, r, g in ((10.5, 45, 7, 4.2), (24.5, 46, 7.5, 4.6), (39.5, 46, 7.5, 4.6), (53.5, 45, 7, 4.2)):
        _circle(d, cx, cy, r, k, LENS_BG, EDGE, 2)
        _glow(d, cx, cy, g, k)
    return img.resize((size, size), Image.LANCZOS)


def draw_simple(size):
    k = size * SS / 64
    img = Image.new("RGBA", (size * SS, size * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([2 * k, 16 * k, 62 * k, 34 * k], radius=6 * k, fill=BODY, outline=EDGE, width=int(3 * k))
    for cx, cy in ((11, 40), (25.5, 41), (38.5, 41), (53, 40)):
        _circle(d, cx, cy, 9.5, k, LENS_BG, EDGE, 3)
        _circle(d, cx, cy, 6, k, GLOW_FLAT)
    return img.resize((size, size), Image.LANCZOS)


def main():
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = {s: (draw_simple(s) if s < 32 else draw_detailed(s)) for s in sizes}
    images[256].save(os.path.join(ROOT, "icon.png"))
    images[256].save(os.path.join(ROOT, "icon.ico"), format="ICO",
                     sizes=[(s, s) for s in sizes],
                     append_images=[images[s] for s in sizes if s != 256])
    print("Wrote icon.png and icon.ico")


if __name__ == "__main__":
    main()
