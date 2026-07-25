"""
Visotale — 4 amiral gemisi tablo tanımı.

Her tablonun prompt / negative_prompt / controlnet_conditioning_scale değeri,
fal.ai illusion-diffusion playground'unda elle test edilip onaylanan
değerlerdir (bkz. proje sohbet geçmişi). Buradaki sayıları değiştirirken
dikkatli ol — her biri "tablo tanınıyor + yüz gizli ama gözünü kısınca
çıkıyor" dengesi için özel ayarlandı.
"""

COMMON_NEGATIVE = (
    "(low quality, worst quality:1.4), text, signature, watermark, blurry, "
    "deformed, photograph, realistic pasted face, 3d render, human, person"
)

PAINTINGS = {
    "starry_night": {
        "label": "Yıldızlı Gece",
        "artist": "Van Gogh",
        "prompt": (
            'Vincent van Gogh "The Starry Night", post-impressionist oil painting, '
            "swirling glowing night sky with spiraling cobalt-blue and indigo currents, "
            "large radiant golden-yellow stars and a crescent moon, dark flame-like "
            "cypress tree, small village with a church spire and rolling hills, heavy "
            "impasto thick expressive brushstrokes, masterpiece, museum quality wall "
            "art, 8k"
        ),
        "negative_prompt": COMMON_NEGATIVE,
        "conditioning_scale": 1.1,
        "guidance_scale": 7.5,
        "num_inference_steps": 20,
        "control_guidance_end": 0.80,
    },
    "monet_bridge": {
        "label": "Nilüfer Havuzu / Japon Köprüsü",
        "artist": "Claude Monet",
        "prompt": (
            'Claude Monet "The Water Lily Pond", impressionist oil painting, green '
            "arched Japanese footbridge over a pond, weeping willows and dense green "
            "foliage, water lilies with pink and white blossoms on rippling water, "
            "soft dappled light, blue-green reflections, loose impressionist "
            "brushstrokes, masterpiece, museum quality wall art, 8k"
        ),
        "negative_prompt": COMMON_NEGATIVE,
        "conditioning_scale": 1.15,
        "guidance_scale": 7.5,
        "num_inference_steps": 20,
        "control_guidance_end": 0.80,
    },
    "baroque_bouquet": {
        "label": "Barok Çiçek Buketi",
        "artist": "Klasik natürmort",
        "prompt": (
            "Opulent Dutch Baroque flower still life, a lush overflowing bouquet of "
            "roses, peonies, tulips and ranunculus in crimson, deep pink, white, "
            "cream and violet, dense overlapping petals and foliage filling the "
            "upper canvas, arranged in an ornate polished bronze footed urn with "
            "clear reflective highlights, sculpted detailing and a defined "
            "silhouette against the dark background, dramatic chiaroscuro "
            "lighting, oil painting with thick textured brushwork, masterpiece, "
            "museum quality wall art, 8k"
        ),
        "negative_prompt": COMMON_NEGATIVE,
        "conditioning_scale": 1.15,
        "guidance_scale": 7.5,
        "num_inference_steps": 20,
        "control_guidance_end": 0.80,
    },
    "sunflower_bouquet": {
        "label": "Ayçiçeği Buketi",
        "artist": "Van Gogh esintili natürmort",
        "prompt": (
            "Opulent Baroque still life of sunflowers, a lush overflowing bouquet "
            "of vivid golden-yellow sunflowers of many sizes packed edge to edge "
            "filling the canvas, interwoven with small wildflowers, wheat stalks, "
            "dried seed heads and dark green foliage in the gaps, warm amber, "
            "ochre and honey tones, arranged in an ornate polished bronze footed "
            "urn with reflective highlights and a defined silhouette, dramatic "
            "chiaroscuro lighting, warm dark background, oil painting with thick "
            "textured brushwork, masterpiece, museum quality wall art, 8k"
        ),
        "negative_prompt": COMMON_NEGATIVE,
        "conditioning_scale": 1.2,
        "guidance_scale": 7.5,
        "num_inference_steps": 20,
        "control_guidance_end": 0.80,
    },
}


def get_painting(key: str):
    return PAINTINGS.get(key)
