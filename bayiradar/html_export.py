"""Tek dosyalık HTML çıktısı.

Neden bu var: kullanıcının günlük işi HTML'de olsun, Python'a hiç dokunmasın.
Veri HTML'in İÇİNE gömülüyor — dosya çift tıklanınca açılıyor, internet bile
gerekmiyor. Filtreleme, arama, Excel ve PDF çıktısı tarayıcının kendi içinde.

Tarayıcı başka sitelere gidemez (CORS), o yüzden toplama işi yine Python'da;
ama o iş haftada bir yapılıyor ve kullanıcıyı ilgilendirmiyor.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from .normalize import ILLER, phone_display

# plaka kodu eşlemesi: il adı -> "34"
PLAKA = {ad: f"{i+1:02d}" for i, ad in enumerate(ILLER)}

ALANLAR = ["marka", "bayi_adi", "il", "ilce", "adres", "telefon",
           "email", "website", "veri_durumu"]


def _kompakt(kayitlar):
    """Kayıtları dizi-dizisi haline getirir. Sözlük yerine dizi = ~%60 küçük dosya."""
    satirlar = []
    for k in kayitlar:
        satirlar.append([
            k.get("marka", ""), k.get("bayi_adi", ""), k.get("il", ""),
            k.get("ilce", ""), k.get("adres", ""),
            phone_display(k.get("telefon", "")), k.get("email", ""),
            k.get("website", ""), k.get("veri_durumu", "Güncel"),
        ])
    return satirlar


def to_html(kayitlar, path, marka_durumlari=None, baslik="Motosiklet Bayi Rehberi"):
    veri = {
        "olusturma": datetime.now(timezone.utc).astimezone().isoformat(timespec="minutes"),
        "alanlar": ALANLAR,
        "plaka": PLAKA,
        "satirlar": _kompakt(kayitlar),
        "markalar": [
            {"ad": m["marka"], "adet": m["toplam"], "durum": m["son_deneme_durum"],
             "etiket": m["etiket"], "son": m["son_basarili"]}
            for m in (marka_durumlari or [])
        ],
    }
    html = SABLON.replace("__BASLIK__", baslik).replace(
        "__VERI__", json.dumps(veri, ensure_ascii=False, separators=(",", ":")))
    Path(path).write_text(html, encoding="utf-8")
    return path


SABLON = r"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__BASLIK__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Familjen+Grotesk:wght@400;500;600;700&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{
  --kagit:#F7F6F3; --murekkep:#16202B; --celik:#5F6E7C; --hat:#E2DFD8;
  --hat-koyu:#CBC7BE; --uyari:#A8590C; --uyari-zemin:#FDF3E3;
  --plaka-mavi:#1B4B9E; --vurgu:#0F5E52;
  --golge:0 1px 2px rgba(22,32,43,.06), 0 8px 24px -12px rgba(22,32,43,.18);
  --display:"Familjen Grotesk",system-ui,sans-serif;
  --mono:"DM Mono",ui-monospace,"SF Mono",Menlo,monospace;
}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{
  background:var(--kagit); color:var(--murekkep);
  font-family:var(--display); font-size:15px; line-height:1.45;
  -webkit-font-smoothing:antialiased;
}
button,select,input{font:inherit;color:inherit}

/* ---------- üst rail ---------- */
.rail{
  background:var(--murekkep); color:#EDEAE3;
  padding:14px 22px; display:flex; align-items:center; gap:18px; flex-wrap:wrap;
  position:sticky; top:0; z-index:40;
}
.rail h1{
  font-size:17px; font-weight:600; margin:0; letter-spacing:-.01em;
  display:flex; align-items:center; gap:10px;
}
.rail h1 .mark{
  font-family:var(--mono); font-size:11px; letter-spacing:.14em;
  background:#2A3846; padding:3px 7px; border-radius:3px; color:#9FB0BF;
}
.rail .sag{margin-left:auto; display:flex; align-items:center; gap:14px;
  font-size:12.5px; color:#9FB0BF; font-family:var(--mono)}
.rail .sag b{color:#EDEAE3; font-weight:500}

/* ---------- veri durumu şeridi ---------- */
.uyari-serit{
  background:var(--uyari-zemin); border-bottom:1px solid #EAD9BC;
  color:var(--uyari); padding:9px 22px; font-size:13.5px;
  display:none; align-items:flex-start; gap:9px;
}
.uyari-serit.acik{display:flex}
.uyari-serit svg{flex:none;margin-top:2px}
.uyari-serit button{
  background:none;border:0;text-decoration:underline;cursor:pointer;
  color:inherit;padding:0;font-size:inherit
}

/* ---------- filtre ---------- */
.filtre{
  padding:18px 22px; border-bottom:1px solid var(--hat);
  display:flex; gap:14px; align-items:flex-end; flex-wrap:wrap;
  background:#FCFBF9;
}
.alan{display:flex;flex-direction:column;gap:5px}
.alan > label{
  font-family:var(--mono); font-size:10.5px; letter-spacing:.11em;
  text-transform:uppercase; color:var(--celik);
}
.alan select,.alan input{
  border:1px solid var(--hat-koyu); background:#fff; border-radius:5px;
  padding:8px 11px; min-width:170px; outline:none;
}
.alan select:focus,.alan input:focus{
  border-color:var(--vurgu); box-shadow:0 0 0 3px rgba(15,94,82,.13)
}
.alan input{min-width:230px}
.alan select:disabled{background:#F2F0EC;color:#A7A29A}

/* plaka rozeti — Türk plakası mantığı, il seçimini bu dille gösteriyoruz */
.plaka{
  display:inline-flex; align-items:stretch; height:26px; border-radius:3px;
  overflow:hidden; border:1.5px solid var(--murekkep); background:#fff;
  font-family:var(--mono); line-height:1; user-select:none;
}
.plaka .tr{
  background:var(--plaka-mavi); color:#fff; font-size:8px; font-weight:500;
  display:flex; align-items:flex-end; justify-content:center;
  width:15px; padding-bottom:3px; letter-spacing:.02em;
}
.plaka .kod{
  display:flex; align-items:center; padding:0 8px;
  font-size:14px; font-weight:500; letter-spacing:.06em;
}
.plaka.bos{opacity:.3}

.sayac{
  margin-left:auto; display:flex; gap:22px; align-items:flex-end;
  font-family:var(--mono);
}
.sayac div{text-align:right}
.sayac .n{font-size:22px; font-weight:500; line-height:1; display:block}
.sayac .e{
  font-size:10px; letter-spacing:.11em; text-transform:uppercase;
  color:var(--celik);
}

/* ---------- tablo ---------- */
.sarmal{overflow:auto; max-height:calc(100vh - 250px)}
table{border-collapse:collapse; width:100%; font-size:13.5px}
thead th{
  position:sticky; top:0; z-index:5; background:var(--murekkep); color:#EDEAE3;
  text-align:left; padding:9px 12px; font-weight:500;
  font-family:var(--mono); font-size:10.5px; letter-spacing:.1em;
  text-transform:uppercase; white-space:nowrap;
}
tbody td{padding:9px 12px; border-bottom:1px solid var(--hat); vertical-align:top}
tbody tr:hover{background:#FFFDF7}
tbody tr.supheli{background:var(--uyari-zemin)}
tbody tr.supheli:hover{background:#FBEDD6}
tbody tr.supheli td:first-child{box-shadow:inset 3px 0 0 var(--uyari)}
.marka{font-weight:600; white-space:nowrap}
.tel{font-family:var(--mono); white-space:nowrap; font-size:13px}
.tel a{color:var(--vurgu); text-decoration:none}
.tel a:hover{text-decoration:underline}
.konum{white-space:nowrap}
.konum .kod{
  font-family:var(--mono); font-size:11px; color:var(--celik);
  margin-right:6px;
}
.adres{color:#3B4855; max-width:400px}
.rozet{
  display:inline-block; font-family:var(--mono); font-size:10px;
  padding:2px 6px; border-radius:3px; white-space:nowrap;
  background:var(--uyari); color:#fff;
}
/* kapak: il seçimi — plaka kartları */
.kapak{padding:34px 26px 60px; max-width:1180px; margin:0 auto}
.kapak h2{
  font-size:21px; font-weight:600; margin:0 0 4px; letter-spacing:-.01em;
}
.kapak .alt-not{
  color:var(--celik); font-size:14px; margin:0 0 24px;
}
.il-grid{
  display:grid; gap:11px;
  grid-template-columns:repeat(auto-fill,minmax(178px,1fr));
}
.il-kart{
  display:flex; align-items:center; gap:11px; text-align:left;
  border:1px solid var(--hat-koyu); background:#fff; border-radius:7px;
  padding:11px 13px; cursor:pointer; box-shadow:var(--golge);
  transition:border-color .12s, transform .12s;
}
.il-kart:hover{border-color:var(--murekkep); transform:translateY(-1px)}
.il-kart .ad{font-weight:600; font-size:14.5px; line-height:1.2}
.il-kart .sayi{
  font-family:var(--mono); font-size:11.5px; color:var(--celik); margin-top:2px;
}
.il-kart.tumu{grid-column:1/-1; background:var(--murekkep); border-color:var(--murekkep)}
.il-kart.tumu .ad,.il-kart.tumu .sayi{color:#EDEAE3}
.il-kart.tumu .plaka{border-color:#EDEAE3}

/* ilçe şeridi */
.ilce-serit{
  padding:13px 22px; border-bottom:1px solid var(--hat); background:#FCFBF9;
  display:flex; gap:8px; align-items:center; flex-wrap:wrap;
}
.geri{
  border:1px solid var(--hat-koyu); background:#fff; border-radius:5px;
  padding:6px 11px; cursor:pointer; font-size:13px; font-weight:500;
  display:inline-flex; align-items:center; gap:6px; margin-right:5px;
}
.geri:hover{border-color:var(--murekkep)}
.cip{
  border:1px solid var(--hat-koyu); background:#fff; border-radius:20px;
  padding:5px 13px; cursor:pointer; font-size:13px; white-space:nowrap;
}
.cip:hover{border-color:var(--murekkep)}
.cip.secili{background:var(--murekkep); border-color:var(--murekkep); color:#fff}

.bos-durum{padding:60px 22px; text-align:center; color:var(--celik)}
.bos-durum strong{display:block; font-size:17px; color:var(--murekkep); margin-bottom:6px}

/* ---------- alt bar ---------- */
.alt{
  position:sticky; bottom:0; background:#FCFBF9; border-top:1px solid var(--hat);
  padding:13px 22px; display:flex; gap:10px; align-items:center; z-index:30;
}
.alt .not{font-size:12.5px; color:var(--celik); margin-right:auto}
.btn{
  border:1px solid var(--hat-koyu); background:#fff; border-radius:5px;
  padding:9px 15px; cursor:pointer; font-size:13.5px; font-weight:500;
  display:inline-flex; align-items:center; gap:7px; box-shadow:var(--golge);
}
.btn:hover{border-color:var(--murekkep)}
.btn.ana{background:var(--vurgu); border-color:var(--vurgu); color:#fff}
.btn.ana:hover{background:#0C4C42}
.btn:focus-visible,select:focus-visible,input:focus-visible{
  outline:2px solid var(--vurgu); outline-offset:2px
}

/* ---------- yazdırma / PDF ---------- */
@media print{
  @page{size:A4 landscape; margin:11mm}
  .rail,.filtre,.alt,.uyari-serit button{display:none!important}
  .sarmal{max-height:none; overflow:visible}
  body{background:#fff; font-size:9.5pt}
  .yazdir-basi{display:block!important}
  thead th{background:#16202B!important; color:#fff!important;
    -webkit-print-color-adjust:exact; print-color-adjust:exact}
  tbody tr.supheli{background:#FDF3E3!important;
    -webkit-print-color-adjust:exact; print-color-adjust:exact}
  tbody tr{page-break-inside:avoid}
  .uyari-serit{display:none!important}
  .gizle-yazdir{display:none!important}
}
.yazdir-basi{display:none; padding:0 0 10px}
.yazdir-basi h2{margin:0; font-size:16pt}
.yazdir-basi p{margin:3px 0 0; font-size:9pt; color:#5F6E7C; font-family:var(--mono)}
.yazdir-basi .uyari-not{color:#A8590C; font-family:var(--display); font-size:9pt}

@media (max-width:720px){
  .sayac{width:100%; margin-left:0; justify-content:space-between}
  .adres{max-width:none}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
</style>
</head>
<body>

<header class="rail">
  <h1><span class="mark">BAYİ</span> Motosiklet Bayi Rehberi</h1>
  <div class="sag">
    <span>Veri: <b id="rTarih">—</b></span>
    <span><b id="rMarka">0</b> marka · <b id="rToplam">0</b> bayi</span>
  </div>
</header>

<div class="uyari-serit" id="uyariSerit">
  <svg width="15" height="15" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
    <path d="M8 1.5 15 14H1L8 1.5Zm0 4v4.2m0 1.6v.9" stroke="currentColor"
          stroke-width="1.4" fill="none" stroke-linecap="round"/>
  </svg>
  <div><span id="uyariMetin"></span> <button id="uyariDetay">Hangi markalar?</button></div>
</div>

<!-- KAPAK: il seçimi -->
<section class="kapak gizle-yazdir" id="kapak">
  <h2>Hangi ilin bayilerini görmek istiyorsunuz?</h2>
  <p class="alt-not">Bir ile tıklayın. Sonraki adımda ilçe seçebilirsiniz.</p>
  <div class="il-grid" id="ilGrid"></div>
</section>

<!-- İLÇE ŞERİDİ -->
<section class="ilce-serit gizle-yazdir" id="ilceSerit" style="display:none">
  <button class="geri" id="btnGeri">← İl değiştir</button>
  <span class="plaka" id="plakaRozet"><span class="tr">TR</span><span class="kod" id="plakaKod">34</span></span>
  <div id="ilceCipler" style="display:flex;gap:8px;flex-wrap:wrap"></div>
</section>

<section class="filtre gizle-yazdir" id="filtre" style="display:none">
  <div class="alan">
    <label for="fMarka">Marka</label>
    <select id="fMarka"><option value="">Tüm markalar</option></select>
  </div>
  <div class="alan">
    <label for="fArama">Ara</label>
    <input id="fArama" type="search" placeholder="Bayi adı, adres veya telefon" autocomplete="off">
  </div>
  <div class="sayac">
    <div><span class="n" id="sBayi">0</span><span class="e">Bayi</span></div>
    <div><span class="n" id="sMarka">0</span><span class="e">Marka</span></div>
    <div><span class="n" id="sIlce">0</span><span class="e">İlçe</span></div>
  </div>
</section>

<div class="yazdir-basi" id="yazdirBasi"><h2></h2><p></p><p class="uyari-not"></p></div>

<div class="sarmal" id="sarmal" style="display:none">
  <table>
    <thead><tr>
      <th>Marka</th><th>Bayi</th><th>Konum</th><th>Adres</th><th>Telefon</th>
    </tr></thead>
    <tbody id="govde"></tbody>
  </table>
  <div class="bos-durum" id="bosDurum" style="display:none">
    <strong>Bu bölgede kayıtlı bayi yok</strong>
    Filtreyi genişletin ya da ilçe seçimini kaldırın.
  </div>
</div>

<footer class="alt gizle-yazdir" id="altBar" style="display:none">
  <span class="not" id="altNot"></span>
  <button class="btn" id="btnCsv">CSV</button>
  <button class="btn" id="btnExcel">Excel indir</button>
  <button class="btn ana" id="btnPdf">PDF / Yazdır</button>
</footer>

<script>
const D = __VERI__;

const $ = s => document.querySelector(s);
const [MARKA,AD,IL,ILCE,ADRES,TEL,MAIL,WEB,DURUM] = [0,1,2,3,4,5,6,7,8];
const esc = s => String(s??"").replace(/[&<>"]/g, c =>
  ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

/* Türkçe arama: "kadikoy" yazınca "Kadıköy" bulunsun */
const kat = s => (s||"").toLocaleLowerCase("tr")
  .replace(/[çğıöşü]/g, c => ({"ç":"c","ğ":"g","ı":"i","ö":"o","ş":"s","ü":"u"}[c]))
  .replace(/[^a-z0-9]+/g," ").trim();

const supheli = r => r[DURUM] && r[DURUM] !== "Güncel";

/* ---------- durum ---------- */
let SEC = { il:"", ilce:"" };

/* ---------- kurulum ---------- */
function kur(){
  $("#rTarih").textContent = new Date(D.olusturma)
    .toLocaleString("tr-TR",{day:"2-digit",month:"2-digit",year:"numeric",
                             hour:"2-digit",minute:"2-digit"});
  $("#rToplam").textContent = D.satirlar.length.toLocaleString("tr-TR");

  const markalar = [...new Set(D.satirlar.map(r=>r[MARKA]))]
    .sort((a,b)=>a.localeCompare(b,"tr"));
  $("#rMarka").textContent = markalar.length;
  $("#fMarka").insertAdjacentHTML("beforeend",
    markalar.map(m=>`<option value="${esc(m)}">${esc(m)}</option>`).join(""));

  /* il kartları — bayi sayısına göre büyükten küçüğe */
  const sayim = {};
  D.satirlar.forEach(r => { if(r[IL]) sayim[r[IL]] = (sayim[r[IL]]||0)+1; });
  const iller = Object.keys(sayim).sort((a,b)=>
    sayim[b]-sayim[a] || a.localeCompare(b,"tr"));

  $("#ilGrid").innerHTML =
    `<button class="il-kart tumu" data-il="">
       <span class="plaka"><span class="tr">TR</span><span class="kod">TR</span></span>
       <span><span class="ad">Türkiye geneli</span>
       <span class="sayi">${D.satirlar.length} bayi · tüm iller</span></span>
     </button>` +
    iller.map(i=>`
      <button class="il-kart" data-il="${esc(i)}">
        <span class="plaka"><span class="tr">TR</span>
          <span class="kod">${D.plaka[i]||"--"}</span></span>
        <span><span class="ad">${esc(i)}</span>
        <span class="sayi">${sayim[i]} bayi</span></span>
      </button>`).join("");

  $("#ilGrid").onclick = e => {
    const b = e.target.closest(".il-kart");
    if(b) ilSec(b.dataset.il);
  };
  $("#btnGeri").onclick = kapakGoster;

  const sorunlu = (D.markalar||[]).filter(m=>m.durum && m.durum!=="basarili");
  if(sorunlu.length){
    $("#uyariSerit").classList.add("acik");
    $("#uyariMetin").textContent =
      `${sorunlu.length} markanın sitesi son taramada güncellenemedi. ` +
      `Bu markalar için en son doğrulanmış veri gösteriliyor — kayıtlar silinmedi.`;
    $("#uyariDetay").onclick = () => alert(
      "Son güncellemesi başarısız markalar:\n\n" +
      sorunlu.map(m=>`${m.ad} — ${m.etiket} (${m.adet} bayi korunuyor)`).join("\n"));
  }
}

/* ---------- ekranlar ---------- */
function kapakGoster(){
  SEC = { il:"", ilce:"" };
  $("#kapak").style.display   = "block";
  ["#ilceSerit","#filtre","#sarmal","#altBar"].forEach(x=>$(x).style.display="none");
  window.scrollTo(0,0);
}

function ilSec(il){
  SEC.il = il; SEC.ilce = "";
  $("#kapak").style.display   = "none";
  $("#ilceSerit").style.display = il ? "flex" : "none";
  $("#filtre").style.display  = "flex";
  $("#sarmal").style.display  = "block";
  $("#altBar").style.display  = "flex";

  if(il){
    $("#plakaKod").textContent = D.plaka[il] || "--";
    const ilceler = [...new Set(D.satirlar.filter(r=>r[IL]===il)
      .map(r=>r[ILCE]).filter(Boolean))].sort((a,b)=>a.localeCompare(b,"tr"));
    $("#ilceCipler").innerHTML =
      `<button class="cip secili" data-ilce="">Tüm ${esc(il)}</button>` +
      ilceler.map(x=>`<button class="cip" data-ilce="${esc(x)}">${esc(x)}</button>`).join("");
    $("#ilceCipler").onclick = e => {
      const b = e.target.closest(".cip"); if(!b) return;
      SEC.ilce = b.dataset.ilce;
      [...$("#ilceCipler").children].forEach(c=>c.classList.toggle("secili", c===b));
      ciz();
    };
  }
  ciz();
  window.scrollTo(0,0);
}

/* ---------- filtreleme ---------- */
function suz(){
  const marka=$("#fMarka").value, q=kat($("#fArama").value);
  return D.satirlar.filter(r=>
    (!SEC.il || r[IL]===SEC.il) && (!SEC.ilce || r[ILCE]===SEC.ilce) &&
    (!marka || r[MARKA]===marka) &&
    (!q || kat(r[AD]+" "+r[ADRES]+" "+r[TEL]+" "+r[ILCE]+" "+r[IL]).includes(q)));
}

function ciz(){
  const rows = suz();
  $("#govde").innerHTML = rows.map(r=>{
    const kod = D.plaka[r[IL]] || "";
    return `<tr class="${supheli(r)?"supheli":""}">
      <td class="marka">${esc(r[MARKA])}</td>
      <td>${esc(r[AD])}${supheli(r)
        ? `<br><span class="rozet">${esc(r[DURUM])}</span>` : ""}</td>
      <td class="konum"><span class="kod">${kod}</span>${esc(r[ILCE]||r[IL])}</td>
      <td class="adres">${esc(r[ADRES])}</td>
      <td class="tel">${r[TEL]
        ? `<a href="tel:${esc(r[TEL].replace(/\s/g,""))}">${esc(r[TEL])}</a>` : "—"}</td>
    </tr>`;}).join("");

  $("#bosDurum").style.display = rows.length ? "none" : "block";
  $("#sBayi").textContent  = rows.length.toLocaleString("tr-TR");
  $("#sMarka").textContent = new Set(rows.map(r=>r[MARKA])).size;
  $("#sIlce").textContent  = new Set(rows.map(r=>r[ILCE]).filter(Boolean)).size;

  const s = rows.filter(supheli).length;
  $("#altNot").textContent = s
    ? `${s} kayıt son taramada doğrulanamadı — sarı satırlar`
    : (rows.length ? "Tüm kayıtlar güncel" : "");

  const yer = [SEC.il, SEC.ilce].filter(Boolean).join(" / ") || "Türkiye geneli";
  $("#yazdirBasi").querySelector("h2").textContent =
    "Motosiklet Yetkili Bayi Listesi — "+yer;
  $("#yazdirBasi").querySelector("p").textContent =
    `${rows.length} kayıt · veri ${$("#rTarih").textContent}`;
  $("#yazdirBasi").querySelector(".uyari-not").textContent = s
    ? `Sarı zeminli ${s} kayıt son taramada doğrulanamadı; markanın sitesine `
      + `ulaşılamadığı için en son doğrulanmış veri gösteriliyor. Kayıt silinmemiştir.`
    : "";
  return rows;
}

/* ---------- dışa aktarma ---------- */
const BASLIK = ["Marka","Bayi Adı","İl","İlçe","Adres","Telefon","E-posta","Web Sitesi","Veri Durumu"];

function dosyaAdi(uzanti){
  const il=kat(SEC.il).replace(/ /g,""), ilce=kat(SEC.ilce).replace(/ /g,"");
  const yer=[il,ilce].filter(Boolean).join("-")||"tumu";
  const d=new Date(), p=n=>String(n).padStart(2,"0");
  return `bayiler-${yer}-${d.getFullYear()}${p(d.getMonth()+1)}${p(d.getDate())}.${uzanti}`;
}
function indir(blob, ad){
  const u=URL.createObjectURL(blob), a=document.createElement("a");
  a.href=u; a.download=ad; a.click(); setTimeout(()=>URL.revokeObjectURL(u),1500);
}

$("#btnCsv").onclick = () => {
  const rows=suz();
  const csv=[BASLIK, ...rows].map(r=>r.map(c=>
    `"${String(c??"").replace(/"/g,'""')}"`).join(";")).join("\r\n");
  indir(new Blob(["\uFEFF"+csv],{type:"text/csv;charset=utf-8"}), dosyaAdi("csv"));
};

$("#btnExcel").onclick = async () => {
  const b=$("#btnExcel"), eski=b.textContent;
  const rows=suz();
  b.disabled=true; b.textContent="Hazırlanıyor…";
  try{
    if(!window.XLSX){
      await new Promise((ok,hata)=>{
        const s=document.createElement("script");
        s.src="https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js";
        s.onload=ok; s.onerror=hata; document.head.appendChild(s);
      });
    }
    const ws=XLSX.utils.aoa_to_sheet([BASLIK, ...rows]);
    ws["!cols"]=[{wch:16},{wch:36},{wch:13},{wch:15},{wch:52},{wch:16},{wch:26},{wch:26},{wch:28}];
    ws["!freeze"]={xSplit:0,ySplit:1};
    const wb=XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb,ws,"Bayiler");
    XLSX.writeFile(wb, dosyaAdi("xlsx"));
  }catch(e){
    b.textContent="CSV olarak indirildi";
    $("#btnCsv").click();
    setTimeout(()=>{b.textContent=eski;},2200);
    return;
  }finally{ b.disabled=false; }
  b.textContent=eski;
};

$("#btnPdf").onclick = () => window.print();

/* ---------- bağla ---------- */
$("#fMarka").onchange = ciz;
let z; $("#fArama").oninput = () => { clearTimeout(z); z=setTimeout(ciz,140); };

kur();
kapakGoster();
</script>
</body>
</html>
"""
