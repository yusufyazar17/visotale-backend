"""
Visotale — 4 amiral gemisi tablo tanımı.

Her tablonun prompt / negative_prompt / controlnet_conditioning_scale değeri,
fal.ai illusion-diffusion playground'unda elle test edilip onaylanan
değerlerdir (bkz. proje sohbet geçmişi). Buradaki sayıları değiştirirken
dikkatli ol — her biri "tablo tanınıyor + yüz gizli ama gözünü kısınca
çıkıyor" dengesi için özel ayarlandı.

STRENGTH_DELTA: müşterinin seçtiği "Az / Orta / Çok" belirginlik seviyesi,
tablonun temel conditioning_scale değerine eklenen/çıkarılan bir pay.
"Az" -> yüz daha gizli ama tablo daha sağlam kalır (bozulma riski azalır).
"Çok" -> yüz daha belirgin çıkar ama tablo bozulma riski artar.
"""

COMMON_NEGATIVE = (
    "(low quality, worst quality:1.4), text, signature, watermark, blurry, "
    "deformed, photograph, realistic pasted face, 3d render, human, person, "
    "asymmetry, mutated, disfigured, extra limbs, cropped, out of frame, "
    "jpeg artifacts, compression artifacts, duplicate, tiling, grainy, "
    "poorly drawn, bad anatomy, disproportionate"
)

STRENGTH_DELTA = {
    "az": -0.10,
    "orta": 0.0,
    "cok": 0.10,
}

PAINTINGS = {
    "starry_night": {
        "label": "Yıldızlı Gece",
        "artist": "Van Gogh",
        "prompt": (
            'Vincent van Gogh "The Starry Night" (1889), post-impressionist oil '
            "painting on canvas, turbulent night sky filled with swirling spiral "
            "currents in deep ultramarine, cobalt blue, and indigo blending into "
            "pale cerulean, eleven radiant golden-yellow stars each haloed with "
            "concentric glowing rings, one oversized luminous crescent moon in "
            "the upper right glowing amber-gold, one tall dark flame-shaped "
            "cypress tree in the foreground reaching into the sky with twisting "
            "black-green silhouette, small sleeping village below with pointed "
            "blue-roofed cottages and one tall church spire, rolling indigo hills "
            "in the background, thick heavy impasto brushstrokes applied in "
            "rhythmic curving strokes following the movement of the sky, visible "
            "raised paint texture, rich saturated color palette, masterpiece, "
            "museum quality wall art, gallery lighting, 8k highly detailed"
        ),
        "negative_prompt": COMMON_NEGATIVE,
        "conditioning_scale": 1.1,
        "guidance_scale": 7.5,
        "num_inference_steps": 20,
        "control_guidance_end": 1.0,
    },
    "monet_bridge": {
        "label": "Nilüfer Havuzu / Japon Köprüsü",
        "artist": "Claude Monet",
        "prompt": (
            'Claude Monet "The Water Lily Pond" (1899), impressionist oil painting '
            "on canvas, Giverny garden, an arched wooden Japanese footbridge "
            "painted soft sage-green spanning the width of the canvas, ornate "
            "curved railings with visible wood grain, cascading weeping willow "
            "branches draping down from both sides framing the bridge, dense "
            "layered green foliage in emerald, olive, and sage tones, calm "
            "pond water beneath scattered with round lily pads and blooming "
            "water lilies in soft pink, white, and pale yellow, gentle mirror-like "
            "reflections of the bridge and trees rippling on the water surface, "
            "warm dappled sunlight filtering through leaves creating patches of "
            "golden light, loose visible impressionist brushstrokes, soft "
            "atmospheric color blending, tranquil plein-air painting, masterpiece, "
            "museum quality wall art, gallery lighting, 8k highly detailed"
        ),
        "negative_prompt": COMMON_NEGATIVE,
        "conditioning_scale": 1.15,
        "guidance_scale": 7.5,
        "num_inference_steps": 20,
        "control_guidance_end": 1.0,
    },
    "baroque_bouquet": {
        "label": "Barok Çiçek Buketi",
        "artist": "Klasik natürmort",
        "prompt": (
            "Opulent 17th-century Dutch Golden Age flower still life in the style "
            "of Jan Davidsz de Heem, a lush overflowing bouquet completely filling "
            "the upper two-thirds of the canvas, layered clusters of full-bloom "
            "crimson and burgundy roses, blush-pink peonies with ruffled petals, "
            "striped orange and yellow parrot tulips, deep purple ranunculus, and "
            "small white blossoms, dense overlapping petals with delicate veined "
            "green leaves and curling stems filling every gap, arranged in an "
            "ornate polished bronze footed urn with engraved floral relief and "
            "bright specular highlights, urn sitting on a dark wooden ledge, "
            "the entire bouquet set against a deep black-brown background, single "
            "dramatic light source from the upper left creating strong chiaroscuro "
            "contrast between illuminated petals and shadowed depths, thick "
            "textured oil paint with visible brushwork and glossy varnish sheen, "
            "masterpiece, museum quality wall art, gallery lighting, 8k highly "
            "detailed"
        ),
        "negative_prompt": COMMON_NEGATIVE,
        "conditioning_scale": 1.15,
        "guidance_scale": 7.5,
        "num_inference_steps": 20,
        "control_guidance_end": 1.0,
    },
    "sunflower_bouquet": {
        "label": "Ayçiçeği Buketi",
        "artist": "Van Gogh esintili natürmort",
        "prompt": (
            "Opulent Baroque-style still life of sunflowers in the spirit of "
            "Van Gogh, a lush overflowing bouquet completely filling the canvas "
            "edge to edge, dozens of vivid golden-yellow sunflowers of varying "
            "sizes and open angles with thick textured brown-black seed centers "
            "and curling ochre petals, interwoven with small orange wildflowers, "
            "golden wheat stalks, dried rust-brown seed heads, and dark olive-green "
            "foliage filling every gap between blooms, arranged in an ornate "
            "polished bronze footed urn with engraved detailing and warm specular "
            "highlights, urn resting on a dark wooden surface, warm amber and "
            "honey-toned dramatic chiaroscuro lighting from one side against a "
            "deep warm-brown background, thick expressive impasto brushstrokes "
            "with visible raised paint texture, masterpiece, museum quality wall "
            "art, gallery lighting, 8k highly detailed"
        ),
        "negative_prompt": COMMON_NEGATIVE,
        "conditioning_scale": 1.2,
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
    painting = dict(base)  # kopya — orijinali değiştirme
    scale = base["conditioning_scale"] + delta
    # güvenli aralık dışına taşmasın (çok düşükte yüz hiç çıkmaz, çok yüksekte tablo bozulur)
    painting["conditioning_scale"] = max(0.85, min(1.5, round(scale, 2)))
    return painting
