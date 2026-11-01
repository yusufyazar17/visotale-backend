"""
Visotale — şifreli önizleme test paneli.

Kullanım (main.py'nin EN SONUNA ekle):

    import test_page
    test_page.register(app, _run_pipeline, _fetch_source_bytes)

Sonra tarayıcıdan  https://<railway-adresin>/test  aç.

Güvenlik:
  - TEST_PASSWORD ortam değişkeni tanımlı DEĞİLSE üretim kapalıdır (503),
    yani yanlışlıkla herkese açık maliyet oluşmaz.
  - TEST_MAX_RUNS (varsayılan 300): sunucu yeniden başlayana kadar
    en fazla bu kadar üretim yapılır — bütçe sigortası.
Mevcut /job-status/{id} uç noktasını yeniden kullanır, başka bir şeye dokunmaz.
"""

import hmac
import inspect
import io
import json
import os
import threading

from fastapi import File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response

import jobs
from paintings import PAINTINGS, get_painting

# Panelde yalnızca bu stiller listelenir (kafa karışıklığı olmasın diye).
ACTIVE_TEST_STYLES = ("sakayik_buketi", "klasik_barok")

TEST_PASSWORD = os.environ.get("TEST_PASSWORD", "")
TEST_MAX_RUNS = int(os.environ.get("TEST_MAX_RUNS", "300"))
MAX_UPLOAD_BYTES = 20 * 1024 * 1024

_runs = 0
_runs_lock = threading.Lock()


def _clamp(v, lo, hi, default):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, x))


