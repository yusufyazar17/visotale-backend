"""Visotale Studio — yeni üretim ekranı (/studio). /test/run ve /job-status uç noktalarını kullanır."""

STUDIO_HTML = r"""<!doctype html>
<html lang="tr"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>Visotale Studio</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family=Fraunces:opsz,wght@9..144,500;9..144,600&display=swap" rel="stylesheet">
<style>
:root{--g:#1B3E28;--g2:#225033;--acc:#5EC37E;--soft:#E8F7EC;--bg:#FAFAF7;--bg2:#F4F2EC;--line:#E8E8E5;--mut:#6B6B6B;--bad:#D14545}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:#1a1a1a;font-family:'DM Sans',system-ui,sans-serif}
h1,h2{font-family:'Fraunces',Georgia,serif;font-weight:500;margin:0}
header{background:var(--g);color:#fff;padding:16px 24px;display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
header h1{font-size:22px}header span{font-size:13px;opacity:.75}
.wrap{max-width:1180px;margin:0 auto;padding:20px 16px 70px;display:grid;grid-template-columns:380px 1fr;gap:20px}
@media(max-width:860px){.wrap{grid-template-columns:1fr}}
.card{background:#fff;border:1px solid var(--line);border-radius:16px;padding:18px}
.step{display:flex;align-items:center;gap:10px;margin:0 0 10px}
.step b{width:26px;height:26px;border-radius:50%;background:var(--soft);color:var(--g);display:flex;align-items:center;justify-content:center;font-size:13px}
.step h2{font-size:17px}
.sec{margin-bottom:20px}
label.l{display:block;font-size:12.5px;color:var(--mut);margin:10px 0 4px}
input[type=password],input[type=number],textarea,select{width:100%;padding:9px 10px;border:1px solid var(--line);border-radius:10px;font:inherit;font-size:14px;background:#fff}
textarea{min-height:100px;resize:vertical;line-height:1.4}
#drop{border:1.5px dashed #CFCFC8;border-radius:14px;padding:16px;text-align:center;cursor:pointer;background:var(--bg);color:var(--mut);font-size:14px}
#drop.on{border-color:var(--acc);background:var(--soft)}
#drop img{max-width:100%;max-height:200px;border-radius:10px;display:block;margin:0 auto 8px}
#styles{display:grid;grid-template-columns:repeat(2,1fr);gap:8px}
.sty{border:1.5px solid var(--line);background:#fff;border-radius:12px;padding:11px 10px;font:inherit;font-size:14px;font-weight:500;cursor:pointer;text-align:left}
.sty.on{border-color:var(--g);background:var(--soft);color:var(--g)}
.seg{display:flex;gap:6px}.seg button{flex:1;border:1.5px solid var(--line);background:#fff;border-radius:100px;padding:8px;font:inherit;font-size:13.5px;cursor:pointer}
.seg button.on{background:var(--g);color:#fff;border-color:var(--g)}
.go{width:100%;background:var(--g);color:#fff;border:0;border-radius:100px;padding:14px;font:inherit;font-weight:600;font-size:15px;cursor:pointer}
.go:disabled{opacity:.45;cursor:not-allowed}
details summary{cursor:pointer;font-size:13.5px;color:var(--g2);font-weight:500}
.stage{min-height:420px;display:flex;flex-direction:column;gap:14px}
#view{position:relative;background:var(--bg2);border-radius:14px;aspect-ratio:1/1;max-height:70vh;margin:0 auto;width:100%;max-width:640px;overflow:hidden;display:flex;align-items:center;justify-content:center;color:var(--mut);font-size:14px;text-align:center;padding:20px}
#view img{position:absolute;inset:0;width:100%;height:100%;object-fit:contain;transition:filter .08s}
#msg.err{color:var(--bad)}
.squint{display:none;align-items:center;gap:12px;max-width:640px;margin:0 auto;width:100%;font-size:13px;color:var(--mut)}
.squint input{flex:1;accent-color:var(--g)}
.act{display:none;gap:14px;justify-content:center;font-size:13px}
.act a{color:var(--g2)}
#hist{display:flex;gap:8px;flex-wrap:wrap}
#hist img{width:84px;height:84px;object-fit:cover;border-radius:10px;border:2px solid var(--line);cursor:pointer}
#hist img.on{border-color:var(--g)}
.tip{font-size:12px;color:var(--mut);margin-top:4px}
</style></head><body>
<header><h1>visotale · Studio</h1><span>İllüzyonlu tablo üretim ekranı</span></header>
<div class="wrap">
<div class="card">
  <div class="sec"><label class="l" style="margin-top:0">Şifre</label><input id="pw" type="password" placeholder="TEST_PASSWORD" autocomplete="off"></div>
  <div class="sec"><div class="step"><b>1</b><h2>Fotoğraf</h2></div>
    <div id="drop"><span id="dropt">Fotoğraf seç ya da buraya bırak</span></div>
    <input id="file" type="file" accept="image/*" hidden></div>
  <div class="sec"><div class="step"><b>2</b><h2>Stil</h2></div><div id="styles"></div></div>
  <div class="sec"><div class="step"><b>3</b><h2>Yüz belirginliği</h2></div>
    <div class="seg" id="seg"><button data-d="-0.1">Az</button><button data-d="0" class="on">Orta</button><button data-d="0.1">Çok</button></div>
    <div class="tip">Çok: yüz daha belirgin, tablo bozulma riski artar.</div></div>
  <div class="sec"><details><summary>Gelişmiş ayarlar</summary>
    <label class="l">Prompt (bu stile özel, düzenleyebilirsin)</label><textarea id="prompt"></textarea>
    <label class="l">Negatif prompt</label><textarea id="neg"></textarea>
    <label class="l">Yüz yerleşimi</label><select id="layout"><option value="none">Tüm tuval</option><option value="cutout">Buket silüeti (oval)</option></select>
    <label class="l">Adım sayısı</label><input id="steps" type="number" min="10" max="50" value="20">
    <label class="l">Guidance</label><input id="guid" type="number" step="0.5" value="7.5">
    <label class="l">Seed benzeri tekrar sayısı (aynı ayarla kaç görsel)</label><input id="rep" type="number" min="1" max="4" value="1"></details></div>
  <button class="go" id="go">Üret</button>
</div>
<div class="card stage">
  <div id="view"><span id="msg">Fotoğraf ve stil seç, “Üret”e bas.</span></div>
  <div class="squint" id="sq"><span>Net</span><input id="blur" type="range" min="0" max="14" value="0"><span>Gözünü kıs</span></div>
  <div class="act" id="act"><a id="dl" target="_blank" download>İndir</a><a id="rawl" target="_blank">Filigransız / ham görsel</a></div>
  <div id="hist"></div>
</div>
</div>
<script>
var STYLES=__STYLES__, DEF=__DEFAULTS__;
var $=function(i){return document.getElementById(i)};
var cur=STYLES.length?STYLES[0].key:null, delta=0, file=null, hist=[];
try{$('pw').value=sessionStorage.getItem('vpw')||''}catch(e){}
function renderStyles(){var h='';STYLES.forEach(function(s){h+='<button class="sty'+(s.key===cur?' on':'')+'" data-k="'+s.key+'">'+s.label+'</button>'});$('styles').innerHTML=h;
 Array.prototype.forEach.call($('styles').children,function(b){b.onclick=function(){cur=b.dataset.k;renderStyles();loadDef()}})}
function loadDef(){var d=DEF[cur];if(!d)return;$('prompt').value=d.prompt;$('neg').value=d.negative_prompt;$('steps').value=d.num_inference_steps;$('guid').value=d.guidance_scale;$('layout').value=d.layout==='none'?'none':'cutout'}
renderStyles();loadDef();
Array.prototype.forEach.call($('seg').children,function(b){b.onclick=function(){Array.prototype.forEach.call($('seg').children,function(x){x.classList.remove('on')});b.classList.add('on');delta=parseFloat(b.dataset.d)}});
var drop=$('drop');drop.onclick=function(){$('file').click()};
drop.ondragover=function(e){e.preventDefault();drop.classList.add('on')};drop.ondragleave=function(){drop.classList.remove('on')};
drop.ondrop=function(e){e.preventDefault();drop.classList.remove('on');if(e.dataTransfer.files[0])setFile(e.dataTransfer.files[0])};
$('file').onchange=function(){if(this.files[0])setFile(this.files[0])};
function setFile(f){file=f;drop.innerHTML='<img src="'+URL.createObjectURL(f)+'"><span>'+f.name+' — değiştirmek için tıkla</span>'}
function show(url){var v=$('view');v.innerHTML='<img id="im" src="'+url+'">';$('sq').style.display='flex';$('act').style.display='flex';$('blur').value=0;$('dl').href=url;$('rawl').href=url}
$('blur').oninput=function(){var i=$('im');if(i)i.style.filter='blur('+this.value+'px)'};
function msg(t,err){$('view').innerHTML='<span id="msg" class="'+(err?'err':'')+'">'+t+'</span>';$('sq').style.display='none';$('act').style.display='none'}
function addHist(url){hist.unshift(url);var h='';hist.forEach(function(u,i){h+='<img src="'+u+'" data-i="'+i+'">'});$('hist').innerHTML=h;
 Array.prototype.forEach.call($('hist').children,function(im){im.onclick=function(){show(hist[im.dataset.i])}})}
function poll(id,done,fail){var n=0;(function t(){n++;fetch('/job-status/'+id).then(function(r){return r.json()}).then(function(d){
 if(d.status==='done')return done(d);if(d.status==='error')return fail(d.error||'Hata');if(n>120)return fail('Zaman aşımı');setTimeout(t,2000)}).catch(function(){if(n>120)fail('Bağlantı hatası');else setTimeout(t,3000)})})()}
$('go').onclick=function(){
 if(!$('pw').value){alert('Şifreyi gir.');return}if(!file){alert('Önce fotoğraf seç.');return}if(!cur){alert('Stil yok.');return}
 try{sessionStorage.setItem('vpw',$('pw').value)}catch(e){}
 var rep=Math.max(1,Math.min(4,parseInt($('rep').value)||1)),left=rep,btn=$('go');btn.disabled=true;
 msg('Üretiliyor… (30-60 sn sürebilir)');
 function one(){var fd=new FormData();fd.append('password',$('pw').value);fd.append('painting_key',cur);fd.append('file',file);
  fd.append('prompt',$('prompt').value);fd.append('negative_prompt',$('neg').value);
  fd.append('conditioning_scale',(DEF[cur].conditioning_scale+delta).toFixed(2));
  fd.append('guidance_scale',$('guid').value);fd.append('num_inference_steps',$('steps').value);
  fd.append('control_guidance_end',DEF[cur].control_guidance_end);fd.append('layout',$('layout').value);
  fetch('/test/run',{method:'POST',body:fd}).then(function(r){return r.json().then(function(j){return{s:r.status,b:j}})}).then(function(x){
   if(!x.b.ok){msg(x.b.error||'Hata',true);fin();return}
   poll(x.b.job_id,function(d){var u=(d.debug&&d.debug.raw_result_url)||d.preview_url;addHist(u);show(u);fin()},function(e){msg(e,true);fin()})
  }).catch(function(){msg('Sunucuya ulaşılamadı',true);fin()})}
 function fin(){left--;if(left<=0)btn.disabled=false}
 for(var i=0;i<rep;i++)one()
};
</script></body></html>
"""
