from __future__ import annotations

import hashlib
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
    "radiotedu_station": {
        "bg": "#2634c7",
        "paper": "#ede5d8",
        "line": "#f8f3ea",
        "accent": "#ef233c",
        "logo": "white",
    },
    "morning_signal": {
        "bg": "#f1e9dc",
        "paper": "#111111",
        "line": "#151515",
        "accent": "#ef233c",
        "logo": "dark",
    },
    "campus_frequencies": {
        "bg": "#10131b",
        "paper": "#edf7f6",
        "line": "#62e6df",
        "accent": "#ef233c",
        "logo": "white",
    },
    "night_lab": {
        "bg": "#1d255f",
        "paper": "#f2eadc",
        "line": "#f4efe7",
        "accent": "#8fd5ff",
        "logo": "white",
    },
    "weekend_transmission": {
        "bg": "#0f3b34",
        "paper": "#efe6d4",
        "line": "#f7eecb",
        "accent": "#ffb703",
        "logo": "white",
    },
}

LOGO_ASSET = "radiotedu_logo.png"
LOGO_SOURCE = "radiotedu_logo_source.png"
LOGO_SOURCE_WHITE = "radiotedu_logo_source_white.png"


def generate_covers(settings: Settings) -> list[str]:
    settings.covers_path.mkdir(parents=True, exist_ok=True)
    _write_logo_asset(settings.covers_path)
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
    palette = PALETTES[key]
    image = Image.new("RGBA", (1024, 1024), palette["bg"])
    draw = ImageDraw.Draw(image)
    border = 25
    draw.rectangle((0, 0, 1023, 1023), outline=palette["paper"], width=border)
    _paper_grain(image, key)
    _draw_modern_lines(image, key, palette)
    _paste_logo(image, path.parent, palette["logo"])
    label_font = _font(30)
    text_fill = palette["paper"]
    if key == "morning_signal":
        text_fill = palette["paper"]
    draw = ImageDraw.Draw(image)
    if key != "radiotedu_station":
        draw.text((58, 66), _program_label(key), fill=text_fill, font=label_font)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(path, quality=95)


def _draw_modern_lines(image, key: str, palette: dict[str, str]) -> None:
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    rng = _rng(key)
    line = _hex_to_rgba(palette["line"], 205)
    faint = _hex_to_rgba(palette["line"], 90)
    accent = _hex_to_rgba(palette["accent"], 190)
    draw.line((26, 670, 998, 110), fill=line, width=3)
    draw.line((690, 26, 690, 998), fill=faint, width=3)
    draw.line((26, 702, 998, 928), fill=faint, width=3)
    ellipses = [
        (210, 70, 1010, 450),
        (80, 520, 965, 895),
        (330, 690, 930, 1010),
    ]
    offsets = {
        "radiotedu_station": (0, 0),
        "morning_signal": (-80, 38),
        "campus_frequencies": (45, -22),
        "night_lab": (-20, 70),
        "weekend_transmission": (70, 35),
    }[key]
    for index, box in enumerate(ellipses):
        dx, dy = offsets
        jitter = rng.randint(-28, 28)
        shifted = (
            box[0] + dx + jitter,
            box[1] + dy - jitter,
            box[2] + dx - jitter,
            box[3] + dy + jitter,
        )
        draw.ellipse(shifted, outline=line if index == 0 else faint, width=2)
    for i in range(3):
        y = 150 + i * 245 + rng.randint(-18, 18)
        points = []
        for x in range(40, 990, 28):
            wave = math.sin((x / (74 + i * 11)) + rng.random() * 2.2) * (10 + i * 7)
            points.append((x, y + wave))
        draw.line(points, fill=faint, width=1)
    if key in {"campus_frequencies", "weekend_transmission"}:
        draw.arc((130, 150, 970, 990), 198, 322, fill=accent, width=3)
    elif key == "morning_signal":
        draw.line((140, 950, 920, 80), fill=accent, width=3)
    image.alpha_composite(overlay)


def _paste_logo(image, covers_path: Path, variant: str) -> None:
    source = covers_path / (LOGO_SOURCE_WHITE if variant == "white" else LOGO_SOURCE)
    if not source.exists() or Image is None:
        return
    logo = Image.open(source).convert("RGBA")
    logo.thumbnail((240, 68), Image.Resampling.LANCZOS)
    x = 1024 - logo.width - 58
    y = 60
    image.alpha_composite(logo, (x, y))


def _write_logo_asset(covers_path: Path) -> None:
    if Image is None:
        return
    source = covers_path / LOGO_SOURCE
    target = covers_path / LOGO_ASSET
    if not source.exists():
        return
    logo = Image.open(source).convert("RGBA")
    logo.thumbnail((720, 140), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (760, 160), (0, 0, 0, 0))
    canvas.alpha_composite(logo, ((canvas.width - logo.width) // 2, (canvas.height - logo.height) // 2))
    canvas.save(target)


def _paper_grain(image, key: str) -> None:
    pixels = image.load()
    rng = _rng(f"grain:{key}")
    for _ in range(18000):
        x = rng.randrange(25, 999)
        y = rng.randrange(25, 999)
        delta = rng.choice((-5, -3, 3, 5))
        r, g, b, a = pixels[x, y]
        pixels[x, y] = (
            max(0, min(255, r + delta)),
            max(0, min(255, g + delta)),
            max(0, min(255, b + delta)),
            a,
        )


def _hex_to_rgba(value: str, alpha: int) -> tuple[int, int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4)) + (alpha,)


def _rng(seed: str):
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    state = int.from_bytes(digest[:8], "big")

    class Generator:
        def _next(self) -> int:
            nonlocal state
            state = (6364136223846793005 * state + 1442695040888963407) & ((1 << 64) - 1)
            return state

        def randint(self, start: int, end: int) -> int:
            return start + self._next() % (end - start + 1)

        def randrange(self, start: int, end: int) -> int:
            return start + self._next() % (end - start)

        def choice(self, values):
            return values[self._next() % len(values)]

        def random(self) -> float:
            return self._next() / float(1 << 64)

    return Generator()


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
