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
import json
import os
import threading

from fastapi import File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse

import jobs
from paintings import PAINTINGS, get_painting

TEST_PASSWORD = os.environ.get("TEST_PASSWORD", "")
TEST_MAX_RUNS = int(os.environ.get("TEST_MAX_RUNS", "300"))
MAX_UPLOAD_BYTES = 20 * 1024 * 1024

_runs = 0
_runs_lock = threading.Lock()


def register(app, run_pipeline, fetch_bytes):
    styles = [{"key": k, "label": v["label"]} for k, v in PAINTINGS.items()]

    @app.get("/test", response_class=HTMLResponse)
    async def test_page():
        return HTML.replace("__STYLES__", json.dumps(styles, ensure_ascii=False))

    @app.post("/test/run")
    async def test_run(
        password: str = Form(...),
        painting_key: str = Form(...),
        strength: str = Form("orta"),
        file: UploadFile = File(...),
    ):
        global _runs

        if not TEST_PASSWORD:
            return JSONResponse(
                status_code=503,
                content={"ok": False, "error": "Test paneli kapalı (TEST_PASSWORD tanımlı değil)."},
            )
        if not hmac.compare_digest(password.encode(), TEST_PASSWORD.encode()):
            return JSONResponse(status_code=401, content={"ok": False, "error": "Şifre yanlış."})

        painting = get_painting(painting_key, strength)
        if not painting:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Geçersiz stil."})

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
  label.chk{display:inline-flex;align-items:center;gap:6px;margin:0 12px 6px 0;font-size:14px}
  input[type=password],select{padding:9px 10px;border:1px solid var(--line);border-radius:8px;font-size:14px;width:100%;max-width:280px}
  button{font:inherit;cursor:pointer}
  .btn{background:var(--g);color:#fff;border:0;border-radius:10px;padding:11px 18px;font-weight:600}
  .btn:disabled{opacity:.45;cursor:not-allowed}
  .btn.sec{background:#fff;color:var(--g);border:1.5px solid var(--g)}
  .small{font-size:12.5px;color:var(--mut)}
  #squint{position:sticky;top:0;z-index:5;background:#fff;border:1px solid var(--line);border-radius:14px;padding:12px 16px;margin-bottom:16px;display:flex;gap:14px;align-items:center;flex-wrap:wrap}
  #squint input[type=range]{flex:1 1 220px}
  #grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:14px}
  .card{background:#fff;border:1px solid var(--line);border-radius:14px;padding:12px}
  .card h3{margin:0;font-size:14px}
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
  .links{font-size:12px;margin-top:6px}
  .links a{color:var(--g2)}
  #lb{position:fixed;inset:0;background:rgba(15,26,19,.94);display:none;align-items:center;justify-content:center;z-index:50}
  #lb img{max-width:92vw;max-height:92vh;border-radius:6px}
  #summary{font-size:14px}
</style>
</head>
<body>
<header>
  <h1>visotale · Test Paneli</h1>
  <p>Fotoğraf yükle, stil seç, sonucu gör, “gözünü kıs” kaydırıcısıyla yüzün çıkıp çıkmadığını dene.</p>
</header>
<main>

  <div class="panel">
    <h2>1) Ayarlar</h2>
    <div class="row">
      <div>
        <div class="small" style="margin-bottom:4px">Şifre</div>
        <input id="pw" type="password" placeholder="TEST_PASSWORD" autocomplete="off">
        <div class="small" style="margin:12px 0 4px">Fotoğraflar (birden fazla seçebilirsin)</div>
        <input id="files" type="file" accept="image/*" multiple>
      </div>
      <div>
        <div class="small" style="margin-bottom:6px">Stiller</div>
        <div id="styles"></div>
        <div class="small" style="margin:10px 0 6px">Belirginlik</div>
        <label class="chk"><input type="checkbox" class="str" value="az"> Az</label>
        <label class="chk"><input type="checkbox" class="str" value="orta" checked> Orta</label>
        <label class="chk"><input type="checkbox" class="str" value="cok"> Çok</label>
      </div>
    </div>
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
var LS = 'visotale_test_pw';
var tasks = [], running = 0, MAXPAR = 2, halted = false;

var pw = document.getElementById('pw');
try { pw.value = sessionStorage.getItem(LS) || ''; } catch (e) {}
pw.addEventListener('input', function () { try { sessionStorage.setItem(LS, pw.value); } catch (e) {} });

var stylesBox = document.getElementById('styles');
STYLES.forEach(function (s, i) {
  var l = document.createElement('label');
  l.className = 'chk';
  l.innerHTML = '<input type="checkbox" class="sty" value="' + s.key + '"' + (['starry_night','yilbasi_agaci','aycicegi_salonu','sakayik_buketi'].indexOf(s.key) >= 0 ? ' checked' : '') + '> ' + s.label;
  stylesBox.appendChild(l);
});

function selected(cls) {
  return Array.prototype.map.call(document.querySelectorAll(cls + ':checked'), function (e) { return e.value; });
}
function updateCount() {
  var n = document.getElementById('files').files.length * selected('.sty').length * selected('.str').length;
  document.getElementById('count').textContent = n + ' üretim ≈ ' + (n * 0.044).toFixed(2) + ' $';
}
document.addEventListener('change', updateCount);
updateCount();

var blur = document.getElementById('blur');
function applyBlur() {
  var v = blur.value;
  document.getElementById('blurv').textContent = v + ' px';
  var imgs = document.querySelectorAll('.res img, #lbimg');
  for (var i = 0; i < imgs.length; i++) imgs[i].style.filter = v > 0 ? 'blur(' + v + 'px)' : '';
}
blur.addEventListener('input', applyBlur);

var grid = document.getElementById('grid');

function labelOf(key) {
  for (var i = 0; i < STYLES.length; i++) if (STYLES[i].key === key) return STYLES[i].label;
  return key;
}

function makeCard(t) {
  var c = document.createElement('div');
  c.className = 'card';
  c.innerHTML =
    '<h3>' + labelOf(t.style) + ' · ' + t.strength + '</h3>' +
    '<div class="meta"></div>' +
    '<div class="imgs"><div class="side"><img class="orig" alt=""><img class="cond" alt="" style="display:none"></div>' +
    '<div class="res"><div class="st">Sırada…</div></div></div>' +
    '<div class="rate"></div><div class="links"></div>';
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
    document.getElementById('lbimg').src = url;
    document.getElementById('lb').style.display = 'flex';
    applyBlur();
  });
  if (d.debug && d.debug.conditioning_url) {
    var cd = t.card.querySelector('.cond');
    cd.src = d.debug.conditioning_url; cd.style.display = 'block';
  }
  t.card.querySelector('.meta').textContent = t.file.name + ' · ' + d.elapsed_s + ' sn';
  t.elapsed = d.elapsed_s;
  t.card.querySelector('.links').innerHTML =
    '<a target="_blank" rel="noopener" href="' + d.preview_url + '">filigranlı önizleme</a>';
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
  var el = document.getElementById('summary');
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
    fd.append('strength', t.strength);
    fd.append('file', t.file);
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

document.getElementById('go').addEventListener('click', function () {
  var files = document.getElementById('files').files;
  var sty = selected('.sty'), str = selected('.str');
  if (!pw.value) { alert('Şifreyi gir.'); return; }
  if (!files.length || !sty.length || !str.length) { alert('Fotoğraf, stil ve belirginlik seç.'); return; }
  var n = files.length * sty.length * str.length;
  if (n > 40 && !confirm(n + ' üretim başlayacak (≈ ' + (n * 0.044).toFixed(2) + ' $). Devam?')) return;
  halted = false;
  Array.prototype.forEach.call(files, function (f) {
    var u = URL.createObjectURL(f);
    sty.forEach(function (s) {
      str.forEach(function (z) {
        var t = { file: f, objUrl: u, style: s, strength: z, rate: {}, started: false };
        tasks.push(t); makeCard(t);
      });
    });
  });
  summarize(); pump();
});

document.getElementById('lb').addEventListener('click', function () { this.style.display = 'none'; });

document.getElementById('csv').addEventListener('click', function () {
  var rows = [['dosya', 'stil', 'belirginlik', 'tablo_taniniyor', 'yuz_cikiyor', 'yapistirilmis_his', 'sure_sn', 'hata']];
  tasks.forEach(function (t) {
    rows.push([t.file.name, t.style, t.strength, t.rate.known ? 1 : 0, t.rate.face ? 1 : 0, t.rate.pasted ? 1 : 0, t.elapsed || '', t.failed ? 1 : 0]);
  });
  var csv = rows.map(function (r) { return r.map(function (c) { return '"' + String(c).replace(/"/g, '""') + '"'; }).join(','); }).join('\n');
  var a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob(['﻿' + csv], { type: 'text/csv' }));
  a.download = 'visotale-test-sonuclari.csv';
  a.click();
});
</script>
</body>
</html>
"""
