from __future__ import annotations

import math
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:  # pragma: no cover
    Image = None
    ImageDraw = None
    ImageFont = None

from .prompts import PROMPTS
from ..config import Settings


PALETTES = {
    "radiotedu_station": ("#f8fafc", "#111827", "#e11d48", "#020617"),
    "morning_signal": ("#fff8e7", "#ef476f", "#ffd166", "#26547c"),
    "campus_frequencies": ("#f4fff8", "#2a9d8f", "#3a86ff", "#1d3557"),
    "night_lab": ("#10131f", "#7bdff2", "#b2f7ef", "#f7d6e0"),
    "weekend_transmission": ("#fffaf0", "#ff9f1c", "#2ec4b6", "#264653"),
}


def generate_covers(settings: Settings) -> list[str]:
    settings.covers_path.mkdir(parents=True, exist_ok=True)
    paths = []
    for name in PROMPTS:
        path = settings.covers_path / f"{name}.png"
        draw_cover(path, name)
        paths.append(str(path))
    return paths


def draw_cover(path: Path, key: str) -> None:
    if Image is None or ImageDraw is None:
        path.write_bytes(b"")
        return
    bg, primary, accent, ink = PALETTES[key]
    image = Image.new("RGB", (1024, 1024), bg)
    draw = ImageDraw.Draw(image)
    for i in range(18):
        y = 100 + i * 48
        amp = 20 + (i % 5) * 9
        points = []
        for x in range(80, 950, 18):
            wave = math.sin((x / 70) + i) * amp
            points.append((x, y + wave))
        draw.line(points, fill=primary if i % 2 else accent, width=4)
    draw.ellipse((230, 230, 794, 794), outline=ink, width=8)
    draw.line((512, 210, 512, 820), fill=ink, width=7)
    draw.polygon([(512, 210), (370, 820), (654, 820)], outline=ink)
    for radius in (170, 250, 330):
        draw.arc((512 - radius, 512 - radius, 512 + radius, 512 + radius), 210, 330, fill=accent, width=6)
    title_font = _font(94)
    sub_font = _font(34)
    program_font = _font(42)
    title = "RadioTEDU"
    subtitle = "AI RADIO"
    program = _program_label(key)
    draw.rounded_rectangle((120, 760, 904, 920), radius=28, fill=bg, outline=ink, width=4)
    draw.text((512, 790), title, fill=ink, font=title_font, anchor="mm")
    draw.text((512, 852), subtitle, fill=primary, font=sub_font, anchor="mm")
    if key != "radiotedu_station":
        draw.text((512, 908), program, fill=accent, font=program_font, anchor="mm")
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def _font(size: int):
    if ImageFont is None:
        return None
    for name in ("arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _program_label(key: str) -> str:
    return {
        "morning_signal": "TEDU DAWN",
        "campus_frequencies": "CAMPUS FLOW",
        "night_lab": "JAZZ LAB",
        "weekend_transmission": "WEEKEND SIGNAL",
    }.get(key, "AI RADIO")