def register(app, run_pipeline, fetch_bytes):
    from image_prep import prepare_conditioning_image, LAYOUT_BOUQUET

    try:
        layout_supported = "conditioning_layout" in inspect.getsource(run_pipeline)
    except Exception:  # noqa: BLE001
        layout_supported = False

    styles = [{"key": k, "label": v["label"]} for k, v in PAINTINGS.items() if k in ACTIVE_TEST_STYLES]
    defaults = {
        k: {
            "prompt": v["prompt"],
            "negative_prompt": v["negative_prompt"],
            "conditioning_scale": v["conditioning_scale"],
            "guidance_scale": v["guidance_scale"],
            "num_inference_steps": v["num_inference_steps"],
            "control_guidance_end": v.get("control_guidance_end", 1.0),
            "layout": v.get("conditioning_layout") or "none",
            "layout_params": v.get("layout_params") or LAYOUT_BOUQUET,
        }
        for k, v in PAINTINGS.items()
        if k in ACTIVE_TEST_STYLES
    }

    @app.get("/test", response_class=HTMLResponse)
    async def test_page():
        return (
            HTML.replace("__STYLES__", json.dumps(styles, ensure_ascii=False))
            .replace("__DEFAULTS__", json.dumps(defaults, ensure_ascii=False))
            .replace("__LAYOUT_OK__", "true" if layout_supported else "false")
        )

    def _check_password(password: str):
        if not TEST_PASSWORD:
            return JSONResponse(
                status_code=503,
                content={"ok": False, "error": "Test paneli kapalı (TEST_PASSWORD tanımlı değil)."},
            )
        if not hmac.compare_digest(password.encode(), TEST_PASSWORD.encode()):
            return JSONResponse(status_code=401, content={"ok": False, "error": "Şifre yanlış."})
        return None

    @app.post("/test/cond")
    async def test_cond(
        password: str = Form(...),
        layout: str | None = Form(None),
        layout_params: str | None = Form(None),
        file: UploadFile = File(...),
    ):
        """Yalnızca hazırlık görselini üretir — illusion fal çağrısı YOK. (Sadece "arka planı sil" modunda ~1 kuruşluk silme çağrısı yapılır; aynı fotoğraf önbelleğe alınır.)"""
        bad = _check_password(password)
        if bad:
            return bad
        raw_bytes = file.file.read()
        if not raw_bytes or len(raw_bytes) > MAX_UPLOAD_BYTES:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Dosya geçersiz."})
        try:
            params = json.loads(layout_params) if layout_params else None
        except ValueError:
            params = None
        lay = "cutout_strict" if layout == "cutout" else (layout if layout == "bouquet" else None)
        try:
            img = prepare_conditioning_image(raw_bytes, lay, params)
        except Exception as e:
            return JSONResponse(status_code=500, content={"ok": False, "error": "Arka plan silinemedi: " + str(e)[:300]})
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=88)
        return Response(content=buf.getvalue(), media_type="image/jpeg")

    @app.post("/test/run")
    async def test_run(
        password: str = Form(...),
        painting_key: str = Form(...),
        file: UploadFile = File(...),
        prompt: str | None = Form(None),
        negative_prompt: str | None = Form(None),
        conditioning_scale: str | None = Form(None),
        guidance_scale: str | None = Form(None),
        num_inference_steps: str | None = Form(None),
        control_guidance_end: str | None = Form(None),
        layout: str | None = Form(None),
        layout_params: str | None = Form(None),
    ):
        global _runs

        bad = _check_password(password)
        if bad:
            return bad

        base = get_painting(painting_key, "orta")
        if not base:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Geçersiz stil."})

        # Panelden gelen değerler (güvenli aralıkta) stilin varsayılanlarını ezer.
        painting = dict(base)
        if prompt and prompt.strip():
            painting["prompt"] = prompt.strip()[:2000]
        if negative_prompt is not None and negative_prompt.strip():
            painting["negative_prompt"] = negative_prompt.strip()[:2000]
        painting["conditioning_scale"] = _clamp(conditioning_scale, 0.3, 2.0, base["conditioning_scale"])
        painting["guidance_scale"] = _clamp(guidance_scale, 1.0, 20.0, base["guidance_scale"])
        painting["num_inference_steps"] = int(_clamp(num_inference_steps, 10, 50, base["num_inference_steps"]))
        painting["control_guidance_end"] = _clamp(
            control_guidance_end, 0.2, 1.0, base.get("control_guidance_end", 1.0)
        )

        if layout is not None:
            painting["conditioning_layout"] = "cutout_strict" if layout == "cutout" else ("bouquet" if layout == "bouquet" else None)
        if layout_params:
            try:
                lp = json.loads(layout_params)
                if isinstance(lp, dict):
                    painting["layout_params"] = lp
            except ValueError:
                pass

        raw_bytes = file.file.read()
        if not raw_bytes:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Boş dosya."})
        if len(raw_bytes) > MAX_UPLOAD_BYTES:
            return JSONResponse(status_code=413, content={"ok": False, "error": "Dosya 20MB sınırını aşıyor."})

        with _runs_lock:
            if _runs >= TEST_MAX_RUNS:
                return JSONResponse(
                    status_code=429,
                    content={"ok": False, "error": f"Test sınırına ulaşıldı ({TEST_MAX_RUNS})."},
                )
            _runs += 1
            used = _runs

        job_id = jobs.create_job({"painting_key": painting_key, "test": True})

        def worker():
            try:
                result = run_pipeline(raw_bytes, painting_key, painting)
                jobs.set_job_done(job_id, result)
            except HTTPException as exc:
                jobs.set_job_error(job_id, str(exc.detail))
            except Exception as exc:  # noqa: BLE001
                jobs.set_job_error(job_id, f"Beklenmedik hata: {exc}")

        threading.Thread(target=worker, daemon=True).start()
        return JSONResponse({"ok": True, "job_id": job_id, "runs_used": used, "runs_max": TEST_MAX_RUNS})


