"""
Visotale — 12 stil tanımı (sıfırdan yeniden kuruluyor).
Her stil, kullanıcının verdiği referans görselden üretilmiş prompt ile eklenir.
Şimdilik: 1/12 -> klasik_barok
"""

COMMON_NEGATIVE = (
    "(low quality, worst quality:1.4), text, signature, watermark, blurry, "
    "deformed, photograph, realistic pasted face, 3d render, human, person, "
    "asymmetry, mutated, disfigured, extra limbs, cropped, out of frame, "
    "jpeg artifacts, compression artifacts, duplicate, tiling, grainy, "
    "poorly drawn, bad anatomy, disproportionate"
)

STRENGTH_DELTA = {"az": -0.10, "orta": 0.0, "cok": 0.10}

PAINTINGS = {
    "klasik_barok": {
        "label": "Klasik Barok",
        "artist": "Hollanda Altın Çağı çiçek natürmortu",
        "prompt": (
            "dark moody Dutch Golden Age oil painting of a baroque flower "
            "bouquet, loose wide fan-shaped bouquet of large creamy white "
            "peonies, long white freesia and tulip buds, deep burgundy-red "
            "carnations, royal purple bellflowers, a few soft pink roses and "
            "only two or three small orange accents, slender green stems and "
            "pointed leaves, short ornate antique aged-gold urn with a round "
            "medallion relief, dark worn wooden table, very dark mottled "
            "brown-black painterly background with visible brushwork, low-key "
            "dim lighting, strong chiaroscuro, deep shadows, rich dark jewel "
            "tones, thick oil paint texture, craquelure, Rembrandt "
            "atmosphere, painting not photograph"
        ),
        "negative_prompt": COMMON_NEGATIVE + (
            ", photograph, studio photo, bright background, flat gray wall, pastel peach, bright orange dominant, carnation dome, tall fluted goblet, picture frame, wooden frame, border, molding, face in the "
            "background, figure in the background, shape in the background, "
            "wallpaper, damask, tablecloth, curtain, drapery, second vase, "
            "multiple vases, vase rim above flowers, cabinet, shelf, door, "
            "mirror, neon colors, pastel washed-out colors, flat illustration"
        ),
        "conditioning_scale": 1.15,
        "guidance_scale": 7.5,
        "num_inference_steps": 20,
        "control_guidance_end": 1.0,
    },
    "beyaz_sakayik": {
        "label": "Beyaz Şakayık",
        "artist": "Siyah zemin üzerinde beyaz çiçek natürmortu",
        "prompt": (
            "dark moody baroque still life oil painting, a large loose airy "
            "bouquet made only of ivory-white peonies with golden-yellow "
            "centers, white tulips and tiny white wildflowers with dark green "
            "leaves and stems, in a plain cream-white glazed ceramic round "
            "vase, white satin drape hanging on the left, a few white petals "
            "fallen on a dark polished wooden table, pitch black background, "
            "single soft light from the upper left, deep chiaroscuro, "
            "monochrome white and black palette, thick oil paint, painting "
            "not photograph"
        ),
        "negative_prompt": COMMON_NEGATIVE + (
            ", photograph, studio photo, bright background, gray wall, "
            "colored flowers, orange, pink, purple, red, yellow petals, "
            "gold vase, brass urn, picture frame, border, wallpaper, "
            "multiple vases, pastel colors"
        ),
        "conditioning_scale": 1.15,
        "guidance_scale": 7.5,
        "num_inference_steps": 20,
        "control_guidance_end": 1.0,
    },
}


def get_painting(key: str, strength: str = "orta"):
    base = PAINTINGS.get(key)
    if not base:
        return None
    delta = STRENGTH_DELTA.get(strength, 0.0)
    painting = dict(base)
    scale = base["conditioning_scale"] + delta
    painting["conditioning_scale"] = max(0.85, min(1.5, round(scale, 2)))
    return painting
