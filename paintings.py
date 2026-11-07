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
            "classic Dutch Golden Age baroque floral still life oil painting, a "
            "huge lush overflowing rounded bouquet of ivory-white peonies and "
            "freesias, royal purple bellflowers, deep burgundy-red carnations, "
            "blush pink ranunculus roses and a few burnt orange tulips, with "
            "slender green leaves and buds, the bouquet filling the upper "
            "three quarters of the canvas, standing in one ornate antique "
            "aged-gold brass urn with a round medallion relief and a footed "
            "base, on a worn dark wooden table with a few fallen blossoms and "
            "petals resting on the table at the bottom, background a dark "
            "mottled brown-black wall with soft painterly brushwork, single "
            "warm light from the upper left, dramatic chiaroscuro, rich "
            "saturated jewel tones, glossy highlights, thick textured oil "
            "paint, Old Masters realism, masterpiece, museum quality wall art, "
            "8k highly detailed"
        ),
        "negative_prompt": COMMON_NEGATIVE + (
            ", picture frame, wooden frame, border, molding, face in the "
            "background, figure in the background, shape in the background, "
            "wallpaper, damask, tablecloth, curtain, drapery, second vase, "
            "multiple vases, vase rim above flowers, cabinet, shelf, door, "
            "mirror, neon colors, pastel washed-out colors, flat illustration"
        ),
        "conditioning_scale": 1.15,
        "guidance_scale": 7.5,
        "num_inference_steps": 20,
        "control_guidance_end": 1.0,
        "conditioning_layout": "cutout",
        "layout_params": {"cx": 0.50, "cy": 0.38, "w": 0.88, "h": 0.66, "feather": 0.10, "bg": 24, "size": 0.68, "halo": 150, "dy": 0.02, "pad_top": 1.0, "fit": 0.92},
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
