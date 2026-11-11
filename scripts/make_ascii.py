"""One-off: turn an image into colored ASCII art saved at assets/ascii.json.

Run locally (needs Pillow):
  python3 scripts/make_ascii.py photo.png 110,0,640,580  # photo, crop box
  python3 scripts/make_ascii.py assets/avatar.png 85,76,315,328 --invert  # current avatar: bright pixels -> dense glyphs
  python3 scripts/make_ascii.py drawing.png --drawn  # transparent drawing: dark -> dense
Pick a crop box whose aspect matches the grid (photo ~0.91 w/h, drawing ~0.95).
"""
import json
import sys

from PIL import Image, ImageEnhance, ImageOps

RAMP = ".:-=+*#%@@"
PHOTO_RAMP = "=+*#%@"  # dense only: color carries the image


def main(src, drawn=False, box=None, invert=False, lift=0.45, dst="assets/ascii.json"):
    # drawings: 50x22 at 14px. photos need detail: 88x44 at 8px (cell 4.8x10.5)
    cols, rows, font, lh = (50, 22, 14, 20) if drawn else (88, 44, 8, 10.5)
    src_im = Image.open(src).convert("RGBA")
    if box:
        src_im = src_im.crop(box)
    alpha = src_im.getchannel("A").resize((cols, rows), Image.LANCZOS)
    im = src_im.convert("RGB")
    im = ImageEnhance.Color(im).enhance(1.4)
    im = ImageEnhance.Contrast(im).enhance(1.25)
    im = im.resize((cols, rows), Image.LANCZOS)
    gray = ImageOps.autocontrast(im.convert("L"), cutoff=1)
    out = []
    for y in range(rows):
        row = []
        for x in range(cols):
            r, g, b = im.getpixel((x, y))
            v = gray.getpixel((x, y))
            if drawn:
                ch_ = "0" if v > 215 else RAMP[min(9, (255 - v) * 10 // 256)]
            else:
                v = 255 - v if invert else v
                ch_ = PHOTO_RAMP[min(len(PHOTO_RAMP) - 1, v * len(PHOTO_RAMP) // 256)]
                # lift shadows so dark fabric still shows on a dark card
                r, g, b = (int(255 * (c / 255) ** lift) for c in (r, g, b))
            if alpha.getpixel((x, y)) < 128:
                ch_ = " "
            row.append([ch_, f"#{r:02x}{g:02x}{b:02x}"])
        out.append(row)
    json.dump({"font": font, "lh": lh, "rows": out}, open(dst, "w"))
    print("\n".join("".join(c for c, _ in row) for row in out))


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    box = tuple(int(v) for v in args[1].split(",")) if len(args) > 1 else None  # left,top,right,bottom
    invert = "--invert" in sys.argv  # dark subject on bright background (the meatball)
    main(args[0] if args else "assets/avatar.png", drawn="--drawn" in sys.argv, box=box,
         invert=invert, lift=1.0 if invert else 0.45)
