"""
Önizleme görselini "kaliteyi gösterir ama kullanılamaz" hâle getirir:
  - Uzun kenarı PREVIEW_MAX_DIM'e küçültür (baskıya yetmeyecek çözünürlük)
  - Yarı saydam, tekrarlayan çapraz "VISOTALE" filigranı bindirir

Not: Bu, kararlı bir caydırıcıdır — mutlak bir kopya-koruması değildir.
Ekran görüntüsü her zaman alınabilir; asıl güvence düşük çözünürlük +
görünür filigranın baskıya uygun olmamasıdır.
"""

from PIL import Image, ImageDraw, ImageFont

PREVIEW_MAX_DIM = 900  # düşük çözünürlük — kaliteyi gösterir, baskıya yetmez
WATERMARK_TEXT = "VISOTALE.COM — ÖNİZLEME"


def _load_font(size):
    try:
        return ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size
        )
    except Exception:
        return ImageFont.load_default()


def apply_preview_treatment(img: Image.Image) -> Image.Image:
    img = img.convert("RGB")

    # 1) küçült
    w, h = img.size
    scale = PREVIEW_MAX_DIM / max(w, h)
    if scale < 1:
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    # 2) tekrarlayan çapraz filigran katmanı
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    font = _load_font(max(18, img.width // 22))

    text_w = draw.textlength(WATERMARK_TEXT, font=font)
    step_x = int(text_w * 1.6)
    step_y = int(img.height / 5)

    for row in range(-1, 6):
        y = row * step_y
        offset = (step_x // 2) if (row % 2) else 0
        for col in range(-1, int(img.width / step_x) + 2):
            x = col * step_x + offset
            draw.text((x, y), WATERMARK_TEXT, font=font, fill=(255, 255, 255, 90))

    rotated = layer.rotate(30, expand=False)
    out = Image.alpha_composite(img.convert("RGBA"), rotated)
    return out.convert("RGB")