HTML = r"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Visotale Test Paneli</title>
<style>
  :root{--g:#1B3E28;--g2:#225033;--acc:#5EC37E;--soft:#E8F7EC;--bg:#FAFAF7;--line:#E1E1DC;--mut:#6B6B6B;--bad:#D14545}
  *{box-sizing:border-box}
  body{margin:0;font-family:'DM Sans',system-ui,-apple-system,sans-serif;background:var(--bg);color:#1a1a1a}
  header{background:var(--g);color:#fff;padding:18px 24px}
  header h1{margin:0;font-family:Georgia,serif;font-weight:500;font-size:22px}
  header p{margin:4px 0 0;font-size:13px;opacity:.8}
  main{max-width:1280px;margin:0 auto;padding:20px 16px 80px}
  .panel{background:#fff;border:1px solid var(--line);border-radius:14px;padding:16px;margin-bottom:16px}
  .panel h2{margin:0 0 10px;font-size:15px}
  .row{display:flex;flex-wrap:wrap;gap:16px;align-items:flex-start}
  .row>div{flex:1 1 260px}
  .lbl{font-size:12.5px;color:var(--mut);margin:10px 0 4px;display:block}
  input[type=password],input[type=text],select,textarea{padding:9px 10px;border:1px solid var(--line);border-radius:8px;font:inherit;font-size:14px;width:100%}
  textarea{min-height:110px;resize:vertical;line-height:1.4}
  button{font:inherit;cursor:pointer}
  .btn{background:var(--g);color:#fff;border:0;border-radius:10px;padding:11px 18px;font-weight:600}
  .btn:disabled{opacity:.45;cursor:not-allowed}
  .btn.sec{background:#fff;color:var(--g);border:1.5px solid var(--g)}
  .small{font-size:12.5px;color:var(--mut)}
  .hint{font-size:12px;color:var(--mut);margin-top:3px}
  #squint{position:sticky;top:0;z-index:5;background:#fff;border:1px solid var(--line);border-radius:14px;padding:12px 16px;margin-bottom:16px;display:flex;gap:14px;align-items:center;flex-wrap:wrap}
  #squint input[type=range]{flex:1 1 220px}
  #grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:14px}
  .card{background:#fff;border:1px solid var(--line);border-radius:14px;padding:12px}
  .card h3{margin:0;font-size:13.5px;line-height:1.35}
  .meta{font-size:12px;color:var(--mut);margin:2px 0 8px}
  .imgs{display:grid;grid-template-columns:1fr 2fr;gap:8px}
  .imgs .side{display:flex;flex-direction:column;gap:8px}
  .imgs img{width:100%;border-radius:8px;display:block;background:#eee;aspect-ratio:1/1;object-fit:cover}
  .res{position:relative}
  .res img{cursor:zoom-in;transition:filter .1s}
  .st{font-size:13px;padding:30px 8px;text-align:center;color:var(--mut)}
  .st.err{color:var(--bad)}
  .rate{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
  .rate button{border:1px solid var(--line);background:#fff;border-radius:100px;padding:5px 10px;font-size:12.5px}
  .rate button.on{background:var(--soft);border-color:var(--acc);color:var(--g);font-weight:600}
  .rate button.on.bad{background:#fdeaea;border-color:var(--bad);color:var(--bad)}
  .links{font-size:12px;margin-top:6px;display:flex;gap:12px;flex-wrap:wrap}
  .links a,.links button{color:var(--g2);background:none;border:0;padding:0;text-decoration:underline;font-size:12px}
  .note{width:100%;margin-top:6px;font-size:12.5px;padding:6px 8px}
  #lb{position:fixed;inset:0;background:rgba(15,26,19,.94);display:none;align-items:center;justify-content:center;z-index:50}
  #lb img{max-width:92vw;max-height:92vh;border-radius:6px}
  #summary{font-size:14px}
  .grid2{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}
  @media(max-width:560px){#grid{grid-template-columns:1fr}.grid2{grid-template-columns:1fr}}
</style>
</head>
<body>
<header>
  <h1>visotale · Test Paneli</h1>
  <p>Tek stil modu: silüet alanını ayarla (ücretsiz önizleme), sonra üret, “gözünü kıs” ile yüzü ara.</p>
</header>
<main>

  <div class="panel">
    <h2>1) Fotoğraf</h2>
    <div class="row">
      <div>
        <span class="lbl">Şifre</span>
        <input id="pw" type="password" placeholder="TEST_PASSWORD" autocomplete="off">
        <span class="lbl">Fotoğraflar (birden fazla seçebilirsin)</span>
        <input id="files" type="file" accept="image/*" multiple>
      </div>
      <div>
        <span class="lbl">Stil</span>
        <select id="style"></select>
        <button class="btn sec" id="reset" type="button" style="margin-top:10px">Bu stilin varsayılanlarını yükle</button>
      </div>
    </div>
  </div>

  <div class="panel">
    <h2>2) Silüet alanı <span class="small">(yüz yalnızca bu elipste, çiçeklerin içinde olur)</span></h2>
    <div id="layoutwarn" class="small" style="display:none;color:#D14545;margin-bottom:8px">
      Uyarı: main.py güncel değil, bu ayarlar üretime uygulanmaz. Kılavuzdaki tek satırlık main.py değişikliğini yap.
    </div>
    <div class="grid2">
      <div>
        <span class="lbl">Yerleşim</span>
        <select id="layout"><option value="cutout">Arka planı sil + elipse sığdır (YENİ)</option><option value="bouquet">Buket elipsi (kare portre)</option><option value="none">Eski: tüm tuval</option></select>
      </div>
      <div>
        <span class="lbl">Elips dışı parlaklık (0 siyah, 24 önerilen)</span>
        <input id="l_bg" type="text">
      </div>
      <div><span class="lbl">Merkez yatay (0.2–0.8)</span><input id="l_cx" type="text"></div>
      <div><span class="lbl">Merkez dikey (0.2–0.8, küçük=yukarı)</span><input id="l_cy" type="text"></div>
      <div><span class="lbl">Genişlik (0.3–1.0)</span><input id="l_w" type="text"></div>
      <div><span class="lbl">Yükseklik (0.3–1.0)</span><input id="l_h" type="text"></div>
      <div><span class="lbl">Kenar yumuşatma (0–0.4)</span><input id="l_f" type="text"></div>
      <div><span class="lbl">Portre boyutu (0.3–1.0; 0 = elipse otomatik sığdır)</span><input id="l_s" type="text">
        <div class="hint">Kesiliyorsa küçült. 0 yazarsan portrenin tamamı kesinlikle elipse sığar.</div></div>
      <div><span class="lbl">Açık halka parlaklığı (0–255, 150 önerilen)</span><input id="l_halo" type="text">
        <div class="hint">Portre çevresindeki açık zemin. Saçlar kayboluyorsa artır, arka plana iz sızıyorsa düşür.</div></div>
      <div><span class="lbl">Portre dikey kayma (−0.15…0.15, + aşağı)</span><input id="l_dy" type="text">
        <div class="hint">Kafa tepesi kesiliyorsa pozitif yap (portre aşağı iner).</div></div>
      <div><span class="lbl">Kişi sığdırma oranı (0.5–1.0, sadece "arka planı sil")</span><input id="l_fit" type="text">
        <div class="hint">Kişi elipse ne kadar dolu otursun. Taşıyorsa düşür, küçük kalıyorsa artır.</div></div>
      <div><span class="lbl">Baş üstü boşluğu (0.3–1.6)</span><input id="l_pt" type="text">
        <div class="hint">Saç kırpılıyorsa artır. Fotoğrafın kendisinde boşluk yoksa etkisi sınırlıdır.</div></div>
    </div>
    <div style="margin-top:12px;display:flex;gap:12px;align-items:center;flex-wrap:wrap">
      <button class="btn sec" id="prevcond" type="button">Hazırlık önizlemesi (ücretsiz)</button>
      <span class="small">fal.ai çağrılmaz, para harcamaz. Elipsin buketle örtüştüğünü kontrol et.</span>
    </div>
    <div id="condstrip" style="display:flex;gap:10px;flex-wrap:wrap;margin-top:10px"></div>
  </div>

  <div class="panel">
    <h2>3) Ayarlar <span class="small">(virgülle birden fazla değer yazarsan hepsini dener)</span></h2>
    <div class="grid2">
      <div>
        <span class="lbl">ControlNet gücü (yüz ne kadar çıksın)</span>
        <input id="scale" type="text">
        <div class="hint">Yüz hiç çıkmıyorsa artır, çok belliyse düşür. Örnek: 0.9, 1.0, 1.15, 1.3</div>
      </div>
      <div>
        <span class="lbl">Guidance (prompt'a bağlılık)</span>
        <input id="guid" type="text">
        <div class="hint">Yüksek: tablo daha “tablo gibi”, düşük: görsele daha yakın. Örnek: 6.5, 7.5, 9</div>
      </div>
      <div>
        <span class="lbl">Adım sayısı</span>
        <input id="steps" type="text">
        <div class="hint">20-30 arası. Yüksek: yavaş ama temiz olabilir.</div>
      </div>
      <div>
        <span class="lbl">Control guidance end (0.2–1.0)</span>
        <input id="cge" type="text">
        <div class="hint">Düşük: yüz yapısı yalnızca erken adımlarda etkili, daha “doğal”.</div>
      </div>
    </div>
    <span class="lbl">Prompt (tabloyu tarif eden metin, değiştirebilirsin)</span>
    <textarea id="prompt"></textarea>
    <details style="margin-top:8px"><summary class="small" style="cursor:pointer">Negatif prompt</summary>
      <textarea id="neg" style="min-height:70px;margin-top:6px"></textarea>
    </details>
    <div style="margin-top:14px;display:flex;gap:12px;align-items:center;flex-wrap:wrap">
      <button class="btn" id="go">Başlat</button>
      <span id="count" class="small"></span>
    </div>
  </div>

  <div id="squint">
    <strong style="font-size:14px">Gözünü kıs</strong>
    <input id="blur" type="range" min="0" max="14" step="0.5" value="0">
    <span id="blurv" class="small">0 px</span>
    <button class="btn sec" id="csv" type="button">Sonuçları CSV indir</button>
  </div>
  <div class="panel" id="summary">Henüz sonuç yok.</div>

  <div id="grid"></div>
</main>
<div id="lb"><img id="lbimg" alt=""></div>

<script>
var STYLES = __STYLES__;
var DEFAULTS = __DEFAULTS__;
var LAYOUT_OK = __LAYOUT_OK__;
if (!LAYOUT_OK) { document.getElementById('layoutwarn').style.display = 'block'; }
var LS = 'visotale_test_pw';
var tasks = [], running = 0, MAXPAR = 2, halted = false;

function $(id) { return document.getElementById(id); }

var pw = $('pw');
try { pw.value = sessionStorage.getItem(LS) || ''; } catch (e) {}
pw.addEventListener('input', function () { try { sessionStorage.setItem(LS, pw.value); } catch (e) {} });

var sel = $('style');
STYLES.forEach(function (s) {
  var o = document.createElement('option');
  o.value = s.key; o.textContent = s.label;
  sel.appendChild(o);
});
sel.value = DEFAULTS['sakayik_buketi'] ? 'sakayik_buketi' : STYLES[0].key;

function loadDefaults() {
  var d = DEFAULTS[sel.value];
  $('scale').value = d.conditioning_scale;
  $('guid').value = d.guidance_scale;
  $('steps').value = d.num_inference_steps;
  $('cge').value = d.control_guidance_end;
  $('prompt').value = d.prompt;
  $('neg').value = d.negative_prompt;
  $('layout').value = d.layout || 'none';
  var lp = d.layout_params || {};
  $('l_cx').value = lp.cx; $('l_cy').value = lp.cy; $('l_w').value = lp.w;
  $('l_h').value = lp.h; $('l_f').value = lp.feather; $('l_bg').value = lp.bg;
  $('l_s').value = (lp.size === undefined ? 0.68 : lp.size);
  $('l_halo').value = (lp.halo === undefined ? 150 : lp.halo);
  $('l_dy').value = (lp.dy === undefined ? 0.02 : lp.dy);
  $('l_fit').value = (lp.fit === undefined ? 0.92 : lp.fit);
  $('l_pt').value = (lp.pad_top === undefined ? 1.0 : lp.pad_top);
  updateCount();
}
sel.addEventListener('change', loadDefaults);
$('reset').addEventListener('click', loadDefaults);

function nums(str) {
  return String(str).split(',').map(function (x) { return parseFloat(x.trim().replace(',', '.')); })
    .filter(function (x) { return !isNaN(x); });
}
function layoutParams() {
  return JSON.stringify({
    cx: parseFloat($('l_cx').value), cy: parseFloat($('l_cy').value),
    w: parseFloat($('l_w').value), h: parseFloat($('l_h').value),
    feather: parseFloat($('l_f').value), bg: parseFloat($('l_bg').value),
    size: parseFloat($('l_s').value),
    halo: parseFloat($('l_halo').value),
    dy: parseFloat($('l_dy').value),
    pad_top: parseFloat($('l_pt').value),
    fit: parseFloat($('l_fit').value)
  });
}
function updateCount() {
  var n = $('files').files.length * nums($('scale').value).length * nums($('guid').value).length;
  $('count').textContent = n + ' üretim ≈ ' + (n * 0.044).toFixed(2) + ' $';
}
document.addEventListener('change', updateCount);
document.addEventListener('input', function (e) { if (e.target.id === 'scale' || e.target.id === 'guid') updateCount(); });

var blur = $('blur');
function applyBlur() {
  var v = blur.value;
  $('blurv').textContent = v + ' px';
  var imgs = document.querySelectorAll('.res img, #lbimg');
  for (var i = 0; i < imgs.length; i++) imgs[i].style.filter = v > 0 ? 'blur(' + v + 'px)' : '';
}
blur.addEventListener('input', applyBlur);

var grid = $('grid');

function paramText(p) {
  return 'güç ' + p.scale + ' · guid ' + p.guid + ' · adım ' + p.steps + ' · end ' + p.cge;
}

function makeCard(t) {
  var c = document.createElement('div');
  c.className = 'card';
  c.innerHTML =
    '<h3></h3><div class="meta"></div>' +
    '<div class="imgs"><div class="side"><img class="orig" alt=""><img class="cond" alt="" style="display:none"></div>' +
    '<div class="res"><div class="st">Sırada…</div></div></div>' +
    '<div class="rate"></div><div class="links"></div>';
  c.querySelector('h3').textContent = paramText(t.p);
  c.querySelector('.meta').textContent = t.file.name;
  c.querySelector('.orig').src = t.objUrl;
  t.card = c;
  grid.appendChild(c);
}

function setStatus(t, msg, isErr) {
  var r = t.card.querySelector('.res');
  r.innerHTML = '<div class="st' + (isErr ? ' err' : '') + '"></div>';
  r.firstChild.textContent = msg;
}

function showResult(t, d) {
  var url = (d.debug && d.debug.raw_result_url) || d.preview_url;
  var r = t.card.querySelector('.res');
  r.innerHTML = '<img alt="sonuç">';
  var im = r.firstChild;
  im.src = url;
  im.addEventListener('click', function () {
    $('lbimg').src = url;
    $('lb').style.display = 'flex';
    applyBlur();
  });
  if (d.debug && d.debug.conditioning_url) {
    var cd = t.card.querySelector('.cond');
    cd.src = d.debug.conditioning_url; cd.style.display = 'block';
  }
  t.card.querySelector('.meta').textContent = t.file.name + ' · ' + d.elapsed_s + ' sn';
  t.elapsed = d.elapsed_s;
  var links = t.card.querySelector('.links');
  links.innerHTML = '<a target="_blank" rel="noopener" href="' + d.preview_url + '">filigranlı önizleme</a>';
  var use = document.createElement('button');
  use.type = 'button'; use.textContent = 'bu ayarı forma al';
  use.addEventListener('click', function () {
    $('scale').value = t.p.scale; $('guid').value = t.p.guid;
    $('steps').value = t.p.steps; $('cge').value = t.p.cge;
    window.scrollTo({ top: 0, behavior: 'smooth' }); updateCount();
  });
  links.appendChild(use);
  var note = document.createElement('input');
  note.type = 'text'; note.className = 'note'; note.placeholder = 'not (örn. yüz çok belli, ağız bozuk)';
  note.addEventListener('input', function () { t.note = note.value; });
  t.card.appendChild(note);
  buildRate(t);
  applyBlur();
}

function buildRate(t) {
  var box = t.card.querySelector('.rate');
  var defs = [['known', 'Tablo tanınıyor'], ['face', 'Yüz kısınca çıkıyor'], ['pasted', 'Yapıştırılmış his', 'bad']];
  defs.forEach(function (d) {
    var b = document.createElement('button');
    b.type = 'button';
    b.textContent = d[1];
    if (d[2]) b.className = d[2];
    b.addEventListener('click', function () {
      t.rate[d[0]] = !t.rate[d[0]];
      b.classList.toggle('on', t.rate[d[0]]);
      summarize();
    });
    box.appendChild(b);
  });
  summarize();
}

function summarize() {
  var done = tasks.filter(function (t) { return t.elapsed !== undefined; });
  var err = tasks.filter(function (t) { return t.failed; }).length;
  var pass = done.filter(function (t) { return t.rate.known && t.rate.face && !t.rate.pasted; }).length;
  var el = $('summary');
  if (!tasks.length) { el.textContent = 'Henüz sonuç yok.'; return; }
  el.innerHTML = '<b>' + done.length + '</b> sonuç · <b>' + err + '</b> hata · geçen (üç kriter): <b>' + pass + '</b> / ' + done.length +
    (done.length ? ' (%' + Math.round(100 * pass / done.length) + ')' : '') +
    ' <span class="small">— hedef: %80</span>';
}

function poll(t, jobId) {
  var tries = 0;
  (function tick() {
    tries++;
    fetch('/job-status/' + jobId).then(function (r) { return r.json(); }).then(function (d) {
      if (d.status === 'done') { showResult(t, d); finish(); return; }
      if (d.status === 'error') { t.failed = true; setStatus(t, d.error || 'Hata', true); summarize(); finish(); return; }
      if (tries > 120) { t.failed = true; setStatus(t, 'Zaman aşımı', true); summarize(); finish(); return; }
      setTimeout(tick, 2000);
    }).catch(function () {
      if (tries > 120) { t.failed = true; setStatus(t, 'Bağlantı hatası', true); summarize(); finish(); return; }
      setTimeout(tick, 3000);
    });
  })();
}

function finish() { running--; pump(); }

function pump() {
  while (!halted && running < MAXPAR) {
    var t = tasks.find(function (x) { return !x.started; });
    if (!t) break;
    t.started = true; running++;
    setStatus(t, 'Üretiliyor…');
    var fd = new FormData();
    fd.append('password', pw.value);
    fd.append('painting_key', t.style);
    fd.append('file', t.file);
    fd.append('prompt', t.prompt);
    fd.append('negative_prompt', t.neg);
    fd.append('conditioning_scale', t.p.scale);
    fd.append('guidance_scale', t.p.guid);
    fd.append('num_inference_steps', t.p.steps);
    fd.append('control_guidance_end', t.p.cge);
    fd.append('layout', t.layout);
    fd.append('layout_params', t.lp);
    (function (tt) {
      fetch('/test/run', { method: 'POST', body: fd }).then(function (r) {
        return r.json().then(function (j) { return { status: r.status, body: j }; });
      }).then(function (res) {
        if (res.status === 401 || res.status === 503 || res.status === 429) {
          halted = true; tt.failed = true;
          setStatus(tt, res.body.error, true);
          alert(res.body.error);
          running--; summarize(); return;
        }
        if (!res.body.ok) { tt.failed = true; setStatus(tt, res.body.error || 'Hata', true); summarize(); finish(); return; }
        poll(tt, res.body.job_id);
      }).catch(function () { tt.failed = true; setStatus(tt, 'Sunucuya ulaşılamadı', true); summarize(); finish(); });
    })(t);
  }
}

$('go').addEventListener('click', function () {
  var files = $('files').files;
  var scales = nums($('scale').value), guids = nums($('guid').value);
  var steps = nums($('steps').value)[0], cge = nums($('cge').value)[0];
  if (!pw.value) { alert('Şifreyi gir.'); return; }
  if (!files.length) { alert('En az bir fotoğraf seç.'); return; }
  if (!scales.length || !guids.length || steps === undefined || cge === undefined) { alert('Ayar alanlarına sayı gir.'); return; }
  var n = files.length * scales.length * guids.length;
  if (n > 40 && !confirm(n + ' üretim başlayacak (≈ ' + (n * 0.044).toFixed(2) + ' $). Devam?')) return;
  halted = false;
  Array.prototype.forEach.call(files, function (f) {
    var u = URL.createObjectURL(f);
    scales.forEach(function (sc) {
      guids.forEach(function (g) {
        var t = {
          file: f, objUrl: u, style: sel.value, rate: {}, started: false,
          prompt: $('prompt').value, neg: $('neg').value,
          layout: $('layout').value, lp: layoutParams(),
          p: { scale: sc, guid: g, steps: steps, cge: cge }
        };
        tasks.push(t); makeCard(t);
      });
    });
  });
  summarize(); pump();
});

$('prevcond').addEventListener('click', function () {
  var files = $('files').files;
  if (!pw.value) { alert('Şifreyi gir.'); return; }
  if (!files.length) { alert('Önce fotoğraf seç.'); return; }
  var strip = $('condstrip');
  strip.innerHTML = '';
  Array.prototype.forEach.call(files, function (f) {
    var fd = new FormData();
    fd.append('password', pw.value);
    fd.append('file', f);
    fd.append('layout', $('layout').value);
    fd.append('layout_params', layoutParams());
    fetch('/test/cond', { method: 'POST', body: fd }).then(function (r) {
      if (!r.ok) { return r.json().then(function (j) { throw new Error(j.error || 'Hata'); }); }
      return r.blob();
    }).then(function (b) {
      var im = document.createElement('img');
      im.src = URL.createObjectURL(b);
      im.title = f.name;
      im.style.cssText = 'width:150px;height:150px;border-radius:8px;object-fit:cover';
      strip.appendChild(im);
    }).catch(function (e) { alert(e.message); });
  });
});

$('lb').addEventListener('click', function () { this.style.display = 'none'; });

$('csv').addEventListener('click', function () {
  var rows = [['dosya', 'stil', 'guc', 'guidance', 'adim', 'control_end', 'yerlesim', 'tablo_taniniyor', 'yuz_cikiyor', 'yapistirilmis_his', 'sure_sn', 'hata', 'not']];
  tasks.forEach(function (t) {
    rows.push([t.file.name, t.style, t.p.scale, t.p.guid, t.p.steps, t.p.cge, t.layout + ' ' + t.lp,
      t.rate.known ? 1 : 0, t.rate.face ? 1 : 0, t.rate.pasted ? 1 : 0, t.elapsed || '', t.failed ? 1 : 0, t.note || '']);
  });
  var csv = rows.map(function (r) { return r.map(function (c) { return '"' + String(c).replace(/"/g, '""') + '"'; }).join(','); }).join('\n');
  var a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob(['﻿' + csv], { type: 'text/csv' }));
  a.download = 'visotale-test-sonuclari.csv';
  a.click();
});

loadDefaults();
</script>
</body>
</html>
"""
