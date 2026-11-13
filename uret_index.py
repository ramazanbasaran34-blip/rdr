#!/usr/bin/env python3
"""index.html üretir — MOTOSİKLET BAYİ VE SERVİS AĞI.

Tek sayfa, üç kaynak:
  1. Veritabanındaki toplanmış kayıtlar (satış / servis / ikisi rolleriyle)
  2. Excel'deki resmi sayfa linkleri — henüz taranmamış markalar için
  3. Her kayıt için markanın kendi sayfasına doğrudan giriş bağlantısı

Kullanım:  python uret_index.py [cikti_yolu]
"""

import base64
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from bayiradar.normalize import ILLER, fold, phone_display

PLAKA = {ad: f"{i+1:02d}" for i, ad in enumerate(ILLER)}
ROL_ADI = {"satis": "Satış", "servis": "Servis", "satis_servis": "Satış + Servis"}

# Veri çekilen makine uçları — insana gösterilecek bağlantı olamazlar.
MAKINE_UC = re.compile(
    r"(?:/api/|ajax[\w\-]*\.php|\.json(?:\?|$)|\.xml(?:\?|$)"
    r"|/services\.php|subeListe|wp-json)", re.I)


def makine_ucu(url: str) -> bool:
    """Bu adres tarayıcıda açılınca ham veri mi döker?"""
    return bool(url) and bool(MAKINE_UC.search(url))


def _logo(yol: str) -> str:
    """Logoyu dosyaya gömer — tek dosya kalsın, internet gerekmesin."""
    p = Path(yol)
    if not p.exists():
        return ""
    return "data:image/png;base64," + p.read_text(encoding="utf-8").strip()


def markalari_oku(yol="markalar.json"):
    return json.load(open(yol, encoding="utf-8"))


def veritabanindan_oku(db_yolu="bayiler.db"):
    if not Path(db_yolu).exists():
        return [], {}
    from bayiradar.store import db, marka_durumu, sorgula
    with db(db_yolu) as con:
        kayitlar = sorgula(con)
        durum = {m["marka"]: m for m in marka_durumu(con)}
    return kayitlar, durum


def uret(cikti="index.html", markalar_json="markalar.json", db_yolu="bayiler.db",
         logo_dizin="logolar"):
    markalar = markalari_oku(markalar_json)
    kayitlar, durum = veritabanindan_oku(db_yolu)

    # Marka → resmi sayfa adresleri (doğrudan giriş sütunu için)
    link = {m["ad"]: m for m in markalar}

    # Kaynak adresleri brands.yaml'den: markalar.json'da yalnızca bayi
    # linki var, Excel'de servis linki de görünsün diye tarifteki
    # kaynakları rolüne göre ayırıyoruz.
    try:
        import yaml
        tarif = (yaml.safe_load(Path("brands.yaml").read_text(encoding="utf-8"))
                 or {}).get("markalar", {})
    except Exception:  # noqa: BLE001
        tarif = {}
    for m in markalar:
        kaynaklar = (tarif.get(m["ad"]) or {}).get("kaynaklar") or []
        satis_u, servis_u = [], []
        for k in kaynaklar:
            u = (k.get("url") or "").split("{")[0].rstrip("?&")
            if not u:
                continue
            rol = k.get("rol") or ""
            if rol in ("satis", "satis_servis", "hepsi"):
                satis_u.append(u)
            if rol in ("servis", "satis_servis", "hepsi"):
                servis_u.append(u)
        m["satis_kaynak"] = " | ".join(dict.fromkeys(satis_u))
        m["servis_kaynak"] = " | ".join(dict.fromkeys(servis_u))
        # elle: true olan markalar taranmıyor; sayfada düzenlenebilir olsun
        m["elle"] = bool((tarif.get(m["ad"]) or {}).get("elle"))

    # İl bazlı satış adetleri (TÜİK). Bayi başına verim raporunda
    # kullanılıyor. Dosya yoksa rapor sekmesi boş görünür, sayfa çalışır.
    try:
        il_satis = json.loads(
            Path("veri/il_satis.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        il_satis = {"iller": {}, "_yillar": []}

    # Cari kod: aynı fiziksel firma (telefon+ilçe) tek kod taşır.
    # Bir firma birden çok markanın bayisi olabildiği için kod, kayıtları
    # tekilleştirip "kaç ayrı bayi var" sorusuna cevap veriyor.
    try:
        from cari_kod import firma_anahtari
        kod_esleme = json.loads(
            Path("cari_kodlar.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        firma_anahtari, kod_esleme = None, {}

    # Kompakt dizi: [marka, ad, il, ilce, adres, tel, durum, rol, giris_url, kod]
    satirlar = []
    for k in kayitlar:
        m = link.get(k["marka"], {})
        # "Marka sayfasına git" bağlantısı KULLANICIYA açılacak sayfa olmalı.
        # Veri kaynağı çoğu markada bir API ucu (api/bayiler.php, ajax.php,
        # maps.xml); o adres tarayıcıda açılınca ham JSON dökülüyordu.
        # Bu yüzden makine uçlarını eleyip markanın kendi sayfasına düşüyoruz.
        giris = ""
        for aday in (k.get("kaynak_servis"), k.get("kaynak_satis"),
                     k.get("kaynak_url"), m.get("bayi"), m.get("site")):
            if aday and not makine_ucu(aday):
                giris = aday
                break
        if not giris:
            giris = m.get("bayi") or m.get("site") or ""
        kod = ""
        if firma_anahtari:
            kod = kod_esleme.get(firma_anahtari(
                k.get("telefon", ""), k["il"], k["ilce"], k["bayi_adi"]), "")
        satirlar.append([
            k["marka"], k["bayi_adi"], k["il"], k["ilce"], k["adres"],
            phone_display(k.get("telefon", "")), k.get("veri_durumu", "Güncel"),
            k.get("rol") or "satis", giris, kod,
        ])

    say = defaultdict(lambda: {"satis": 0, "servis": 0, "ikisi": 0, "toplam": 0})
    for k in kayitlar:
        r = k.get("rol") or "satis"
        s = say[k["marka"]]
        s["toplam"] += 1
        s["ikisi" if r == "satis_servis" else r] += 1

    for m in markalar:
        s = say.get(m["ad"])
        m["sayi"] = s["toplam"] if s else None
        m["rol_sayi"] = (s or {"satis": 0, "servis": 0, "ikisi": 0})
        d = durum.get(m["ad"])
        m["tazelik"] = d["etiket"] if d else ""

    veri = {
        "olusturma": datetime.now().astimezone().isoformat(timespec="minutes"),
        "iller": sorted([{"ad": i, "plaka": PLAKA[i], "slug": fold(i).replace(" ", "")}
                         for i in ILLER], key=lambda x: fold(x["ad"])),
        # Menşe bilgisi arayüzde gösterilmiyor; sayfaya da gömülmüyor.
        "markalar": [{k: v for k, v in m.items() if k != "mensei"}
                     for m in sorted(markalar, key=lambda m: fold(m["ad"]))],
        "bayiler": satirlar,
        "rol_adi": ROL_ADI,
        "il_satis": il_satis,
    }

    html = (SABLON
            .replace("__VERI__", json.dumps(veri, ensure_ascii=False,
                                            separators=(",", ":")))
            .replace("__LOGO_SOL__", _logo(f"{logo_dizin}/kuralkan.b64"))
            .replace("__LOGO_SAG__", _logo(f"{logo_dizin}/dayanisma.b64")))
    Path(cikti).parent.mkdir(parents=True, exist_ok=True)
    Path(cikti).write_text(html, encoding="utf-8")
    return cikti, len(satirlar), sum(1 for m in markalar if m["sayi"])


SABLON = r"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<!-- Telefon tarayıcıları sayfayı agresif önbelleğe alıp güncellemeleri
     günlerce göstermiyordu (silinen bölümler ekranda kalıyordu).
     Bu üç satır tarayıcıya her açılışta sunucuya sormasını söylüyor. -->
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
<title>Motosiklet Bayi ve Servis Ağı</title>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Familjen+Grotesk:wght@400;500;600;700&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{
  --zemin:#F4F6FA; --kart:#FFFFFF; --murekkep:#122036; --celik:#5A6B84;
  --hat:#DEE4EE; --hat2:#C3CDDD;
  --satis:#D9480F;   --satis-z:#FFF0E6;   /* turuncu  */
  --servis:#0B7285;  --servis-z:#E3F6F9;  /* turkuaz  */
  --ikisi:#5F3DC4;   --ikisi-z:#EFEAFB;   /* mor      */
  --vurgu:#1864AB;   --vurgu-z:#E7F1FC;   /* mavi     */
  --uyari:#B54708;   --uyari-z:#FFF6E5;
  --mavi:#1B4B9E;
  --golge:0 1px 2px rgba(18,32,54,.05), 0 10px 28px -18px rgba(18,32,54,.35);
  --d:"Familjen Grotesk",system-ui,sans-serif; --m:"DM Mono",ui-monospace,monospace;
}
*{box-sizing:border-box} html,body{margin:0}
body{background:var(--zemin);color:var(--murekkep);font-family:var(--d);
  font-size:14px;line-height:1.45;-webkit-font-smoothing:antialiased}
button,input,select{font:inherit;color:inherit}
a{color:var(--vurgu)}

/* ================= BAŞLIK ================= */
.tepe{background:#fff;border-bottom:3px solid var(--murekkep);padding:14px 22px;
  display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:18px}
.tepe img{display:block;height:42px;width:auto}
.tepe .sag-logo{height:56px;justify-self:end}
.tepe .orta{text-align:center}
.tepe h1{margin:0;font-size:26px;font-weight:700;letter-spacing:-.02em;line-height:1.05}
.tepe .alt{margin:3px 0 0;font-family:var(--m);font-size:11px;letter-spacing:.14em;
  text-transform:uppercase;color:var(--celik)}
@media (max-width:760px){
  .tepe{grid-template-columns:auto 1fr auto;gap:10px;padding:10px 14px}
  .tepe h1{font-size:17px} .tepe img{height:28px} .tepe .sag-logo{height:36px}
  .tepe .alt{font-size:9px;letter-spacing:.1em}
}

/* ================= ŞERİT ================= */
/* Üst şerit: koyu/siyah zemin yerine kurumsal açık zemin.
   Sekmeler ortada; sağa yapışık değil. */
.serit{background:#fff;color:var(--celik);padding:5px 14px 0;display:flex;
  flex-direction:column;gap:3px;align-items:center;font-family:var(--m);
  font-size:11px;position:sticky;top:0;z-index:40;
  border-bottom:1px solid var(--hat2);box-shadow:0 2px 10px -6px rgba(16,32,56,.25)}
.serit b{color:var(--murekkep);font-weight:600}
.seritust{display:flex;gap:16px;align-items:center;flex-wrap:wrap;
  justify-content:center;text-align:center}
/* Beş sekme dar ekrana sığmıyordu (360px'de 21px taşma). Şerit kendi
   içinde yatay kaydırılabilir; sayfa yatay kaymıyor. */
.sek{display:flex;gap:6px;justify-content:center;width:100%;
  border-top:1px solid var(--hat2);padding-top:4px;
  overflow-x:auto;scrollbar-width:none;-webkit-overflow-scrolling:touch}
.sek::-webkit-scrollbar{display:none}
.sek button{flex:0 0 auto;white-space:nowrap}
.sek button{background:none;border:0;border-bottom:3px solid transparent;
  color:var(--celik);border-radius:0;padding:6px 14px 7px;cursor:pointer;
  font-size:14.5px;font-weight:600;font-family:var(--d);letter-spacing:-.01em}
.sek button:hover{color:var(--murekkep)}
.sek button.aktif{color:var(--murekkep);border-bottom-color:var(--vurgu)}

.sar{max-width:1100px;margin:0 auto;padding:20px 18px 70px}
h2{font-size:17px;font-weight:600;margin:0 0 4px}
.notm{color:var(--celik);font-size:12px;margin:0 0 8px}

.ara{width:100%;border:1px solid var(--hat2);background:#fff;border-radius:7px;
  padding:9px 12px;outline:none;margin-bottom:12px;font-size:13.5px}
.ara:focus{border-color:var(--vurgu);box-shadow:0 0 0 3px rgba(24,100,171,.15)}

/* ================= PLAKA ================= */
.plaka{display:inline-flex;align-items:stretch;height:20px;border-radius:3px;
  overflow:hidden;border:1.5px solid var(--murekkep);background:#fff;
  font-family:var(--m);line-height:1;flex:none}
.plaka .tr{background:var(--mavi);color:#fff;font-size:6px;display:flex;
  align-items:flex-end;justify-content:center;width:12px;padding-bottom:2px}
.plaka .kod{display:flex;align-items:center;padding:0 6px;font-size:12px;font-weight:500}

/* ================= ROL ROZETİ ================= */
.rol{display:inline-flex;align-items:center;gap:4px;font-family:var(--m);
  font-size:9.5px;padding:2px 7px;border-radius:11px;white-space:nowrap;
  letter-spacing:.03em;font-weight:500;border:1px solid transparent}
.rol.satis {background:var(--satis-z); color:var(--satis); border-color:#F5C9AE}
.rol.servis{background:var(--servis-z);color:var(--servis);border-color:#A9DDE6}
.rol.ikisi {background:var(--ikisi-z); color:var(--ikisi); border-color:#C9BCF0}

/* ================= LİSTE ================= */
/* overflow:hidden köşeleri kırpıyordu ama içindeki position:sticky
   başlığı da öldürüyordu (sütun başlığı kaydırınca kayboluyordu).
   Kırpma yerine ilk/son satıra köşe yarıçapı veriyoruz. */
.liste{background:var(--kart);border:1px solid var(--hat2);border-radius:9px;
  box-shadow:var(--golge)}
.liste > *:first-child{border-top-left-radius:9px;border-top-right-radius:9px}
.liste > *:last-child{border-bottom-left-radius:9px;border-bottom-right-radius:9px}
.sat{display:flex;align-items:center;gap:10px;width:100%;text-align:left;
  background:none;border:0;border-bottom:1px solid var(--hat);padding:9px 13px;
  cursor:pointer;text-decoration:none;color:inherit}
.sat:last-child{border-bottom:0}
.sat:hover{background:var(--vurgu-z)}
.sat .ad{font-weight:600;font-size:13.5px}
.sat .sag{margin-left:auto;display:flex;align-items:center;gap:10px}
.sat .men{font-family:var(--m);font-size:9.5px;color:var(--celik);
  text-transform:uppercase;letter-spacing:.07em}
.sat .alan{font-family:var(--m);font-size:10.5px;color:var(--celik)}
.sat .ok{color:var(--vurgu);font-size:14px;font-weight:600}
.sat .esl{font-size:10.5px;color:var(--uyari);font-family:var(--m)}
.sat .sayi{font-family:var(--m);font-size:13px;min-width:42px;text-align:right;font-weight:500}
.sat .sayi.yok{color:var(--hat2);font-weight:400}
.sat.eski{background:var(--uyari-z)}

/* kayıt kartı */
.kayit{padding:10px 13px 10px 26px;border-bottom:1px solid var(--hat);
  border-left:3px solid transparent;background:#FCFDFF}
.kayit:last-child{border-bottom:0}
.kayit.satis {border-left-color:var(--satis)}
.kayit.servis{border-left-color:var(--servis)}
.kayit.ikisi {border-left-color:var(--ikisi)}
.kayit .k1{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.kayit .kad{font-weight:600;font-size:13.5px}
.kayit .k2{color:var(--celik);font-size:12.5px;margin-top:2px}
.kayit .ilcerz{font-family:var(--m);font-size:10px;text-transform:uppercase;
  letter-spacing:.05em;color:var(--celik)}
.kayit .k3{display:flex;gap:14px;align-items:center;margin-top:4px;flex-wrap:wrap}
.kayit .tel{font-family:var(--m);font-size:12.5px;font-weight:500}
.kayit .tel a{text-decoration:none}
.kayit .giris{font-size:11.5px;text-decoration:none;color:var(--vurgu);
  border:1px solid var(--hat2);border-radius:5px;padding:2px 8px;background:#fff}
.kayit .giris:hover{border-color:var(--vurgu);background:var(--vurgu-z)}
.kayit.eski{background:var(--uyari-z)}

.ustcubuk{display:flex;gap:9px;align-items:center;margin-bottom:12px;flex-wrap:wrap}
.geri,.kop{border:1px solid var(--hat2);background:#fff;border-radius:6px;
  padding:6px 11px;cursor:pointer;font-size:12.5px;font-weight:500}
.geri:hover,.kop:hover{border-color:var(--murekkep)}
.ilbaslik{font-size:17px;font-weight:700}


/* --- Ortak sütun sistemi -------------------------------------------
   Başlık çubuğundaki hücreler ile satırlardaki sayı hücreleri tek bir
   genişlik değişkeninden besleniyor. Daha önce her biri ayrı ayrı
   inline min-width taşıdığı için dar ekranda sütunlar kayıyordu. */
:root{--kol:56px;--kol-gen:64px}
.baslikcubuk .k,.sat .sag .k{
  flex:0 0 var(--kol);width:var(--kol);text-align:right}
.sat .sag .k{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.baslikcubuk .k{white-space:normal;word-break:break-word;hyphens:auto;
  line-height:1.15;font-size:8.5px;letter-spacing:.01em}
.baslikcubuk .k.gen,.sat .sag .k.gen{flex-basis:var(--kol-gen);width:var(--kol-gen)}
.baslikcubuk .ilkkol,.sat .govde,.sat>.ad,.sat .plaka{
  flex:1 1 0;min-width:0;overflow:hidden}
.sat .plaka{flex:0 0 auto}
/* Ad alanı okunamayacak kadar ezilmesin */
.sat .govde,.sat>.ad{min-width:82px}
/* Sayı bloğu asla ezilmesin, ad kısalsın */
.sat .sag,.baslikcubuk .sagb{flex:0 0 auto;min-width:0}
.sat .ustsatir,.sat .ad{min-width:0;overflow:hidden;text-overflow:ellipsis;
  white-space:nowrap}
.liste,.sat,.baslikcubuk{max-width:100%;box-sizing:border-box}
.sat{overflow:hidden}
.baslikcubuk{align-items:flex-end;line-height:1.25}
.sat .sag,.baslikcubuk .sagb{margin-left:auto;display:flex;align-items:center;
  gap:8px;flex:0 0 auto}
.sat .ok{flex:0 0 12px;text-align:center}
.baslikcubuk .okbos{flex:0 0 12px}
/* .sayi kendi min-width'ini dayatıyordu; ortak sütun genişliği kazansın. */
.sat .sag .sayi.k{min-width:var(--kol);width:var(--kol);flex-basis:var(--kol)}
.sat .sag .sayi.k.gen{min-width:var(--kol-gen);width:var(--kol-gen);
  flex-basis:var(--kol-gen)}
/* Başlık ve satır aynı yatay dolguyu kullansın, sağ kenarlar çakışsın. */
.baslikcubuk,.sat{padding-left:12px;padding-right:12px;gap:8px}
.baslikcubuk .sagb,.sat .sag{gap:8px}
.cipler{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px}
/* Süzgeçler uzun listelerde ekrandan kaçmasın: sayfa kaydırılınca üstte kalsın */
.yapiskan{position:sticky;top:var(--serit-y,0);z-index:30;background:var(--kagit);
  padding:9px 0 7px;margin-bottom:8px;border-bottom:1px solid var(--hat2);
  box-shadow:0 6px 12px -10px rgba(0,0,0,.35)}
.yapiskan .ara{margin-bottom:7px}
/* Sütun başlığı kaydırırken görünür kalsın: üst şeridin ALTINA
   yapışıyor. Değişken JS ile şeridin gerçek yüksekliğinden
   hesaplanıyor (bkz. seritOlc). */
.baslikcubuk{position:sticky;z-index:20;background:#F0F4FA;
  top:calc(var(--serit-y,0px) + var(--yapiskan-y,0px))}
.rolsuz{display:flex;gap:6px;flex-wrap:wrap}
.rolsuz button{flex:1 1 auto;min-width:0;white-space:nowrap}
.rolsuz button .n{font-family:var(--m);font-size:10.5px;opacity:.75;margin-left:4px}
/* Birleşik kümeler (satış noktası = yalnız satış + satış&servis) öne çıksın */
.rolsuz button.birlesik{border-color:#C9DAF0;background:#F5F9FF;font-weight:600}
.rolsuz button.birlesik.secili{background:var(--murekkep);border-color:var(--murekkep);color:#fff}
.rolsuz button.birlesik .n{opacity:.9}
/* --- Sıralanabilir sütun başlıkları --- */
.baslikcubuk.sirali .sirakol{cursor:pointer;user-select:none;
  border-radius:4px;transition:background .12s,color .12s}
.baslikcubuk.sirali .sirakol:hover{background:var(--hat2);color:var(--murekkep)}
.baslikcubuk.sirali .sirakol.aktifsira{color:var(--murekkep);font-weight:700}
.baslikcubuk.sirali .sirakol.aktifsira::after{
  content:" ▾";font-size:9px;letter-spacing:0}
.baslikcubuk.sirali .sirakol.aktifsira[data-yon="yukari"]::after{content:" ▴"}
/* --- Elle girilen marka düzenleme --- */
.ellebar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;
  background:#FFF8E8;border:1px solid #F0D9B5;border-radius:8px;
  padding:9px 12px;margin:0 0 10px}
.ellebar .rozet{background:var(--uyari,#B7791F);color:#fff;border-radius:5px;
  padding:2px 8px;font-size:11px;font-family:var(--m);font-weight:600}
.ellebar .aciklama{font-size:12.5px;color:var(--celik);flex:1 1 220px}
.kayit.duzenlenebilir{cursor:pointer}
.kayit.duzenlenebilir:hover{background:#F7FAFF}
.kayit .dzip{font-size:10.5px;color:var(--celik);opacity:.7;margin-left:6px}
.ortu{position:fixed;inset:0;background:rgba(16,32,56,.45);z-index:60;
  display:flex;align-items:center;justify-content:center;padding:16px}
.duzenle{background:#fff;border-radius:12px;padding:18px;width:100%;
  max-width:420px;max-height:88vh;overflow:auto;
  box-shadow:0 18px 40px -12px rgba(16,32,56,.5)}
.duzenle h3{margin:0 0 12px;font-size:18px}
.duzenle label{display:block;font-size:12px;color:var(--celik);
  margin-bottom:9px;font-weight:600}
.duzenle input,.duzenle select{width:100%;box-sizing:border-box;margin-top:3px;
  padding:9px 10px;border:1px solid var(--hat2);border-radius:7px;
  font-size:14.5px;font-family:inherit;color:var(--murekkep);font-weight:400}
.dzbtn{display:flex;gap:8px;margin-top:6px}
/* Altı sayı sütunlu tablolar (Toplam servis nok. eklendikten sonra):
   dar ekranda ad alanı eziliyordu, il adları kaybolup sadece plaka
   kalıyordu. Sayı sütunlarını daraltıp ada yer açıyoruz. */
@media (max-width:620px){
  #ilListe .sag .k, #ozetIl .sag .k, #ozetMarka .sag .k,
  #ozetIlce .sag .k, #tumListe .sag .k,
  .baslikcubuk[data-tablo="ilListe"] .k,
  .baslikcubuk[data-tablo="ozetIl"] .k,
  .baslikcubuk[data-tablo="ozetMarka"] .k,
  .baslikcubuk[data-tablo="ozetIlce"] .k,
  .baslikcubuk[data-tablo="tumListe"] .k{min-width:30px;padding:0 2px;font-size:12px}
  .baslikcubuk[data-tablo="ilListe"] .k,
  .baslikcubuk[data-tablo="ozetIl"] .k,
  .baslikcubuk[data-tablo="ozetMarka"] .k,
  .baslikcubuk[data-tablo="ozetIlce"] .k,
  .baslikcubuk[data-tablo="tumListe"] .k{font-size:8px;letter-spacing:0;
    /* "Sadece" kelimesi ortadan bölünüp "Sadec e" görünüyordu */
    overflow-wrap:normal;word-break:keep-all;hyphens:none;line-height:1.2}
  #ilListe .sag, #ozetIl .sag, #ozetMarka .sag, #ozetIlce .sag, #tumListe .sag,
  .baslikcubuk[data-tablo="ilListe"] .sagb,
  .baslikcubuk[data-tablo="ozetIl"] .sagb,
  .baslikcubuk[data-tablo="ozetMarka"] .sagb,
  .baslikcubuk[data-tablo="ozetIlce"] .sagb,
  .baslikcubuk[data-tablo="tumListe"] .sagb{gap:3px}
  /* Plaka rozeti yer kaplıyor; sıra numarası zaten var */
  #ilListe .men{display:none}
  #ilListe .sat, #ozetIl .sat, #ozetMarka .sat,
  #ozetIlce .sat, #tumListe .sat{gap:5px;padding-left:7px;padding-right:7px}
  #ilListe .sirano, #ozetIl .sirano, #ozetMarka .sirano,
  #ozetIlce .sirano, #tumListe .sirano{flex-basis:16px;font-size:9.5px}
}

/* Verim tablosunda 7 sayı sütunu var (3 yıl × satış+verim, artı nokta).
   Dar ekranda sığması için bu tabloya özel daraltma. */
#verimListe .sag .k,
.baslikcubuk[data-tablo="verimListe"] .k{min-width:34px;padding:0 2px}
#verimListe .sag,
.baslikcubuk[data-tablo="verimListe"] .sagb{gap:3px}
#verimListe .govde,#verimListe .sat>.ad{min-width:58px}
@media (max-width:620px){
  #verimListe .sag .k,
  .baslikcubuk[data-tablo="verimListe"] .k{min-width:27px;font-size:11px;padding:0 1px}
  .baslikcubuk[data-tablo="verimListe"] .k{font-size:8px;letter-spacing:0}
  #verimListe .govde,#verimListe .sat>.ad{min-width:42px}
  #verimListe .men{display:none}
  /* Ok işareti ve sıra numarası yer kaplıyor; 7 sütun için gerekli */
  #verimListe .ok,.baslikcubuk[data-tablo="verimListe"] .okbos{display:none}
  #verimListe .sirano{flex-basis:16px;font-size:9px}
  #verimListe .sat{padding-left:6px;padding-right:6px;gap:5px}
}

#anaSayfa{display:inline-flex;align-items:center;cursor:pointer;
  border-radius:6px;transition:opacity .12s;
  /* Dokunma hedefi küçük kalmasın */
  padding:2px;min-height:40px}
.tepe .orta h1{cursor:pointer}
/* Şerit yapışkan olduğu için bu düğme sayfa kaydırılsa da hep görünür.
   Üstteki logo yukarı kayınca ana sayfaya dönüş yolu kalmıyordu. */
#anaSayfaKisa{background:none;border:0;padding:2px 6px;cursor:pointer;
  color:var(--celik);display:inline-flex;align-items:center;
  border-radius:5px;line-height:0}
#anaSayfaKisa:hover{background:var(--hat2);color:var(--murekkep)}
#anaSayfaKisa:active{opacity:.6}
.seritust{display:flex;align-items:center;gap:7px;justify-content:center}
.tepe .orta h1:active{opacity:.6}
#anaSayfa:hover{opacity:.75}
#anaSayfa:active{opacity:.55}

/* İlçe seçim kutusu — eskiden çipler yan yana dizilip ekranın
   yarısını kaplıyordu. Tek kutu, çoklu seçim, arama var. */
.ilcekutu{position:relative;margin:0 0 8px}
#ilceAc{width:100%;display:flex;align-items:center;justify-content:space-between;
  gap:8px;background:#fff;border:1px solid var(--hat2);border-radius:7px;
  padding:9px 12px;font-size:14px;font-family:inherit;color:var(--murekkep);
  cursor:pointer;box-shadow:var(--golge)}
#ilceAc .ok2{color:var(--celik);font-size:12px}
#ilceAc[aria-expanded="true"]{border-color:var(--murekkep)}
/* z-index 35 iken alt özet çubuğu (45) menünün "Kapat" düğmesini
   örtüyordu; telefonda düğmeye hiç ulaşılamıyordu. */
/* KRİTİK: [hidden] öğeye display:none verir, ama aşağıdaki display:flex
   kuralı onu ezip paneli "kapalıyken" bile ekranda tutuyordu. Panel
   görünmez oluyor ama tam ekranı kaplayıp dokunuşları yutuyordu —
   "Tamam'a bastım, liste gelmedi" sorununun sebebi buydu.
   Bu kural her zaman en sonda kalmalı. */
.ilcemenu[hidden]{display:none !important}
.ilcemenu{position:absolute;z-index:90;left:0;right:0;top:calc(100% + 4px);
  background:#fff;border:1px solid var(--hat2);border-radius:9px;
  box-shadow:0 12px 28px -12px rgba(16,32,56,.45);padding:8px}
.ilcemenu .ara{margin-bottom:6px}
#ilceListesi{max-height:46vh;overflow-y:auto}
.ilcesatir{display:flex;align-items:center;gap:8px;padding:7px 6px;
  border-radius:6px;cursor:pointer;font-size:14px}
.ilcesatir:hover{background:var(--hat2)}
.ilcesatir input{width:16px;height:16px;flex:0 0 auto;accent-color:var(--murekkep)}
/* Üst şerit: başlık solda, Temizle/Tamam sağda. Kaydırınca da kalsın. */
.ilceust{display:flex;align-items:center;gap:6px;
  border-bottom:1px solid var(--hat2);padding-bottom:8px;margin-bottom:8px;
  position:sticky;top:0;background:#fff;z-index:2}
.ilcebaslik{flex:1 1 auto;font-weight:700;font-size:14px;color:var(--murekkep)}
.ilceust .btn{padding:7px 13px;font-size:13px;flex:0 0 auto}

@media (max-width:620px){
  /* TELEFONDA TAM EKRAN.
     Önce sayfa içinde açılan panel denendi: alt özet çubuğu düğmeleri
     örtüyordu, sonra katman bağlamı sorunu çıktı, sonra da "Tamam"
     gerçek cihazda kapatmıyordu. Tam ekran modal bu sınıfın tamamını
     ortadan kaldırıyor — sayfadaki düzenleme penceresi de böyle
     çalışıyor ve sorunsuz. */
  .ilcemenu{position:fixed;inset:0;border-radius:0;padding:10px 12px;
    max-height:none;display:flex;flex-direction:column;z-index:90}
  #ilceListesi{max-height:none;flex:1 1 auto;min-height:0;
    -webkit-overflow-scrolling:touch}
  /* Satırlar daraltıldı: ekranda iki kat fazla ilçe görünüyor */
  .ilcesatir{padding:8px 6px;font-size:14.5px;gap:10px}
  .ilcesatir input{width:19px;height:19px}
  .ilcemenu .ara{padding:8px 10px;font-size:14px;margin-bottom:6px}
  .ilceust{padding-bottom:9px;margin-bottom:8px}
  .ilceust .btn{padding:9px 15px;font-size:14.5px}
  .ilcebaslik{font-size:15px}
  body.ilcepanel{overflow:hidden}
}
.ilceortu{display:none}

/* Verim ekranı seçim düğmeleri.
   DİKKAT: .sirala kullanılamaz — o sınıf mobilde gizli. */
.secimler{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 8px}
#verimSecim .btn.secili{background:var(--murekkep);color:#fff;
  border-color:var(--murekkep);font-weight:600}

/* --- "Bu bayi ayrıca şu markaların da bayisi" satırı --- */
.k4{display:flex;flex-wrap:wrap;gap:4px;align-items:center;margin:5px 0 0}
.k4 .dmet{font-size:11px;color:var(--celik);margin-right:2px}
.dmarka{background:var(--hat2);border:1px solid transparent;color:var(--murekkep);
  border-radius:5px;padding:2px 7px;font-size:11px;font-weight:600;
  cursor:pointer;font-family:inherit;line-height:1.5}
.dmarka:hover{background:var(--murekkep);color:#fff}
/* Şu an bakılan marka — listede ilk ve vurgulu */
.dmarka.bumarka{background:var(--murekkep);color:#fff;border-color:var(--murekkep)}
@media (max-width:620px){
  .k4 .dmet{font-size:10px}
  .dmarka{font-size:10px;padding:2px 5px}
  /* Marka listesi uzun olabiliyor (14 markaya kadar); kart genişliğini
     zorlamasın diye satır sarması serbest, kelime bölünmesi kapalı. */
  .k4{flex-wrap:wrap;max-width:100%}
  .dmarka{max-width:100%;overflow-wrap:anywhere}
}
.k4{min-width:0}
.kayit{min-width:0;overflow:hidden}

/* --- Cari kod rozeti --- */
.carikod{font-family:var(--m);font-size:10.5px;font-weight:700;
  background:var(--murekkep);color:#fff;border-radius:4px;
  padding:2px 6px;margin-right:7px;letter-spacing:.06em}

/* --- Alt özet çubuğu ---
   Kayıtlar marka × nokta olarak tutuluyor; bir firma 14 markanın
   bayisi olabiliyor. Buradaki sayılar CARİ KODA göre tekilleştirilmiş,
   yani her bayi yalnızca bir kez sayılıyor. */
.altozet{position:fixed;left:0;right:0;bottom:0;z-index:45;
  background:#fff;border-top:2px solid var(--murekkep);
  box-shadow:0 -6px 18px -10px rgba(16,32,56,.4);
  display:flex;flex-direction:column;gap:6px;padding:11px 12px 12px;
  font-family:var(--m)}
.altozet .aoust{display:flex;gap:8px;align-items:baseline;flex-wrap:wrap}
.altozet .baslik{font-weight:700;font-size:15px;color:var(--murekkep);
  white-space:nowrap;font-family:var(--d);flex:0 0 auto}
.altozet .aonot{font-family:var(--d);font-size:11.5px;color:var(--celik);
  line-height:1.3;flex:1 1 180px}
.altozet .satir{display:flex;align-items:center;gap:10px;overflow-x:auto}
/* Üstteki açıklama */
.acikbilgi{font-size:12.5px;line-height:1.45;color:var(--celik);
  background:#F5F9FF;border:1px solid var(--hat2);border-left:3px solid var(--murekkep);
  border-radius:7px;padding:9px 12px;margin:0 0 11px}
.acikbilgi b{color:var(--murekkep)}
.altozet .kutu{display:flex;flex-direction:column;align-items:center;
  line-height:1.2;flex:0 0 auto;padding:2px 6px;border-left:1px solid var(--hat2)}
.altozet .kutu b{font-size:24px;color:var(--murekkep);
  font-variant-numeric:tabular-nums;letter-spacing:-.02em}
/* Etiketler iki satır: kısaltma yerine tam kelime yazıyoruz, yazıyı
   küçültüp iki mısraya bölerek sığdırıyoruz. */
.altozet .kutu i{font-style:normal;font-size:10px;color:var(--celik);
  white-space:nowrap;letter-spacing:0;margin-top:2px;line-height:1.2;
  text-align:center;font-family:var(--d)}
.altozet .kutu.vurgu b{color:var(--satis)}
.altozet .kutu.vurgu{background:var(--satis-z);border-radius:7px;padding:4px 8px}
.altozet .kutu.toplamf{background:var(--murekkep);border-radius:7px;
  border-left:0;padding:4px 10px}
.altozet .kutu.toplamf b{color:#fff}
.altozet .kutu.toplamf i{color:#C9DAF0}
.sar{padding-bottom:var(--altozet-y,150px)}
@media (max-width:620px){
  /* Dikeyde büyüt, yatayda daralt: rakamlar okunaklı olsun */
  .sek{gap:2px;justify-content:flex-start}
  .sek button{padding:6px 9px 7px;font-size:13.5px}
  .altozet{gap:6px;padding:10px 6px 12px}
  .altozet .baslik{font-size:13px}
  .altozet .satir{gap:4px}
  .altozet .kutu{padding:2px 4px}
  .altozet .kutu b{font-size:23px}
  .altozet .kutu i{font-size:8.5px}
  .altozet .aonot{font-size:10.5px}
  /* Şeritteki kayıt bazlı özet dar ekranda iki satır kaplıyordu;
     aynı bilgi alt çubukta firma bazlı ve daha doğru veriliyor. */
  .genisgor{display:none}
  .sar{padding-bottom:var(--altozet-y,160px)}
  .acikbilgi{font-size:11.5px;padding:8px 10px}
  .altozet .aonot{font-size:9.5px}
}
/* --- Sıra numarası --- */
.sirano{flex:0 0 26px;text-align:right;font-family:var(--m);font-size:11px;
  color:var(--celik);opacity:.75;font-variant-numeric:tabular-nums}
.sirano.kno{flex:0 0 auto;margin-right:6px;background:var(--hat2);
  border-radius:4px;padding:1px 5px;font-size:10.5px}
@media (max-width:620px){ .sirano{flex-basis:20px;font-size:10px} }
.sayi.vurgu{font-weight:700;color:var(--satis);
  background:var(--satis-z);border-radius:5px;padding:1px 5px}
/* Toplam servis noktası — satışın turuncusundan ayrılsın diye turkuaz */
.sayi.vurguserv{font-weight:700;color:var(--servis);
  background:var(--servis-z);border-radius:5px;padding:1px 5px}
.kutu.toplam{border-color:var(--hat);background:#fbfcfe}
.kutu.toplam .n{font-weight:700}
@media (max-width:620px){
  /* Telefonda dikey: sütunlar dar, satır adı kırpılıyor.
     Böylece başlık ile veri hücreleri aynı hizada kalıyor. */
  :root{--kol:36px;--kol-gen:44px}
  .baslikcubuk,.sat{gap:6px}
  .baslikcubuk .sagb,.sat .sag{gap:6px}
  .sat .govde,.sat>.ad{min-width:92px}
  .bslk{font-size:18px}
  h2{font-size:21px}
  .kutu .n{font-size:23px}
  /* Telefonda üst alan ekranın yarısını yiyordu; liste için yer açıyoruz. */
  .sar{padding-top:9px;padding-left:10px;padding-right:10px}
  h2{font-size:17px;margin:0 0 3px}
  .notm{font-size:11px;margin:0 0 6px}
  .sirala{gap:4px;margin-bottom:5px}
  .sirala .et{display:none}          /* "SIRALA" etiketi yer kaplıyor */
  .altbar{gap:5px;margin:0 0 6px}
  .btn{padding:5px 9px;font-size:12px}
  .yapiskan{padding:5px 0 4px;margin-bottom:5px}
  .ara{padding:7px 10px;font-size:13.5px}
  .sat{padding-top:11px;padding-bottom:11px}
  .sat .ad{font-size:14.5px;overflow:hidden;text-overflow:ellipsis;
    white-space:nowrap;display:block}
  .sat .sayi{font-size:13.5px}
  .baslikcubuk{font-size:9px}
  .liste{border-radius:8px}
  .sek button{font-size:14px;padding:8px 12px 9px;flex:1 1 0;text-align:center}
  .serit{padding:8px 10px 0;font-size:11.5px}
  .kutular{grid-template-columns:repeat(auto-fit,minmax(132px,1fr));gap:9px}
}
@media (max-width:380px){
  :root{--kol:33px;--kol-gen:41px}
  .sat .ad{font-size:13.5px}
  .sat .govde,.sat>.ad{min-width:68px}
  .baslikcubuk{font-size:8.5px}
}
.cip{border:1px solid var(--hat2);background:#fff;border-radius:16px;padding:4px 12px;
  cursor:pointer;font-size:12.5px}
.cip:hover{border-color:var(--murekkep)}
.cip.secili{background:var(--murekkep);border-color:var(--murekkep);color:#fff}

/* rol süzgeci */
/* Sıralama artık sütun başlıklarına tıklanarak yapılıyor; bu düğme
   grubu yalnızca geniş ekranda yedek olarak duruyor. */
.sirala{display:flex;gap:5px;align-items:center;flex-wrap:wrap;margin-bottom:7px}
@media (max-width:620px){ .sirala{display:none} }
.sirala .et{font-family:var(--m);font-size:10px;letter-spacing:.09em;
  text-transform:uppercase;color:var(--celik);margin-right:2px}
.sirala button{border:1px solid var(--hat2);background:#fff;border-radius:6px;
  padding:5px 11px;cursor:pointer;font-size:12.5px}
.sirala button:hover{border-color:var(--murekkep)}
.sirala button.secili{background:var(--murekkep);border-color:var(--murekkep);color:#fff}
.rolsuz{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px}
.rolsuz button{border:1.5px solid var(--hat2);background:#fff;border-radius:7px;
  padding:6px 13px;cursor:pointer;font-size:12.5px;font-weight:500;
  display:inline-flex;align-items:center;gap:6px}
.rolsuz button .n{font-family:var(--m);font-size:11px;opacity:.75}
.rolsuz button:hover{border-color:var(--murekkep)}
.rolsuz button.secili{color:#fff}
.rolsuz button[data-r="tum"].secili   {background:var(--murekkep);border-color:var(--murekkep)}
.rolsuz button[data-r="satis"].secili {background:var(--satis); border-color:var(--satis)}
.rolsuz button[data-r="servis"].secili{background:var(--servis);border-color:var(--servis)}
.rolsuz button[data-r="ikisi"].secili {background:var(--ikisi); border-color:var(--ikisi)}

.bilgi{background:var(--uyari-z);border:1px solid #F0D9B5;color:var(--uyari);
  border-radius:8px;padding:10px 13px;font-size:12.5px;margin-bottom:14px}
.bos{padding:30px;text-align:center;color:var(--celik);font-size:13px}
.baslikcubuk{display:flex;gap:10px;padding:7px 13px;font-family:var(--d);font-size:11px;
  letter-spacing:0;color:var(--celik);font-weight:600;
  background:#F0F4FA;border-bottom:1px solid var(--hat2)}
.baslikcubuk .sagb{margin-left:auto}

.kutular{display:grid;gap:11px;grid-template-columns:repeat(auto-fit,minmax(148px,1fr));
  margin-bottom:16px}
/* çubuk grafik */
.cubuk{position:relative;display:block;height:5px;border-radius:3px;background:var(--hat);
  margin-top:5px;overflow:hidden}
.cubuk i{position:absolute;left:0;top:0;bottom:0;border-radius:3px;display:block}
.cubuk i.s{background:var(--satis)} .cubuk i.v{background:var(--servis)}
.sat .govde{flex:1;min-width:0}
.sat .ustsatir{display:flex;align-items:center;gap:9px}
/* hızlı arama */
.hizli{display:flex;gap:8px;align-items:center;margin-bottom:14px;flex-wrap:wrap}
.hizli input{flex:1;min-width:220px;border:1px solid var(--hat2);background:#fff;
  border-radius:7px;padding:9px 12px;outline:none;font-size:13.5px}
.hizli input:focus{border-color:var(--vurgu);box-shadow:0 0 0 3px rgba(24,100,171,.15)}
.oneri{background:#fff;border:1px solid var(--hat2);border-radius:8px;margin-top:-8px;
  margin-bottom:14px;max-height:280px;overflow:auto;box-shadow:var(--golge)}
.oneri:empty{display:none}
.kapsam{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:var(--celik);
  font-family:var(--m);margin-bottom:14px}
.kapsam b{color:var(--murekkep);font-weight:500}
.kutu{background:var(--kart);border:1px solid var(--hat2);border-radius:9px;
  padding:13px 15px;box-shadow:var(--golge)}
.kutu .n{font-family:var(--m);font-size:26px;font-weight:500;line-height:1;display:block}
/* Etiketler daktilo yazıyla ve zorla BÜYÜK HARFE çevriliyordu; okunması
   zordu ve Türkçe imlaya aykırıydı. Normal yazı tipine alındı, harf
   dönüşümü kaldırıldı; metinler artık büyük harfle başlayıp devam ediyor. */
.kutu .e{font-size:12px;font-family:var(--d);letter-spacing:0;
  color:var(--celik);margin-top:5px;display:block;line-height:1.35}
.kutu.satis  .n{color:var(--satis)}
.kutu.servis .n{color:var(--servis)}
.kutu.ikisi  .n{color:var(--ikisi)}
.ikili{display:grid;gap:16px;grid-template-columns:1fr 1fr}
/* Grid ve flex çocukları varsayılan min-width:auto ile içerikten küçülmez;
   telefonda sütunları dışarı taşıran şey buydu. */
.ikili>*{min-width:0}
@media (max-width:820px){.ikili{grid-template-columns:1fr}}
.bslk{font-size:19px;font-weight:700;margin:0 0 10px;display:flex;gap:10px;
  align-items:baseline;justify-content:center;text-align:center;letter-spacing:-.01em}
.bslk span{font-family:var(--m);font-size:12.5px;color:var(--celik);font-weight:500}
h2{font-size:19px;font-weight:700;text-align:center;letter-spacing:-.01em;
  margin:0 0 4px}
.altbar{display:flex;gap:6px;margin:0 0 8px;flex-wrap:wrap}
.btn{border:1px solid var(--hat2);background:#fff;border-radius:7px;padding:6px 11px;
  cursor:pointer;font-size:12.5px;font-weight:500;box-shadow:var(--golge)}
.btn:hover{border-color:var(--murekkep)}
.btn.ana{background:var(--vurgu);border-color:var(--vurgu);color:#fff}
.btn.ana:hover{background:#14568F}
.btn:disabled{opacity:.6;cursor:default}

/* ================= YAZDIRMA: A4 DİKEY ================= */
@media print{
  @page{size:A4 portrait;margin:12mm 10mm}
  .serit,.ara,.cipler,.altbar,.rolsuz,.geri,.kop,.sek,.bilgi,.bos{display:none!important}
  body{background:#fff;font-size:9pt;color:#000}
  .sar{max-width:none;padding:0}
  .tepe{border-bottom:2px solid #000;padding:0 0 6pt;margin-bottom:8pt;
    -webkit-print-color-adjust:exact;print-color-adjust:exact}
  .tepe h1{font-size:15pt}
  .tepe img{height:30px} .tepe .sag-logo{height:38px}
  .liste{border:0;box-shadow:none;border-radius:0}
  .baslikcubuk{background:#122036!important;color:#fff!important;font-size:7.5pt;
    -webkit-print-color-adjust:exact;print-color-adjust:exact}
  .kayit{page-break-inside:avoid;padding:5pt 6pt 5pt 10pt;font-size:8.5pt}
  .kayit .kad{font-size:9pt}
  .kayit .giris{display:none}
  .sat{page-break-inside:avoid}
  .rol{-webkit-print-color-adjust:exact;print-color-adjust:exact;font-size:7pt}
  .yazdir-bilgi{display:block!important}
}
.yazdir-bilgi{display:none;font-family:var(--m);font-size:8pt;color:#444;
  margin:0 0 8pt;text-align:center}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
</style>
</head>
<body>

<header class="tepe">
  <a href="#" id="anaSayfa" title="Ana sayfaya dön"><img src="__LOGO_SOL__" alt="Kuralkan"></a>
  <div class="orta">
    <h1>Motosiklet Bayi ve Servis Ağı</h1>

  </div>
  <img class="sag-logo" src="__LOGO_SAG__" alt="Dayanışma">
</header>

<div class="yazdir-bilgi" id="yazdirBilgi"></div>

<div class="serit">
  <div class="seritust">
    <button id="anaSayfaKisa" title="Ana sayfa" aria-label="Ana sayfa">
      <svg viewBox="0 0 24 24" width="15" height="15" fill="none"
           stroke="currentColor" stroke-width="2" stroke-linecap="round"
           stroke-linejoin="round"><path d="M3 10.5 12 3l9 7.5"/>
        <path d="M5 9.5V21h14V9.5"/></svg>
    </button>
    <span>Veri: <b id="veriTarih">—</b></span>
  </div>
  <nav class="sek">
    <button id="sekOzet">Özet</button>
    <button id="sekIl" class="aktif">İller</button>
    <button id="sekMarka">Markalar</button>
    <button id="sekBayi">Bayiler</button>
    <button id="sekServis">Servisler</button>
    <button id="sekVerim">Satışa Oran</button>
  </nav>
</div>

<div class="sar" id="sar">

  <section id="vOzet" style="display:none">
    <h2>Genel Durum</h2>
    <p class="notm">Satırlara tıklayarak ayrıntıya inebilirsiniz.</p>
    <div class="hizli">
      <input id="hizliAra" type="search"
             placeholder="İl, ilçe, marka veya bayi adı ara — doğrudan git">
    </div>
    <div class="oneri" id="oneriKutu"></div>
    <p class="acikbilgi ust">
      Bayi birden çok marka ile çalışsa bile <b>1 işyeri 1 adet</b> sayıldı;
      Şubeler ayrı adresteyse ayrı işyeri olarak kabul edildi.
    </p>
    <div class="kutular" id="kutular"></div>
    <div class="kapsam" id="kapsam"></div>
    <div class="altbar">
      <button class="btn ana" id="btnOzetTumXls">Tümünü Excel indir</button>
      <button class="btn" id="btnOzetYaz2">Yazdır / PDF</button>
    </div>
    <div class="ikili">
      <div>
        <h3 class="bslk">İllere göre <span id="ilAdet"></span></h3>
        <div class="liste">
          <div class="baslikcubuk sirali" data-tablo="ozetIl"><span class="ilkkol sirakol" data-s="ad">İl</span><span class="sagb"><span data-s="yalnizSatis" class="sirakol k">Sadece<br>bayi</span><span data-s="yalnizServis" class="sirakol k">Sadece<br>servis</span><span data-s="ikisi" class="sirakol k">Bayi ve<br>servis</span><span data-s="satisNoktasi" class="sirakol k gen" style="color:var(--satis)">Toplam<br>satış nok.</span><span data-s="servisNoktasi" class="sirakol k gen" style="color:var(--servis)">Toplam<br>servis nok.</span><span data-s="toplam" class="sirakol k">Toplam<br>nokta</span><span class="okbos"></span></span></div>
          <div id="ozetIl"></div>
        </div>
      </div>
      <div>
        <h3 class="bslk">Markalara göre <span id="mrkAdet"></span></h3>
        <div class="liste">
          <div class="baslikcubuk sirali" data-tablo="ozetMarka"><span class="ilkkol sirakol" data-s="ad">Marka</span><span class="sagb"><span data-s="yalnizSatis" class="sirakol k">Sadece<br>bayi</span><span data-s="yalnizServis" class="sirakol k">Sadece<br>servis</span><span data-s="ikisi" class="sirakol k">Bayi ve<br>servis</span><span data-s="satisNoktasi" class="sirakol k gen" style="color:var(--satis)">Toplam<br>satış nok.</span><span data-s="servisNoktasi" class="sirakol k gen" style="color:var(--servis)">Toplam<br>servis nok.</span><span data-s="toplam" class="sirakol k">Toplam<br>nokta</span><span class="okbos"></span></span></div>
          <div id="ozetMarka"></div>
        </div>
      </div>
    </div>
    <div class="ilceortu" id="ilceOrtu"></div>
    <h3 class="bslk" style="margin-top:20px">İlçe dağılımı <span id="ilceAdet"></span></h3>
    <div class="liste">
      <div class="baslikcubuk sirali" data-tablo="ozetIlce"><span class="ilkkol sirakol" data-s="ad">İl / İlçe</span><span class="sagb"><span data-s="yalnizSatis" class="sirakol k">Sadece<br>bayi</span><span data-s="yalnizServis" class="sirakol k">Sadece<br>servis</span><span data-s="ikisi" class="sirakol k">Bayi ve<br>servis</span><span data-s="satisNoktasi" class="sirakol k gen" style="color:var(--satis)">Toplam<br>satış nok.</span><span data-s="servisNoktasi" class="sirakol k gen" style="color:var(--servis)">Toplam<br>servis nok.</span><span data-s="marka" class="sirakol k">Marka</span><span data-s="toplam" class="sirakol k">Toplam<br>nokta</span><span class="okbos"></span></span></div>
      <div id="ozetIlce"></div>
    </div>
  </section>

  <section id="vIl">
    <h2>İl seçin</h2>
    <p class="notm">İl seçtikten sonra ilçe, marka ve satış/servis süzgeçlerini kullanabilirsiniz.</p>
    <div class="altbar" id="ilUstbar" style="display:none">
      <button class="btn ana" id="btnTumIlXls">Tüm illeri Excel indir</button>
    </div>
    <div class="yapiskan">
      <input class="ara" id="araIl" type="search" placeholder="İl adı veya plaka kodu" autocomplete="off">
    </div>
    <div class="baslikcubuk sirali" data-tablo="ilListe"><span class="ilkkol sirakol" data-s="ad">#  İl</span><span class="sagb"><span data-s="yalnizSatis" class="sirakol k">Sadece<br>bayi</span><span data-s="yalnizServis" class="sirakol k">Sadece<br>servis</span><span data-s="ikisi" class="sirakol k">Bayi ve<br>servis</span><span data-s="satisNoktasi" class="sirakol k gen" style="color:var(--satis)">Toplam<br>satış nok.</span><span data-s="servisNoktasi" class="sirakol k gen" style="color:var(--servis)">Toplam<br>servis nok.</span><span data-s="toplam" class="sirakol k">Toplam<br>nokta</span><span class="okbos"></span></span></div>
    <div class="liste" id="ilListe"></div>
    <div class="bos" id="ilBos" style="display:none">Bu isimde il yok.</div>
  </section>

  <section id="vMarkalar" style="display:none">
    <div class="ustcubuk">
      <button class="geri" id="geri">← İller</button>
      <span class="plaka"><span class="tr">TR</span><span class="kod" id="kod">34</span></span>
      <span class="ilbaslik" id="ilAdi"></span>
      <button class="kop" id="kopyala">İl adını kopyala</button>
    </div>
    <div class="yapiskan">
      <input class="ara" id="araMarka" type="search" placeholder="Marka, bayi adı veya adres ara" autocomplete="off">
      <!-- İlçeler eskiden yan yana çip olarak diziliyordu; büyük illerde
           ekranın yarısını kaplıyordu. Artık tek kutu, çoklu seçim. -->
      <div class="ilcekutu">
        <button id="ilceAc" type="button" aria-expanded="false">
          <span id="ilceOzet">Tüm ilçeler</span>
          <span class="ok2">▾</span>
        </button>
        <div class="ilcemenu" id="ilceMenu" hidden>
          <!-- Düğmeler ÜSTTE: altta olduklarında alt özet çubuğu onları
               örtüyordu ve telefonda hiç ulaşılamıyordu. -->
          <div class="ilceust">
            <span class="ilcebaslik">İlçe seç</span>
            <button class="btn" id="ilceTemizle">Temizle</button>
            <button class="btn ana" id="ilceUygula">Tamam</button>
          </div>
          <input class="ara" id="ilceAra" type="search" placeholder="İlçe ara" autocomplete="off">
          <div id="ilceListesi"></div>
        </div>
      </div>
      <div class="rolsuz" id="rolSuzgec"></div>
    </div>
    <div class="altbar" id="ustbar" style="display:none">
      <button class="btn ana" id="btnXls">Excel indir</button>
      <button class="btn" id="btnHtml">HTML kaydet</button>
      <button class="btn" id="btnCsv">CSV</button>
      <button class="btn" id="btnYaz">Yazdır / PDF</button>
    </div>
    <div class="liste" id="markaListe"></div>
    <div class="bos" id="markaBos" style="display:none">Sonuç yok.</div>
  </section>

  <section id="vMarkaDetay" style="display:none">
    <div class="ustcubuk">
      <button class="geri" id="geriMarka">← Markalar</button>
      <span class="ilbaslik" id="mdAd"></span>
    </div>
    <p class="notm" id="mdOzet"></p>
    <div class="ellebar" id="mdElleBar" style="display:none">
      <span class="rozet">Elle girilen veri</span>
      <span class="aciklama">Bu marka taranmıyor. Kayda dokunup bilgileri
        düzeltebilirsin; değişiklikler bu cihazda saklanır.</span>
      <button class="btn" id="btnElleDisa">Düzeltmeleri indir (JSON)</button>
      <button class="btn" id="btnElleSifirla">Düzeltmeleri sıfırla</button>
    </div>
    <div class="yapiskan">
      <div class="rolsuz" id="mdRolSuzgec"></div>
    </div>
    <div class="altbar">
      <button class="btn ana" id="btnMarkaXls">Excel indir</button>
      <button class="btn" id="btnMarkaHtml">HTML kaydet</button>
      <button class="btn" id="btnMarkaYaz">Yazdır / PDF</button>
    </div>
    <div class="liste" id="mdListe"></div>
  </section>

  <!-- VERİM EKRANI: il bazında satış adedi ve nokta başına verim.
       Satış adetleri TÜİK; bayi/servis sayıları bizim veritabanımızdan
       (firma bazlı, tekilleştirilmiş). -->
  <section id="vVerim" style="display:none">
    <h2 id="verimBaslik">Bayi başına satış</h2>
    <p class="notm" id="verimNot"></p>
    <div class="secimler" id="verimSecim">
      <button class="btn secili" data-v="satis">Bayi başına</button>
      <button class="btn" data-v="servis">Servis başına</button>
    </div>
    <div class="altbar">
      <button class="btn ana" id="btnVerimXls">Excel indir</button>
    </div>
    <div class="yapiskan">
      <input class="ara" id="araVerim" type="search" placeholder="İl ara" autocomplete="off">
    </div>
    <div class="baslikcubuk sirali" data-tablo="verimListe"><span class="ilkkol sirakol" data-s="ad">#  İl</span><span class="sagb"><span data-s="nokta" class="sirakol k" id="verimNoktaBas">Nokta</span><span data-s="2024" class="sirakol k">2024<br>satış</span><span data-s="v2024" class="sirakol k">2024<br>yıllık<br>nokta başı</span><span data-s="2025" class="sirakol k">2025<br>satış</span><span data-s="v2025" class="sirakol k">2025<br>yıllık<br>nokta başı</span><span data-s="2026" class="sirakol k">2026*<br>satış</span><span data-s="v2026" class="sirakol k gen">2026*<br>7 aylık<br>nokta başı</span><span class="okbos"></span></span></div>
    <div class="liste" id="verimListe"></div>
    <div class="bos" id="verimBos" style="display:none">Sonuç bulunamadı.</div>
  </section>

  <!-- FİRMA EKRANI: Bayiler / Servisler sekmeleri.
       Marka değil FİRMA merkezli: aynı cari kod tek satır, yanında
       hangi markaların bayisi/servisi olduğu. 5000+ kart olduğu için
       kademeli çiziliyor. -->
  <section id="vFirma" style="display:none">
    <h2 id="firmaBaslik">Bayiler</h2>
    <p class="notm" id="firmaNot"></p>
    <div class="altbar">
      <button class="btn ana" id="btnFirmaXls">Excel indir</button>
    </div>
    <div class="yapiskan">
      <input class="ara" id="araFirma" type="search"
             placeholder="Firma adı, il, ilçe veya marka ara" autocomplete="off">
    </div>
    <div class="liste" id="firmaListe"></div>
    <div class="bos" id="firmaBos" style="display:none">Sonuç bulunamadı.</div>
    <div style="text-align:center;margin:12px 0 4px">
      <button class="btn" id="btnDahaFirma" style="display:none">Daha fazla göster</button>
    </div>
  </section>

  <section id="vTumMarka" style="display:none">
    <h2>Marka listesi</h2>

    <div class="sirala" id="mrkSirala">
      <span class="et">Sırala</span>
      <button data-s="sayi" class="secili">Nokta sayısına göre</button>
      <button data-s="ad">A → Z</button>
      <button data-s="satis">Satışa göre</button>
      <button data-s="servis">Servise göre</button>
    </div>
    <div class="altbar">
      <button class="btn ana" id="btnOzetXls">Özet tablosunu Excel indir</button>
      <button class="btn" id="btnOzetYaz">Yazdır / PDF</button>
    </div>
    <div class="bilgi" id="sayiUyari">
      <b>Sayılar henüz toplanmadı.</b> Tarama ilk kez çalıştığında bu sütunlar dolar.
    </div>
    <div class="yapiskan">
      <input class="ara" id="araTum" type="search" placeholder="Marka ara" autocomplete="off">
    </div>
    <div class="liste">
      <div class="baslikcubuk sirali" data-tablo="tumListe"><span class="ilkkol sirakol" data-s="ad">Marka</span><span class="sagb"><span data-s="yalnizSatis" class="sirakol k">Sadece<br>bayi</span><span data-s="yalnizServis" class="sirakol k">Sadece<br>servis</span><span data-s="ikisi" class="sirakol k">Bayi ve<br>servis</span><span data-s="satisNoktasi" class="sirakol k gen" style="color:var(--satis)">Toplam<br>satış nok.</span><span data-s="servisNoktasi" class="sirakol k gen" style="color:var(--servis)">Toplam<br>servis nok.</span><span data-s="toplam" class="sirakol k">Toplam<br>nokta</span><span class="okbos"></span></span></div>
      <div id="tumListe"></div>
    </div>
    <div class="bos" id="tumBos" style="display:none">Sonuç yok.</div>
  </section>

</div>
<script>
const D = __VERI__;
/* Yapışkan başlıklar üst şeridin ALTINA otursun; yoksa şeridin arkasında
   kalıp görünmez oluyorlar. Şerit yüksekliği ekrana göre değiştiği için
   ölçüp CSS değişkenine yazıyoruz. */
function seritOlc(){
  const e=document.querySelector(".serit");
  if(e) document.documentElement.style.setProperty("--serit-y", e.offsetHeight+"px");
  // Alt özet çubuğu sabit; son kaydın üstüne binmemesi için sayfa
  // altına onun YÜKSEKLİĞİ kadar boşluk bırakılıyor. Sabit bir değer
  // yetmiyordu: çubuk dar ekranda iki satıra sarınca yükseliyor.
  const a=document.querySelector(".altozet");
  if(a) document.documentElement.style.setProperty(
    "--altozet-y", (a.offsetHeight + 14) + "px");

  // Yapışkan arama/süzgeç bloğu da şeridin altına yapışıyor. Sütun
  // başlığı onunla AYNI yere yapışınca arkasında kalıyordu; başlığı
  // o bloğun altına indiriyoruz. Ekranlar farklı yükseklikte olduğu
  // için görünür olanı ölçüyoruz.
  let y = 0;
  document.querySelectorAll(".yapiskan").forEach(e=>{
    if(e.offsetParent !== null) y = Math.max(y, e.offsetHeight);
  });
  document.documentElement.style.setProperty("--yapiskan-y", y + "px");
}
addEventListener("resize", seritOlc);
addEventListener("load", seritOlc);
setTimeout(seritOlc, 0);
const $ = s => document.querySelector(s);
const [B_MARKA,B_AD,B_IL,B_ILCE,B_ADRES,B_TEL,B_DURUM,B_ROL,B_GIRIS,B_KOD] =
      [0,1,2,3,4,5,6,7,8,9];
const esc = s => String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const kat = s => (s||"").toLocaleLowerCase("tr")
  .replace(/[çğıöşü]/g,c=>({"ç":"c","ğ":"g","ı":"i","ö":"o","ş":"s","ü":"u"}[c]))
  .replace(/[^a-z0-9]+/g," ").trim();

const ROL_SINIF = {satis:"satis", servis:"servis", satis_servis:"ikisi"};
const ROL_AD    = {satis:"Satış", servis:"Servis", satis_servis:"Satış + Servis"};

let IL=null, ILCE="", ROL="tum", MD=null, SIRA="sayi";
/* Birden çok ilçe seçilebiliyor. ILCE tek değer olarak kalıyor
   (adres çubuğu ve eski kodlarla uyum için); ILCELER seçili kümedir.
   Küme boşsa "tüm ilçeler" demektir. */
let ILCELER = new Set();
/* Sütun başlığından sıralama durumu: tablo -> {anahtar, yon}.
   Genel kapsamda; hem özet tabloları hem "Tüm markalar" okuyor. */
const SIRA_DURUM = {};
let basligiIsaretle = () => {};
const VAR_VERI = D.bayiler.length > 0;

/* ---------- üst bilgiler ---------- */
$("#veriTarih").textContent = new Date(D.olusturma)
  .toLocaleString("tr-TR",{day:"2-digit",month:"2-digit",year:"numeric",hour:"2-digit",minute:"2-digit"});
(function(){
})();
if(VAR_VERI) $("#sayiUyari").style.display="none";

/* ---------- rol süzgeci ---------- */
function rolSuzgecCiz(hedef, veri){
  const s={tum:veri.length,satis:0,servis:0,ikisi:0};
  veri.forEach(b=>s[ROL_SINIF[b[B_ROL]]]++);
  // Birleşik kümeler: "satış noktası" = yalnız satış + satış&servis.
  // Kullanıcı asıl bu sayıyı arıyor: kaç noktada satış yapılıyor.
  s.satisNok  = s.satis  + s.ikisi;
  s.servisNok = s.servis + s.ikisi;
  const et={
    tum:"Tümü",
    satisNok:"Toplam satış noktası",
    servisNok:"Toplam servis noktası",
    satis:"Sadece satış",
    servis:"Sadece servis",
    ikisi:"Satış + Servis"};
  const sira=["tum","satisNok","servisNok","satis","servis","ikisi"];
  $(hedef).innerHTML = sira.map(r=>
    `<button data-r="${r}" class="${ROL===r?"secili":""}${
       (r==="satisNok"||r==="servisNok")?" birlesik":""}">${et[r]}
       <span class="n">${s[r]}</span></button>`).join("");
}
function rolBagla(hedef, ciz){
  $(hedef).onclick = e => {
    const b=e.target.closest("button"); if(!b) return;
    ROL = b.dataset.r; ciz();
  };
}
const bicim = n => (n||0).toLocaleString("tr-TR");

/* ---------- firma → hangi markaların bayisi ----------
   Aynı cari kod, aynı fiziksel firma demek. Bir firma birden çok
   markaya bayilik yapabiliyor (rekor: 14 marka). Kartta "bu bayi
   şunların da bayisi" satırı için markaları koda göre topluyoruz. */
const FIRMA_MARKA = (() => {
  const g = {};
  D.bayiler.forEach(b => {
    const k = b[B_KOD];
    if (!k) return;
    (g[k] ||= new Set()).add(b[B_MARKA]);
  });
  return g;
})();

function digerMarkalar(x){
  /* Bu bayinin çalıştığı TÜM markalar — bakılan marka da dahil.
     Önceden bakılan marka listeden çıkarılıyordu; Falcon sayfasında
     "Bu bayi ayrıca: Arora, Hero, Mobilette" yazıp Falcon'u
     göstermeyince kartın tamamına bakınca eksik görünüyordu.
     Bakılan marka en başta ve vurgulu duruyor. */
  const s = FIRMA_MARKA[x[B_KOD]];
  if (!s || s.size < 2) return [];
  const bu = x[B_MARKA];
  const digerleri = [...s].filter(m => m !== bu)
                          .sort((a,b)=>a.localeCompare(b,"tr"));
  return [bu, ...digerleri];
}

/* ---------- alt özet: TEKİL BAYİ sayıları ----------
   D.bayiler marka×nokta tutuyor. Aynı fiziksel bayi birden çok markanın
   kaydında geçiyor (bir firma 14 markaya kadar bayilik yapabiliyor).
   Cari koda göre tekilleştirip her bayiyi bir kez sayıyoruz; rol de
   o bayinin TÜM kayıtlarının birleşimi. */
function tekilSay(veri){
  const g = new Map();
  veri.forEach(b=>{
    const k = b[B_KOD] || ("x|"+b[B_AD]+"|"+b[B_IL]+"|"+b[B_ILCE]);
    let o = g.get(k);
    if(!o){ o = {satis:false, servis:false}; g.set(k, o); }
    const r = b[B_ROL];
    if(r==="satis"||r==="satis_servis") o.satis = true;
    if(r==="servis"||r==="satis_servis") o.servis = true;
  });
  let ys=0, yv=0, ik=0;
  g.forEach(o=>{ if(o.satis&&o.servis) ik++; else if(o.satis) ys++; else yv++; });
  return {yalnizSatis:ys, yalnizServis:yv, ikisi:ik,
          satisNoktasi:ys+ik, servisNoktasi:yv+ik, toplam:g.size};
}

/* Çubuk </body> hemen öncesinde; bu betik ondan ÖNCE çalıştığı için
   ilk çağrıda öğeler henüz yok. Yoksa sessizce geç, DOM hazır olunca
   yeniden çağrılıyor. */
let AO_SON = null;
function altOzetGuncelle(baslik, veri){
  AO_SON = [baslik, veri];
  if(!$("#aoBaslik")) return;
  const c = tekilSay(veri);
  $("#aoBaslik").textContent = baslik;
  $("#aoSatis").textContent     = bicim(c.yalnizSatis);
  $("#aoServis").textContent    = bicim(c.yalnizServis);
  $("#aoIkisi").textContent     = bicim(c.ikisi);
  $("#aoSatisNok").textContent  = bicim(c.satisNoktasi);
  $("#aoToplam").textContent    = bicim(c.toplam);
  $("#aoServisNok").textContent = bicim(c.servisNoktasi);
}

const rolGecer = b => {
  if (ROL === "tum") return true;
  const sn = ROL_SINIF[b[B_ROL]];
  if (ROL === "satisNok")  return sn === "satis"  || sn === "ikisi";
  if (ROL === "servisNok") return sn === "servis" || sn === "ikisi";
  return sn === ROL;
};

/* ---------- ekranlar ---------- */
/* Ekranı gösterir. gecmis=true ise adres etiketine yazar; böylece tarayıcının
   geri tuşu sayfadan çıkmak yerine bir önceki ekrana döner. */
function ekran(v, gecmis=true){
  // Ekranlar farklı yükseklikte yapışkan blok taşıyor (arama kutusu,
  // ilçe çipleri, rol süzgeci). Geçişte yeniden ölçüyoruz ki sütun
  // başlığı hep o bloğun ALTINA yapışsın.
  setTimeout(seritOlc, 0);
  ["vOzet","vIl","vMarkalar","vTumMarka","vMarkaDetay","vFirma","vVerim"]
    .forEach(x=>$("#"+x).style.display="none");
  $("#"+v).style.display="block";
  $("#sar").classList.toggle("genis", v==="vTumMarka"||v==="vMarkaDetay"||
                                      v==="vOzet"||v==="vFirma"||v==="vVerim");
  // Özet ve Satışa Oran ekranlarında sayılar kendi bölümlerinde;
  // alt çubuk hem gereksiz hem de yanıltıcı oluyordu.
  const ao = $("#altOzet");
  if(ao) ao.style.display = (v==="vOzet"||v==="vVerim") ? "none" : "flex";
  $("#sekOzet").classList.toggle("aktif", v==="vOzet");
  $("#sekIl").classList.toggle("aktif", v==="vIl"||v==="vMarkalar");
  $("#sekMarka").classList.toggle("aktif", v==="vTumMarka"||v==="vMarkaDetay");
  $("#sekBayi").classList.toggle("aktif", v==="vFirma" && FIRMA_ROL==="satis");
  $("#sekServis").classList.toggle("aktif", v==="vFirma" && FIRMA_ROL==="servis");
  $("#sekVerim").classList.toggle("aktif", v==="vVerim");
  window.scrollTo(0,0);
  if(gecmis) durumYaz(v);
}

/* ---------- tarayıcı geçmişi ----------
   Adres etiketi (#) kullanıyoruz: pushState dosya olarak açılan sayfalarda
   geçmiş kaydı oluşturmuyor, hash her ortamda çalışıyor. Ayrıca kullanıcı
   bulunduğu ekranın bağlantısını paylaşabiliyor. */
let _kendiYazdi = false;

function durumYaz(v){
  const p = new URLSearchParams();
  p.set("e", v);
  if(IL) p.set("il", IL.ad);
  if(ILCE) p.set("ilce", ILCE);
  if(MD && v === "vMarkaDetay") p.set("marka", MD.ad);
  if(ROL && ROL !== "tum") p.set("rol", ROL);
  const h = "#" + p.toString();
  if(location.hash === h) return;
  _kendiYazdi = true;
  location.hash = h;
  setTimeout(() => { _kendiYazdi = false; }, 0);
}

function hashUygula(){
  const p = new URLSearchParams(location.hash.slice(1));
  const v = p.get("e") || "vOzet";
  ROL = p.get("rol") || "tum";
  const marka = p.get("marka"), il = p.get("il"), ilce = p.get("ilce") || "";

  if(v === "vMarkaDetay" && marka){
    MD = OZET.find(m => m.ad === marka);
    if(MD){ cizMD(); ekran("vMarkaDetay", false); return; }
  }
  if(v === "vMarkalar" && il){
    const bulunan = D.iller.find(x => x.ad === il);
    if(bulunan){
      IL = bulunan; ILCE = ilce;
      $("#kod").textContent = IL.plaka; $("#ilAdi").textContent = IL.ad;
      cizIlce();
      if(ILCE){ ILCELER = new Set([ILCE]); ilceListesiCiz(); ilceOzetGuncelle(); }
      cizMarka(); ekran("vMarkalar", false); return;
    }
  }
  if(v === "vTumMarka"){ cizTum(); ekran("vTumMarka", false); return; }
  if(v === "vIl"){ cizIl(); ekran("vIl", false); return; }
  cizOzet(); ekran("vOzet", false);
}

window.addEventListener("hashchange", () => { if(!_kendiYazdi) hashUygula(); });
$("#sekOzet").onclick  = () => { cizOzet(); ekran("vOzet"); };
/* Logoya (veya başlık yazısına) dokununca ana sayfa = Özet.
   Seçili il, ilçe, marka ve süzgeçler sıfırlanıyor ki temiz bir
   başlangıç olsun.

   Doğrudan onclick yerine BELGE DÜZEYİNDE dinleyici kullanıyoruz:
   öğe henüz oluşmamışsa ya da sonradan yeniden çizilirse bağ kopmuyor. */
function anaSayfayaDon(e){
  if(e) e.preventDefault();
  IL = null; ILCE = ""; ROL = "tum"; MD = null;
  const a = $("#araIl"); if(a) a.value = "";
  const b = $("#araMarka"); if(b) b.value = "";
  cizOzet(); ekran("vOzet");
  window.scrollTo(0, 0);
}
document.addEventListener("click", e => {
  if(e.target.closest("#anaSayfa, #anaSayfaKisa, .tepe .orta h1"))
    anaSayfayaDon(e);
});
$("#sekIl").onclick    = () => {
  // Liste çizilmeden ekran açılıyordu; sekmeye basınca boş görünüyordu.
  if(IL){ ekran("vMarkalar"); } else { cizIl(); ekran("vIl"); }
};
$("#sekMarka").onclick = () => { cizTum(); ekran("vTumMarka"); };
$("#sekBayi").onclick   = () => { FIRMA_ROL="satis";  FIRMA_LIMIT=FIRMA_SAYFA;
                                  $("#araFirma").value=""; cizFirma(); ekran("vFirma"); };
$("#sekServis").onclick = () => { FIRMA_ROL="servis"; FIRMA_LIMIT=FIRMA_SAYFA;
                                  $("#araFirma").value=""; cizFirma(); ekran("vFirma"); };
$("#araFirma").oninput   = () => { FIRMA_LIMIT=FIRMA_SAYFA; cizFirma(); };
$("#sekVerim").onclick   = () => { $("#araVerim").value=""; cizVerim(); ekran("vVerim"); };
$("#araVerim").oninput   = () => cizVerim();
$("#btnVerimXls").onclick = async e => {
  const btn = e.target, eski = btn.textContent;
  btn.disabled = true; btn.textContent = "Hazırlanıyor…";
  // XLSX kütüphanesi ihtiyaç anında indiriliyor (sayfa hafif kalsın diye)
  if(!(await xlsxYukle())){
    btn.textContent = "İnternet gerekiyor";
    setTimeout(()=>{btn.textContent=eski; btn.disabled=false;}, 2500);
    return;
  }
  const l = verimVeri().sort((a,b)=>b.v2025-a.v2025);
  const etiket = VERIM_ROL==="satis" ? "Bayi" : "Servis";
  const bas = ["İl","Plaka",`${etiket} noktası`,
    "2023 satış","2024 satış","2025 satış","2026 satış (31.07)",
    `2023 ${etiket.toLocaleLowerCase("tr")} başı yıllık`,
    `2024 ${etiket.toLocaleLowerCase("tr")} başı yıllık`,
    `2025 ${etiket.toLocaleLowerCase("tr")} başı yıllık`,
    `2026 ${etiket.toLocaleLowerCase("tr")} başı 7 aylık (31.07)`];
  const o = [bas, ...l.map(x=>[x.ad,x.plaka,x.nokta,
    x["2023"],x["2024"],x["2025"],x["2026"],
    x.v2023,x.v2024,x.v2025,x.v2026])];
  const wb = XLSX.utils.book_new();
  sayfaEkle(wb, `${etiket} basina satis`, o,
    [{wch:16},{wch:7},{wch:14},{wch:13},{wch:13},{wch:13},{wch:18},
     {wch:15},{wch:15},{wch:15},{wch:20}]);
  indir(new Blob([XLSX.write(wb,{bookType:"xlsx",type:"array"})],
    {type:"application/octet-stream"}),
    dosyaAdi(etiket.toLocaleLowerCase("tr")+"-basina-satis","xlsx"));
  btn.textContent = eski; btn.disabled = false;
};
$("#verimSecim").onclick = e => {
  const b=e.target.closest("button"); if(!b) return;
  VERIM_ROL=b.dataset.v;
  [...$("#verimSecim").querySelectorAll("button")].forEach(x=>
    x.classList.toggle("secili", x===b));
  cizVerim();
};
// İl satırına tıklayınca o ilin marka listesine git
$("#verimListe").onclick = e => {
  const b=e.target.closest(".sat"); if(!b) return;
  IL=D.iller.find(x=>x.ad===b.dataset.il); if(!IL) return;
  ILCE=""; ROL="tum";
  $("#kod").textContent=IL.plaka; $("#ilAdi").textContent=IL.ad;
  cizIlce(); cizMarka(); ekran("vMarkalar");
};
$("#btnDahaFirma").onclick = () => { FIRMA_LIMIT += FIRMA_SAYFA*2; cizFirma(); };
$("#geri").onclick     = () => { IL=null; ILCE=""; ROL="tum"; $("#araMarka").value=""; ekran("vIl"); };
$("#geriMarka").onclick= () => { ROL="tum"; cizTum();
  altOzetGuncelle("Türkiye geneli", D.bayiler); ekran("vTumMarka"); };

/* ---------- ÖZET ---------- */
function sayRol(veri){
  const c={satis:0,servis:0,ikisi:0};
  veri.forEach(b=>c[ROL_SINIF[b[B_ROL]]]++);
  // Kesişim kümesi mantığı:
  //   yalnizSatis  = yalnızca satış yapan noktalar
  //   yalnizServis = yalnızca servis veren noktalar
  //   ikisi        = kesişim (hem satış hem servis)
  //   satisNoktasi = yalnizSatis + ikisi  → "kaç noktada satış yapılıyor"
  //   servisNoktasi= yalnizServis + ikisi
  //   toplam       = birleşim (tüm noktalar)
  return {yalnizSatis:c.satis, yalnizServis:c.servis, ikisi:c.ikisi,
          satisNoktasi:c.satis+c.ikisi, servisNoktasi:c.servis+c.ikisi,
          // geriye dönük adlar
          satis:c.satis+c.ikisi, servis:c.servis+c.ikisi,
          toplam:veri.length};
}
function cizOzet(){
  const t=sayRol(D.bayiler);
  const iller=new Set(D.bayiler.map(b=>b[B_IL]).filter(Boolean));
  const ilceler=new Set(D.bayiler.filter(b=>b[B_ILCE]).map(b=>b[B_IL]+"/"+b[B_ILCE]));
  const markalar=new Set(D.bayiler.map(b=>b[B_MARKA]));
  const bicim=n=>n.toLocaleString("tr-TR");

  /* Kutular artık FİRMA bazlı (tekilleştirilmiş), kayıt bazlı değil.
     Kayıt bazlı sayılar yanıltıcıydı: bir firma 14 markaya bayilik
     yapınca 14 kez sayılıyordu. Doğru sayılar alt çubuktaydı; onları
     buraya taşıdık ve Özet ekranında alt çubuğu gizledik. */
  const f = tekilSay(D.bayiler);
  $("#kutular").innerHTML=`
    <div class="kutu toplam"><span class="n">${bicim(f.toplam)}</span>
      <span class="e">Satış + Servis Toplamı<br>1 işyeri 1 adet</span></div>
    <div class="kutu satis"><span class="n">${bicim(f.satisNoktasi)}</span>
      <span class="e">Toplam satış noktası<br>${bicim(f.yalnizSatis)} sadece bayi + ${bicim(f.ikisi)} bayi ve servis</span></div>
    <div class="kutu servis"><span class="n">${bicim(f.servisNoktasi)}</span>
      <span class="e">Toplam servis noktası<br>${bicim(f.yalnizServis)} sadece servis + ${bicim(f.ikisi)} bayi ve servis</span></div>
    <div class="kutu"><span class="n">${bicim(f.yalnizSatis)}</span><span class="e">Sadece bayi</span></div>
    <div class="kutu"><span class="n">${bicim(f.yalnizServis)}</span><span class="e">Sadece servis</span></div>
    <div class="kutu ikisi"><span class="n">${bicim(f.ikisi)}</span><span class="e">Bayi ve servis<br>(kesişim)</span></div>
    <div class="kutu"><span class="n">${markalar.size}</span><span class="e">Marka</span></div>
    <div class="kutu"><span class="n">${iller.size}</span><span class="e">İl</span></div>
    <div class="kutu"><span class="n">${ilceler.size}</span><span class="e">İlçe</span></div>`;

  // Kapsama bilgisi
  const telli=D.bayiler.filter(b=>b[B_TEL]).length;
  const ilceli=D.bayiler.filter(b=>b[B_ILCE]).length;
  const eski=D.bayiler.filter(b=>b[B_DURUM]!=="Güncel").length;
  $("#kapsam").innerHTML=
    `<span>Telefonu olan: <b>%${Math.round(telli/t.toplam*100)}</b></span>
     <span>İlçesi belirli: <b>%${Math.round(ilceli/t.toplam*100)}</b></span>
     <span>Kapsanan il: <b>${iller.size}/81</b></span>
     ${eski?`<span style="color:var(--uyari)">Doğrulanamayan: <b>${eski}</b></span>`:""}`;

  // Satır çizici — yanında oransal çubuk
  const enCok = v => Math.max(1, ...v.map(x=>x[1].length));
  function satirlar(veri, tip){
    const m=enCok(veri);
    return veri.map(([ad,v],ix)=>{
      const c=sayRol(v);
      const p=(D.iller.find(x=>x.ad===ad)||{}).plaka;
      return `<button class="sat" data-${tip}="${esc(ad)}">
        <span class="sirano">${ix+1}</span>
        ${p?`<span class="plaka"><span class="tr">TR</span><span class="kod">${p}</span></span>`:""}
        <span class="govde">
          <span class="ustsatir"><span class="ad">${esc(ad)}</span></span>
          <span class="cubuk">
            <i class="s" style="width:${c.satis/m*100}%"></i>
            <i class="v" style="left:${c.satis/m*100}%;width:${c.servis/m*100}%"></i>
          </span>
        </span>
        <span class="sag">
          <span class="sayi k" style="color:var(--satis)">${c.yalnizSatis}</span>
          <span class="sayi k" style="color:var(--servis)">${c.yalnizServis}</span>
          <span class="sayi k" style="color:var(--ikisi)">${c.ikisi}</span>
          <span class="sayi k gen vurgu">${c.satisNoktasi}</span>
        <span class="sayi k gen vurguserv">${c.servisNoktasi}</span>
          <span class="sayi k" style="font-weight:700">${c.toplam}</span>
          <span class="ok">›</span></span></button>`;}).join("");
  }

  /* ---------- sıralanabilir özet tabloları ----------
     Her sütun başlığı tıklanınca o sütuna göre sıralanıyor (Excel gibi).
     İlk tıklama büyükten küçüğe; aynı başlığa tekrar tıklanınca ters
     çevriliyor. Ad sütunu alfabetik başlıyor. */
  // (SIRA_DURUM genel kapsamda tanımlı — bkz. ROL_SINIF yakını)

  function siraDegerleri(v){
    const c = sayRol(v);
    return {yalnizSatis:c.yalnizSatis, yalnizServis:c.yalnizServis,
            ikisi:c.ikisi, satisNoktasi:c.satisNoktasi,
            servisNoktasi:c.servisNoktasi, toplam:c.toplam,
            marka:new Set(v.map(x=>x[B_MARKA])).size};
  }

  function sirala(giris, tablo){
    const d = SIRA_DURUM[tablo] || {anahtar:"toplam", yon:-1};
    const l = [...giris];
    if(d.anahtar === "ad"){
      l.sort((a,b)=>(d.yon<0 ? -1 : 1) * a[0].localeCompare(b[0],"tr"));
    } else {
      l.sort((a,b)=>{
        const fa=siraDegerleri(a[1])[d.anahtar]||0;
        const fb=siraDegerleri(b[1])[d.anahtar]||0;
        return (d.yon<0 ? fb-fa : fa-fb) || a[0].localeCompare(b[0],"tr");
      });
    }
    return l;
  }

  basligiIsaretle = function(tablo){
    const d = SIRA_DURUM[tablo] || {anahtar:"toplam", yon:-1};
    document.querySelectorAll(`.baslikcubuk[data-tablo="${tablo}"] .sirakol`)
      .forEach(h=>{
        const secili = h.dataset.s === d.anahtar;
        h.classList.toggle("aktifsira", secili);
        h.dataset.yon = secili ? (d.yon<0 ? "asagi" : "yukari") : "";
      });
  };

  const OZET_VERI = {};

  function ozetCiz(tablo){
    const {veri, tip, hedef} = OZET_VERI[tablo];
    const l = sirala(veri, tablo);
    $(hedef).innerHTML = tip==="ilce" ? ilceSatirlari(l) : satirlar(l, tip);
    basligiIsaretle(tablo);
  }

  function siralamayiBagla(){
    document.querySelectorAll(".baslikcubuk.sirali").forEach(bas=>{
      bas.onclick = e => {
        const h = e.target.closest(".sirakol");
        if(!h) return;
        const tablo = bas.dataset.tablo, a = h.dataset.s;
        const d = SIRA_DURUM[tablo] || {anahtar:"toplam", yon:-1};
        SIRA_DURUM[tablo] = (d.anahtar === a)
          ? {anahtar:a, yon:-d.yon}
          : {anahtar:a, yon:(a==="ad" ? 1 : -1)};   // sayılar büyükten küçüğe
        if(OZET_VERI[tablo]) ozetCiz(tablo);
        else if(tablo==="tumListe") cizTum();
        else if(tablo==="ilListe") cizIl();
        else if(tablo==="verimListe") cizVerim();
      };
    });
  }

  const ilG={};
  D.bayiler.forEach(b=>{ if(b[B_IL]) (ilG[b[B_IL]]||=[]).push(b); });
  const ilS=Object.entries(ilG);
  $("#ilAdet").textContent=`${ilS.length} il`;
  OZET_VERI["ozetIl"]={veri:ilS, tip:"il", hedef:"#ozetIl"};

  const mG={};
  D.bayiler.forEach(b=>(mG[b[B_MARKA]]||=[]).push(b));
  const mS=Object.entries(mG);
  $("#mrkAdet").textContent=`${mS.length} marka`;
  OZET_VERI["ozetMarka"]={veri:mS, tip:"mrk", hedef:"#ozetMarka"};

  // İlçe dağılımı — ilk 60, en yoğundan
  const iG={};
  D.bayiler.forEach(b=>{ if(b[B_ILCE]) (iG[b[B_IL]+"|"+b[B_ILCE]]||=[]).push(b); });
  const iS=Object.entries(iG).sort((a,b)=>b[1].length-a[1].length).slice(0,60);
  $("#ilceAdet").textContent=`en yoğun ${iS.length} ilçe · toplam ${ilceler.size}`;
  OZET_VERI["ozetIlce"]={veri:iS, tip:"ilce", hedef:"#ozetIlce"};

  function ilceSatirlari(liste){ return liste.map(([k,v],ix)=>{
    const [il,ilce]=k.split("|"), c=sayRol(v);
    return `<button class="sat" data-il="${esc(il)}" data-ilce="${esc(ilce)}">
      <span class="sirano">${ix+1}</span>
      <span class="govde"><span class="ustsatir"><span class="ad">${esc(ilce)}</span>
        <span class="men">${esc(il)}</span></span></span>
      <span class="sag">
        <span class="sayi k" style="color:var(--satis)">${c.yalnizSatis}</span>
        <span class="sayi k" style="color:var(--servis)">${c.yalnizServis}</span>
        <span class="sayi k" style="color:var(--ikisi)">${c.ikisi}</span>
        <span class="sayi k gen vurgu">${c.satisNoktasi}</span>
        <span class="sayi k gen vurguserv">${c.servisNoktasi}</span>
        <span class="sayi k">${new Set(v.map(x=>x[B_MARKA])).size}</span>
        <span class="sayi k" style="font-weight:700">${c.toplam}</span>
        <span class="ok">›</span></span></button>`;}).join(""); }

  ["ozetIl","ozetMarka","ozetIlce"].forEach(ozetCiz);
  siralamayiBagla();
  altOzetGuncelle("Türkiye geneli", D.bayiler);
  yazdirBilgiGuncelle("Genel Özet", D.bayiler.length);
}
function ozetTiklama(e){
  const b=e.target.closest("button.sat"); if(!b) return;
  if(b.dataset.mrk){ markaAc(b.dataset.mrk); return; }
  if(b.dataset.il){
    IL=D.iller.find(x=>x.ad===b.dataset.il); if(!IL) return;
    ILCE=b.dataset.ilce||""; ROL="tum";
    $("#kod").textContent=IL.plaka; $("#ilAdi").textContent=IL.ad;
    cizIlce();
    if(ILCE){ ILCELER = new Set([ILCE]); ilceListesiCiz(); ilceOzetGuncelle(); }
    cizMarka(); ekran("vMarkalar");
  }
}
["#ozetIl","#ozetMarka","#ozetIlce"].forEach(x=>$(x).onclick=ozetTiklama);

/* ---------- hızlı arama: her şeyde ara, doğrudan git ---------- */
let zh;
$("#hizliAra").oninput = () => { clearTimeout(zh); zh=setTimeout(hizliCiz,140); };
function hizliCiz(){
  const q=kat($("#hizliAra").value);
  if(q.length<2){ $("#oneriKutu").innerHTML=""; return; }
  const out=[];
  D.iller.filter(i=>kat(i.ad).includes(q)).slice(0,4).forEach(i=>{
    const n=D.bayiler.filter(b=>b[B_IL]===i.ad).length;
    out.push(`<button class="sat" data-il="${esc(i.ad)}">
      <span class="plaka"><span class="tr">TR</span><span class="kod">${i.plaka}</span></span>
      <span class="ad">${esc(i.ad)}</span>
      <span class="sag"><span class="men">İL</span>
      <span class="sayi">${n}</span><span class="ok">›</span></span></button>`);});
  OZET.filter(m=>kat(m.ad).includes(q)&&m.toplam).slice(0,4).forEach(m=>
    out.push(`<button class="sat" data-mrk="${esc(m.ad)}">
      <span class="ad">${esc(m.ad)}</span>
      <span class="sag"><span class="men">MARKA</span>
      <span class="sayi">${m.toplam}</span><span class="ok">›</span></span></button>`));
  const ilceler=[...new Set(D.bayiler.filter(b=>b[B_ILCE]&&kat(b[B_ILCE]).includes(q))
    .map(b=>b[B_IL]+"|"+b[B_ILCE]))].slice(0,4);
  ilceler.forEach(k=>{
    const [il,ilce]=k.split("|");
    const n=D.bayiler.filter(b=>b[B_IL]===il&&b[B_ILCE]===ilce).length;
    out.push(`<button class="sat" data-il="${esc(il)}" data-ilce="${esc(ilce)}">
      <span class="ad">${esc(ilce)}</span><span class="men">${esc(il)}</span>
      <span class="sag"><span class="men">İLÇE</span>
      <span class="sayi">${n}</span><span class="ok">›</span></span></button>`);});
  const bayiler=D.bayiler.filter(b=>kat(b[B_AD]).includes(q)).slice(0,5);
  bayiler.forEach(b=>out.push(`<button class="sat" data-il="${esc(b[B_IL])}"
      data-ilce="${esc(b[B_ILCE])}">
      <span class="ad">${esc(b[B_AD])}</span>
      <span class="men">${esc(b[B_MARKA])} · ${esc(b[B_ILCE]||b[B_IL])}</span>
      <span class="sag"><span class="ok">›</span></span></button>`));
  $("#oneriKutu").innerHTML = out.join("") ||
    `<div class="bos">Sonuç yok.</div>`;
}
$("#oneriKutu").onclick = e => { ozetTiklama(e); $("#hizliAra").value=""; $("#oneriKutu").innerHTML=""; };
$("#btnOzetTumXls").onclick = e => excelIndir({tip:"tum"},e.target);
$("#btnOzetYaz2").onclick = () => window.print();

/* ---------- iller ---------- */
let IL_SIRA = "sayi";      // varsayılan: en çok noktadan aza
/* İl sıralaması artık sütun başlıklarından (bkz. baslikcubuk[data-tablo=ilListe]) */

function cizIl(){
  $("#ilUstbar").style.display = VAR_VERI ? "flex":"none";
  const q=kat($("#araIl").value);
  let l=D.iller.filter(i=>!q||kat(i.ad).includes(q)||i.plaka.startsWith(q));

  // Her il için sayaçlar; sıralama da bunlar üzerinden.
  const say = {};
  l.forEach(i=>{ say[i.ad]=sayRol(D.bayiler.filter(x=>x[B_IL]===i.ad)); });

  const d = SIRA_DURUM["ilListe"] || {anahtar:"toplam", yon:-1};
  if(d.anahtar==="ad")
    l=[...l].sort((a,b)=>(d.yon<0?-1:1)*a.ad.localeCompare(b.ad,"tr"));
  else
    l=[...l].sort((a,b)=>{
      const fa=say[a.ad][d.anahtar]||0, fb=say[b.ad][d.anahtar]||0;
      return (d.yon<0 ? fb-fa : fa-fb) || a.ad.localeCompare(b.ad,"tr");
    });

  $("#ilBos").style.display=l.length?"none":"block";
  altOzetGuncelle("Türkiye geneli", D.bayiler);
  $("#ilListe").innerHTML=l.map((i,ix)=>{
    const c=say[i.ad];
    return `<button class="sat" data-slug="${i.slug}">
      <span class="sirano">${ix+1}</span>
      <span class="govde"><span class="ustsatir"><span class="ad">${esc(i.ad)}</span>
        <span class="men">${i.plaka}</span></span></span>
      <span class="sag">
        <span class="sayi k" style="color:var(--satis)">${c.yalnizSatis}</span>
        <span class="sayi k" style="color:var(--servis)">${c.yalnizServis}</span>
        <span class="sayi k" style="color:var(--ikisi)">${c.ikisi}</span>
        <span class="sayi k gen vurgu">${c.satisNoktasi}</span>
        <span class="sayi k gen vurguserv">${c.servisNoktasi}</span>
        <span class="sayi k" style="font-weight:700">${c.toplam}</span>
        <span class="ok">›</span></span></button>`;}).join("");
  basligiIsaretle("ilListe");
}
$("#ilListe").onclick = e => {
  const b=e.target.closest(".sat"); if(!b) return;
  IL=D.iller.find(x=>x.slug===b.dataset.slug); ILCE=""; ROL="tum";
  $("#kod").textContent=IL.plaka; $("#ilAdi").textContent=IL.ad;
  cizIlce(); cizMarka(); ekran("vMarkalar");
};
let z1; $("#araIl").oninput=()=>{clearTimeout(z1);z1=setTimeout(cizIl,110);};

/* ---------- ilçe ---------- */
let ILCE_LISTE = [];

function cizIlce(){
  ILCE_LISTE = [...new Set(D.bayiler.filter(b=>b[B_IL]===IL.ad)
    .map(b=>b[B_ILCE]).filter(Boolean))].sort((a,b)=>a.localeCompare(b,"tr"));
  ILCELER = new Set();
  $("#ilceAra").value = "";
  ilceListesiCiz();
  ilceOzetGuncelle();
  $("#ilceMenu").hidden = true;
  $("#ilceAc").setAttribute("aria-expanded", "false");
  document.body.classList.remove("ilcepanel");
  $("#ilceAc").style.display = ILCE_LISTE.length ? "" : "none";
}

function ilceListesiCiz(){
  const q = kat($("#ilceAra").value);
  const l = q ? ILCE_LISTE.filter(x => kat(x).includes(q)) : ILCE_LISTE;
  // "Tüm ilçeler" hep en başta
  $("#ilceListesi").innerHTML =
    `<label class="ilcesatir"><input type="checkbox" id="ilceHepsi"${
      ILCELER.size===0?" checked":""}><span><b>Tüm ${esc(IL.ad)}</b></span></label>` +
    l.map(x=>`<label class="ilcesatir"><input type="checkbox" data-i="${esc(x)}"${
      ILCELER.has(x)?" checked":""}><span>${esc(x)}</span></label>`).join("");
}

function ilceOzetGuncelle(){
  const n = ILCELER.size;
  $("#ilceOzet").textContent = n === 0 ? `Tüm ${IL.ad}`
    : n === 1 ? [...ILCELER][0]
    : `${n} ilçe seçili`;
  ILCE = n === 1 ? [...ILCELER][0] : "";   // adres çubuğu için
}

/* Panel açılıp kapanması — sade tutuluyor.
   Önce geri tuşu için history.pushState/back kullanılmıştı; gerçek
   cihazda "Tamam"a basınca panel kapanmıyor, liste güncellenmiyordu.
   Tarayıcı geçmişine dokunmak fayda sağlamadı, kaldırıldı. */
function ilcePanelAc(){
  const m = $("#ilceMenu");
  /* Panel .yapiskan bloğunun içindeydi. O blok position:sticky +
     z-index taşıdığı için KENDİ katman bağlamını kuruyor ve panelin
     z-index'i dışarıdaki sekme şeridiyle kıyaslanmıyordu: panelin üst
     şeridi (Temizle/Tamam) şeridin arkasında kalıyordu.
     Açarken doğrudan <body>'ye taşıyoruz — sorun kökten bitiyor. */
  if(m.parentElement !== document.body) document.body.appendChild(m);
  m.hidden = false;
  $("#ilceAc").setAttribute("aria-expanded", "true");
  document.body.classList.add("ilcepanel");
  if(window.innerWidth > 620) $("#ilceAra").focus();
}

function ilcePanelKapat(){
  $("#ilceMenu").hidden = true;
  $("#ilceAc").setAttribute("aria-expanded", "false");
  document.body.classList.remove("ilcepanel");
  // Kapanırken listeyi her hâlükârda tazele: seçim onchange ile
  // uygulanıyor olsa da burada da çağırmak güvenli.
  ilceOzetGuncelle();
  cizMarka();
}

$("#ilceAc").onclick = e => {
  e.preventDefault(); e.stopPropagation();
  if($("#ilceMenu").hidden) ilcePanelAc(); else ilcePanelKapat();
};
$("#ilceOrtu").onclick = () => ilcePanelKapat();
$("#ilceAra").oninput = ilceListesiCiz;
$("#ilceListesi").onchange = e => {
  const k = e.target;
  if(k.id === "ilceHepsi"){
    ILCELER.clear();
  } else if(k.dataset.i){
    if(k.checked) ILCELER.add(k.dataset.i); else ILCELER.delete(k.dataset.i);
  } else return;
  ilceListesiCiz(); ilceOzetGuncelle(); cizMarka();
};
$("#ilceTemizle").onclick = e => {
  e.preventDefault(); e.stopPropagation();
  ILCELER.clear(); ilceListesiCiz(); ilceOzetGuncelle(); cizMarka();
};
$("#ilceUygula").onclick = e => {
  e.preventDefault(); e.stopPropagation();
  ilcePanelKapat();
};
// Dışına tıklayınca kapansın (masaüstü)
document.addEventListener("click", e => {
  // Panel artık <body> altında; .ilcekutu içinde değil.
  if(e.target.closest(".ilcekutu") || e.target.closest(".ilcemenu")) return;
  if(!$("#ilceMenu").hidden) ilcePanelKapat();
});

/* ---------- kayıt kartı ---------- */
function kayitHtml(x, no, duzenlenebilir=false){
  const sn=ROL_SINIF[x[B_ROL]];
  const ix = duzenlenebilir
    ? D.bayiler.filter(y=>y[B_MARKA]===x[B_MARKA]).indexOf(x) : -1;
  return `<div class="kayit ${sn} ${x[B_DURUM]!=="Güncel"?"eski":""}${
      duzenlenebilir?" duzenlenebilir":""}"${ix>=0?` data-i="${ix}"`:""}>
    <div class="k1">${no?`<span class="sirano kno">${no}</span>`:""}${
      x[B_KOD]?`<span class="carikod" title="Cari kod">${esc(x[B_KOD])}</span>`:""}<span class="kad">${esc(x[B_AD])}</span>${
      duzenlenebilir?'<span class="dzip">düzenlemek için dokun</span>':""}
      <span class="rol ${sn}">${esc(ROL_AD[x[B_ROL]]||"")}</span>
      ${x[B_DURUM]!=="Güncel"?`<span class="rol" style="background:var(--uyari-z);color:var(--uyari);border-color:#F0D9B5">${esc(x[B_DURUM])}</span>`:""}
    </div>
    <div class="k2">${esc(x[B_ADRES])}${x[B_ADRES]?" · ":""}<span class="ilcerz">${
      esc([x[B_ILCE],x[B_IL]].filter(Boolean).filter((v,i,a)=>a.indexOf(v)===i).join(" / "))}</span></div>
    ${(()=>{const d=digerMarkalar(x); return d.length
      ? `<div class="k4"><span class="dmet">Çalıştığı markalar:</span>${
          d.map((m,i)=>`<button class="dmarka${i===0?" bumarka":""}" data-git="${esc(m)}">${esc(m)}</button>`).join("")}</div>`
      : "";})()}
    <div class="k3">
      <span class="tel">${x[B_TEL]?`<a href="tel:${esc(x[B_TEL].replace(/\s/g,""))}">${esc(x[B_TEL])}</a>`:"—"}</span>
      ${x[B_GIRIS]?`<a class="giris" href="${esc(x[B_GIRIS])}" target="_blank" rel="noopener">Marka sayfasına git ↗</a>`:""}
    </div></div>`;
}

/* ================= VERİM EKRANI (Satış / Bayi) =================
   Her il için: kaç nokta var, o ilde kaç motosiklet satılmış ve
   nokta başına kaç adet düşüyor. Satış adetleri TÜİK verisi;
   nokta sayıları bizim veritabanımızdan ve FİRMA bazlı (aynı firma
   birden çok markaya bayilik yapsa da bir kez sayılır).

   2026 rakamı 31.07 itibarıyla, yıl tamamlanmadı — kıyaslarken
   ayrı değerlendirilmeli, bu yüzden ekranda ayrıca işaretleniyor. */
let VERIM_ROL = "satis";

/* 153.438 gibi sayılar dar sütuna sığmayıp kırpılıyordu ("11.…").
   Bin ve milyon kısaltmasıyla tek bakışta okunur hale getiriyoruz.
   Tam değer, satırın title'ında ve Excel çıktısında duruyor. */
function kisa(n){
  n = n || 0;
  if (n >= 1000000) return (n/1000000).toFixed(1).replace(".",",") + "M";
  if (n >= 10000)   return Math.round(n/1000) + "B";
  if (n >= 1000)    return (n/1000).toFixed(1).replace(".",",") + "B";
  return String(n);
}

function verimVeri(){
  const sat = (D.il_satis && D.il_satis.iller) || {};
  const alan = VERIM_ROL === "satis" ? "satisNoktasi" : "servisNoktasi";
  return D.iller.map(i => {
    const c = tekilSay(D.bayiler.filter(b => b[B_IL] === i.ad));
    const nokta = c[alan] || 0;
    const s = sat[i.ad] || {};
    const o = {ad: i.ad, plaka: i.plaka, nokta,
               "2023": s["2023"]||0, "2024": s["2024"]||0,
               "2025": s["2025"]||0, "2026": s["2026"]||0};
    ["2023","2024","2025","2026"].forEach(y =>
      o["v"+y] = nokta ? Math.round(o[y] / nokta) : 0);
    return o;
  }).filter(x => x.nokta > 0 || x["2024"] > 0);
}

function cizVerim(){
  const q = kat($("#araVerim").value);
  let l = verimVeri().filter(x => !q || kat(x.ad).includes(q) || x.plaka.startsWith(q));

  const d = SIRA_DURUM["verimListe"] || {anahtar:"v2025", yon:-1};
  if(d.anahtar === "ad")
    l.sort((a,b)=>(d.yon<0?-1:1)*a.ad.localeCompare(b.ad,"tr"));
  else
    l.sort((a,b)=>{
      const fa=a[d.anahtar]||0, fb=b[d.anahtar]||0;
      return (d.yon<0 ? fb-fa : fa-fb) || a.ad.localeCompare(b.ad,"tr");
    });

  const etiket = VERIM_ROL === "satis" ? "bayi" : "servis";
  $("#verimBaslik").textContent = VERIM_ROL === "satis"
    ? "Bayi başına yıllık satış" : "Servis başına yıllık satış";
  // Sütun başlığı hangi noktaya göre hesaplandığını açıkça söylesin.
  // Servis kipinde SADECE servis değil, TOPLAM servis noktası
  // (sadece servis + bayi ve servis) kullanılıyor.
  const nb = $("#verimNoktaBas");
  if(nb) nb.innerHTML = VERIM_ROL === "satis"
    ? "Toplam<br>satış nok." : "Toplam<br>servis nok.";

  const topN = l.reduce((a,x)=>a+x.nokta,0);
  const top24 = l.reduce((a,x)=>a+x["2024"],0);
  const top25 = l.reduce((a,x)=>a+x["2025"],0);
  const top26 = l.reduce((a,x)=>a+x["2026"],0);
  $("#verimNot").innerHTML =
    `<b>${bicim(topN)}</b> ${etiket} noktası (ili belirli olanlar) · ` +
    `2024'te <b>${bicim(top24)}</b>, ` +
    `2025'te <b>${bicim(top25)}</b> motosiklet satıldı · ` +
    `Türkiye ortalaması ${etiket} başına <b>${topN?Math.round(top24/topN):0}</b> adet/yıl (2024), ` +
    `<b>${topN?Math.round(top25/topN):0}</b> (2025), ` +
    `<b>${topN?Math.round(top26/topN):0}</b> adet (2026* — 7 aylık). ` +
    `<span style="color:var(--celik)">Satış adetleri TÜİK. ` +
    `<b>*2026 rakamı 31.07 itibarıyladır</b>, yıl tamamlanmadığı için ` +
    `diğer yıllarla doğrudan kıyaslanamaz.</span>`;

  $("#verimBos").style.display = l.length ? "none" : "block";
  $("#verimListe").innerHTML = l.map((x,ix)=>`
    <button class="sat" data-il="${esc(x.ad)}">
      <span class="sirano">${ix+1}</span>
      <span class="govde"><span class="ustsatir"><span class="ad">${esc(x.ad)}</span>
        <span class="men">${x.plaka}</span></span></span>
      <span class="sag">
        <span class="sayi k">${bicim(x.nokta)}</span>
        <span class="sayi k" title="${bicim(x["2024"])}">${kisa(x["2024"])}</span>
        <span class="sayi k" style="color:var(--satis)">${bicim(x.v2024)}</span>
        <span class="sayi k" title="${bicim(x["2025"])}">${kisa(x["2025"])}</span>
        <span class="sayi k" style="color:var(--satis)">${bicim(x.v2025)}</span>
        <span class="sayi k" title="${bicim(x["2026"])}">${kisa(x["2026"])}</span>
        <span class="sayi k gen vurgu">${bicim(x.v2026)}</span>
        <span class="ok">›</span></span></button>`).join("");
  basligiIsaretle("verimListe");
  // Alt çubuk BU EKRANDA gösterilmiyor. Süzülmüş veri gönderilince
  // "Sadece servis: 0" gibi anlamsız sayılar çıkıyordu; ekranın kendi
  // özet satırı zaten doğru toplamları veriyor.
}

/* ================= FİRMA EKRANI (Bayiler / Servisler) =================
   Marka merkezli değil FİRMA merkezli görünüm. Aynı cari kod = aynı
   fiziksel firma; kaç markaya bayilik/servislik yaptığı tek satırda.
   5200 bayi / 5393 servis kartı var, hepsini birden çizmek telefonda
   ~1 sn sürüyor; bu yüzden 150'şer kademeli çiziliyor. */
const FIRMA_SAYFA = 150;
let FIRMA_ROL = "satis";     // "satis" | "servis"
let FIRMA_LIMIT = FIRMA_SAYFA;

const FIRMALAR = (() => {
  const g = new Map();
  D.bayiler.forEach(b => {
    const k = b[B_KOD] || ("x|" + b[B_AD] + "|" + b[B_IL] + "|" + b[B_ILCE]);
    let o = g.get(k);
    if (!o) {
      o = {kod: b[B_KOD] || "", ad: b[B_AD], il: b[B_IL], ilce: b[B_ILCE],
           adres: b[B_ADRES], tel: b[B_TEL],
           satis: new Set(), servis: new Set()};
      g.set(k, o);
    }
    // En uzun ad genelde tam ticari unvan
    if ((b[B_AD] || "").length > o.ad.length) o.ad = b[B_AD];
    if ((b[B_ADRES] || "").length > (o.adres || "").length) o.adres = b[B_ADRES];
    const r = b[B_ROL];
    if (r === "satis" || r === "satis_servis") o.satis.add(b[B_MARKA]);
    if (r === "servis" || r === "satis_servis") o.servis.add(b[B_MARKA]);
  });
  return [...g.values()];
})();

function firmaSuzgec(){
  const q = kat($("#araFirma").value);
  const alan = FIRMA_ROL === "satis" ? "satis" : "servis";
  let l = FIRMALAR.filter(f => f[alan].size > 0);
  if (q) l = l.filter(f => kat(
      f.ad + " " + f.il + " " + f.ilce + " " + [...f.satis, ...f.servis].join(" ")
    ).includes(q));
  // Çok markalı firmalar üstte; sonra alfabetik
  return l.sort((a, b) => b[alan].size - a[alan].size ||
                          a.ad.localeCompare(b.ad, "tr"));
}

function firmaKart(f, no){
  const bu   = FIRMA_ROL === "satis" ? f.satis : f.servis;
  const oteki= FIRMA_ROL === "satis" ? f.servis : f.satis;
  const etiket = FIRMA_ROL === "satis" ? "Bayilik" : "Servislik";
  const oEtiket= FIRMA_ROL === "satis" ? "Ayrıca servis:" : "Ayrıca bayi:";
  const sirala = x => [...x].sort((a,b)=>a.localeCompare(b,"tr"));
  const rozet = m => `<button class="dmarka" data-git="${esc(m)}">${esc(m)}</button>`;
  const dis = sirala(oteki).filter(m => !bu.has(m));
  return `<div class="kayit ${FIRMA_ROL==="satis"?"satis":"servis"}">
    <div class="k1"><span class="sirano kno">${no}</span>${
      f.kod?`<span class="carikod" title="Cari kod">${esc(f.kod)}</span>`:""}
      <span class="kad">${esc(f.ad)}</span>
      <span class="rol ${FIRMA_ROL==="satis"?"satis":"servis"}">${etiket} ${bu.size}</span>
    </div>
    <div class="k2">${esc(f.adres||"")}${f.adres?" · ":""}<span class="ilcerz">${
      esc([f.ilce,f.il].filter(Boolean).filter((v,i,a)=>a.indexOf(v)===i).join(" / "))}</span></div>
    <div class="k4"><span class="dmet">${etiket}:</span>${sirala(bu).map(rozet).join("")}</div>
    ${dis.length?`<div class="k4"><span class="dmet">${oEtiket}</span>${dis.map(rozet).join("")}</div>`:""}
    <div class="k3"><span class="tel">${f.tel?
      `<a href="tel:${esc(f.tel.replace(/\s/g,""))}">${esc(f.tel)}</a>`:"—"}</span></div>
  </div>`;
}

function cizFirma(){
  const l = firmaSuzgec();
  const alan = FIRMA_ROL === "satis" ? "satis" : "servis";
  $("#firmaBaslik").textContent = FIRMA_ROL === "satis" ? "Bayiler" : "Servisler";
  const cok = l.filter(f => f[alan].size > 1).length;
  $("#firmaNot").innerHTML =
    `<b>${bicim(l.length)}</b> firma · <b>${bicim(cok)}</b> tanesi birden çok ` +
    `markaya ${FIRMA_ROL==="satis"?"bayilik":"servislik"} yapıyor`;
  $("#firmaBos").style.display = l.length ? "none" : "block";

  const goster = l.slice(0, FIRMA_LIMIT);
  $("#firmaListe").innerHTML = goster.map((f,i)=>firmaKart(f,i+1)).join("");
  const d = $("#btnDahaFirma");
  d.style.display = l.length > FIRMA_LIMIT ? "inline-block" : "none";
  d.textContent = `Daha fazla göster (${bicim(l.length - FIRMA_LIMIT)} firma daha)`;
  altOzetGuncelle(FIRMA_ROL === "satis" ? "Bayiler" : "Servisler",
                  D.bayiler.filter(b => FIRMA_ROL === "satis"
                    ? (b[B_ROL]==="satis"||b[B_ROL]==="satis_servis")
                    : (b[B_ROL]==="servis"||b[B_ROL]==="satis_servis")));
}

/* ---------- ilin markaları ---------- */
function bolgeVeri(){
  return D.bayiler.filter(b => b[B_IL]===IL.ad &&
    (ILCELER.size === 0 || ILCELER.has(b[B_ILCE])));
}
function cizMarka(){
  const tum=bolgeVeri();
  altOzetGuncelle(IL ? (IL.ad + (ILCE ? " / " + ILCE : "")) : "Türkiye geneli", tum);
  rolSuzgecCiz("#rolSuzgec", tum);
  const q=kat($("#araMarka").value);
  const l=D.markalar.filter(m=>!q||kat(m.ad+" "+m.alan).includes(q));

  let mSira=0;
  $("#markaListe").innerHTML=l.map(m=>{
    const bs=tum.filter(x=>x[B_MARKA]===m.ad && rolGecer(x));
    // O ilde noktası olmayan markayı listeleme. Önceden marka sitesine
    // giden bir bağlantı olarak yine de gösteriliyordu; liste kalabalık
    // görünüyor ve "bu ilde bayisi var" izlenimi veriyordu.
    if(!bs.length) return "";
    const acik=ACIK.has(m.ad);
    const s=bs.filter(x=>x[B_ROL]!=="servis").length, v=bs.filter(x=>x[B_ROL]!=="satis").length;
    mSira++;
    return `<button class="sat" data-m="${esc(m.ad)}">
        <span class="sirano">${mSira}</span>
        <span class="ad">${esc(m.ad)}</span>
        <span class="sag">
          ${s?`<span class="rol satis">${s} satış</span>`:""}
          ${v?`<span class="rol servis">${v} servis</span>`:""}
          <span class="sayi">${bs.length}</span>
          <span class="ok">${acik?"⌄":"›"}</span></span></button>`
      + (acik?bs.map(kayitHtml).join(""):"");
  }).join("");

  const gorunen=tum.filter(rolGecer);
  $("#markaBos").style.display=gorunen.length?"none":"block";
  $("#ustbar").style.display=VAR_VERI&&tum.length?"flex":"none";
  yazdirBilgiGuncelle(`${IL.ad}${ILCE?" / "+ILCE:""}`, gorunen.length);
}
const ACIK=new Set();
$("#markaListe").onclick=e=>{
  const b=e.target.closest("button.sat"); if(!b) return;
  const m=b.dataset.m; ACIK.has(m)?ACIK.delete(m):ACIK.add(m); cizMarka();
};
let z2; $("#araMarka").oninput=()=>{clearTimeout(z2);z2=setTimeout(cizMarka,110);};
rolBagla("#rolSuzgec", cizMarka);

$("#kopyala").onclick=async()=>{
  try{await navigator.clipboard.writeText(IL.ad);$("#kopyala").textContent="Kopyalandı ✓";}
  catch{$("#kopyala").textContent="Kopyalanamadı";}
  setTimeout(()=>$("#kopyala").textContent="İl adını kopyala",1700);
};

/* ---------- marka özeti ---------- */
const OZET=(()=>{
  const o={};
  D.markalar.forEach(m=>o[m.ad]={ad:m.ad,alan:m.alan,bayi_link:m.bayi,
    satis_kaynak:m.satis_kaynak||"", servis_kaynak:m.servis_kaynak||"",
    elle:!!m.elle,
    site:m.site,tazelik:m.tazelik||"",satis:0,servis:0,ikisi:0,toplam:0,
    iller:new Set(),ilceler:new Set()});
  D.bayiler.forEach(b=>{const x=o[b[B_MARKA]]; if(!x)return;
    x.toplam++; x[ROL_SINIF[b[B_ROL]]]++;
    if(b[B_IL])x.iller.add(b[B_IL]);
    if(b[B_ILCE])x.ilceler.add(b[B_IL]+"/"+b[B_ILCE]);});
  // Excel çıktısı markaya göre kaynak adresi arıyor; sözlüğü de tut.
  window.OZET_SOZ = o;
  return Object.values(o);
})();
$("#mrkSirala").onclick = e => {
  const b=e.target.closest("button"); if(!b) return;
  SIRA=b.dataset.s;
  [...$("#mrkSirala").querySelectorAll("button")].forEach(x=>
    x.classList.toggle("secili", x===b));
  cizTum();
};
function cizTum(){
  const q=kat($("#araTum").value);
  let l=OZET.filter(m=>!q||kat(m.ad+" "+m.alan).includes(q));
  // Sütun başlığından sıralama (Excel gibi). Üstteki düğmeler de çalışır.
  const ol={sayi:m=>m.toplam, toplam:m=>m.toplam,
            satis:m=>m.satis+m.ikisi, servis:m=>m.servis+m.ikisi,
            yalnizSatis:m=>m.satis, yalnizServis:m=>m.servis,
            ikisi:m=>m.ikisi, satisNoktasi:m=>m.satis+m.ikisi,
            servisNoktasi:m=>m.servis+m.ikisi};
  const bd = SIRA_DURUM["tumListe"] || null;
  const anahtar = bd ? bd.anahtar : SIRA;
  const yon = bd ? bd.yon : -1;
  l = anahtar in ol
      ? [...l].sort((a,b)=>(yon<0 ? ol[anahtar](b)-ol[anahtar](a)
                                         : ol[anahtar](a)-ol[anahtar](b))
                            || a.ad.localeCompare(b.ad,"tr"))
      : [...l].sort((a,b)=>(anahtar==="ad"?(yon<0?-1:1):1)*a.ad.localeCompare(b.ad,"tr"));
  basligiIsaretle("tumListe");
  $("#tumBos").style.display=l.length?"none":"block";
  $("#tumListe").innerHTML=l.map((m,ix)=>{
    const t=m.toplam>0;
    const ic=`<span class="sirano">${ix+1}</span><span class="ad">${esc(m.ad)}</span>
      <span class="sag">
        <span class="sayi k ${m.satis?"":"yok"}" style="color:var(--satis)">${m.satis||"—"}</span>
        <span class="sayi k ${m.servis?"":"yok"}" style="color:var(--servis)">${m.servis||"—"}</span>
        <span class="sayi k ${m.ikisi?"":"yok"}" style="color:var(--ikisi)">${m.ikisi||"—"}</span>
        <span class="sayi k gen vurgu ${(m.satis+m.ikisi)?"":"yok"}">${(m.satis+m.ikisi)||"—"}</span>
        <span class="sayi k gen vurguserv ${(m.servis+m.ikisi)?"":"yok"}">${(m.servis+m.ikisi)||"—"}</span>
        <span class="sayi k ${t?"":"yok"}" style="font-weight:700">${m.toplam||"—"}</span>
        <span class="ok">${t?"›":"↗"}</span></span>`;
    return t?`<button class="sat" data-m="${esc(m.ad)}">${ic}</button>`
            :`<a class="sat" href="${esc(m.bayi_link||m.site)}" target="_blank" rel="noopener">${ic}</a>`;
  }).join("");
  yazdirBilgiGuncelle("Marka listesi", l.length);
}
let z3; $("#araTum").oninput=()=>{clearTimeout(z3);z3=setTimeout(cizTum,110);};
$("#tumListe").onclick=e=>{const b=e.target.closest("button.sat"); if(b) markaAc(b.dataset.m);};

/* ---------- marka detayı ---------- */
function markaAc(ad){
  MD=OZET.find(m=>m.ad===ad); if(!MD)return;
  ROL="tum"; $("#mdAd").textContent=ad; cizMD(); ekran("vMarkaDetay");
}
function cizMD(){
  const tum=D.bayiler.filter(x=>x[B_MARKA]===MD.ad);
  rolSuzgecCiz("#mdRolSuzgec", tum);
  const b=tum.filter(rolGecer);
  const c=sayRol(tum);
  $("#mdOzet").innerHTML =
    `Sadece satış <b>${MD.satis}</b> · sadece servis <b>${MD.servis}</b> · `
    + `satış+servis <b>${MD.ikisi}</b><br>`
    + `Satış yapan toplam <b>${c.satis}</b> · servis veren toplam <b>${c.servis}</b> · `
    + `nokta sayısı <b>${tum.length}</b> · ${MD.iller.size} il · ${MD.ilceler.size} ilçe`
    + (MD.tazelik&&MD.tazelik!=="Güncel"?` · ${MD.tazelik}`:"");
  const g={};
  b.forEach(x=>(g[x[B_IL]||"— il bilinmiyor —"]||=[]).push(x));
  const dzn = !!MD.elle;
  $("#mdElleBar").style.display = dzn ? "flex" : "none";
  $("#mdListe").innerHTML=Object.keys(g).sort((a,c)=>a.localeCompare(c,"tr")).map(il=>
    `<div class="baslikcubuk"><span>${esc(il)}</span>
       <span class="sagb">${g[il].length} nokta</span></div>`+
    g[il].map((x,ix)=>kayitHtml(x,ix+1,dzn)).join("")).join("");
  yazdirBilgiGuncelle(MD.ad, b.length);
  altOzetGuncelle(MD.ad, tum);
}
rolBagla("#mdRolSuzgec", cizMD);

/* ---------- elle girilen markalarda düzeltme ----------
   Bu markalar taranmıyor (siteleri erişilemiyor), veri elle
   giriliyor. Kullanıcı kaydı düzeltebilsin diye basit bir düzenleme
   ekranı var. Sayfa statik olduğu için değişiklikler TARAYICIDA
   saklanıyor; kalıcı olması için "Düzeltmeleri indir" ile alınan
   JSON'un elle/<marka>.json dosyasına konması gerekiyor. */
const DZ_ANAHTAR = "bayiradar-duzeltme";
let DUZELTME = {};
try { DUZELTME = JSON.parse(localStorage.getItem(DZ_ANAHTAR) || "{}"); }
catch(e){ DUZELTME = {}; }

function dzKimlik(x){ return x[B_MARKA] + "|" + x[B_AD] + "|" + x[B_IL]; }

function duzeltmeleriUygula(){
  D.bayiler.forEach(x=>{
    const d = DUZELTME[dzKimlik(x)];
    if(!d) return;
    if(d.ad!==undefined)    x[B_AD]=d.ad;
    if(d.tel!==undefined)   x[B_TEL]=d.tel;
    if(d.il!==undefined)    x[B_IL]=d.il;
    if(d.ilce!==undefined)  x[B_ILCE]=d.ilce;
    if(d.adres!==undefined) x[B_ADRES]=d.adres;
    if(d.rol!==undefined)   x[B_ROL]=d.rol;
  });
}

let DZ_HEDEF=null;
function duzenleAc(x){
  DZ_HEDEF=x;
  $("#dzAd").value=x[B_AD]||""; $("#dzTel").value=x[B_TEL]||"";
  $("#dzIl").value=x[B_IL]||""; $("#dzIlce").value=x[B_ILCE]||"";
  $("#dzAdres").value=x[B_ADRES]||""; $("#dzMail").value="";
  $("#dzRol").value=x[B_ROL]||"satis_servis";
  $("#duzenleOrtu").style.display="flex";
}
function duzenleKapat(){ $("#duzenleOrtu").style.display="none"; DZ_HEDEF=null; }

/* Düzenleme penceresi </body> hemen öncesinde; bu betik ondan ÖNCE
   çalıştığı için öğeler henüz yok. Bağlamaları DOM hazır olunca yap. */
function dzBagla(){
  if(!$("#dzIptal")) return;
  $("#dzIptal").onclick=duzenleKapat;
  $("#duzenleOrtu").onclick=e=>{ if(e.target.id==="duzenleOrtu") duzenleKapat(); };
  $("#dzKaydet").onclick=dzKaydet;
}
function dzHazir(){
  dzBagla();
  if(AO_SON) altOzetGuncelle(AO_SON[0], AO_SON[1]);
}
if(document.readyState==="loading")
  document.addEventListener("DOMContentLoaded", dzHazir);
else dzHazir();

function dzKaydet(){
  if(!DZ_HEDEF) return;
  const k=dzKimlik(DZ_HEDEF);
  DUZELTME[k]={ad:$("#dzAd").value.trim(), tel:$("#dzTel").value.trim(),
    il:$("#dzIl").value.trim(), ilce:$("#dzIlce").value.trim(),
    adres:$("#dzAdres").value.trim(), rol:$("#dzRol").value};
  try{ localStorage.setItem(DZ_ANAHTAR, JSON.stringify(DUZELTME)); }catch(e){}
  duzeltmeleriUygula();
  duzenleKapat();
  cizMD();
}

/* "Bu bayi ayrıca" rozetine tıklayınca o markanın sayfasına git */
document.addEventListener("click", e=>{
  const d = e.target.closest(".dmarka");
  if(!d) return;
  e.stopPropagation();
  markaAc(d.dataset.git);
});

$("#mdListe").addEventListener("click", e=>{
  if(!MD || !MD.elle) return;
  const kutu=e.target.closest(".kayit.duzenlenebilir"); if(!kutu) return;
  const i=+kutu.dataset.i;
  const x=D.bayiler.filter(y=>y[B_MARKA]===MD.ad)[i];
  if(x) duzenleAc(x);
});

$("#btnElleSifirla").onclick=()=>{
  DUZELTME={};
  try{ localStorage.removeItem(DZ_ANAHTAR); }catch(e){}
  location.reload();
};

$("#btnElleDisa").onclick=()=>{
  const kayitlar=D.bayiler.filter(x=>x[B_MARKA]===MD.ad).map(x=>({
    marka:x[B_MARKA], rol:x[B_ROL], bayi_adi:x[B_AD], il:x[B_IL],
    ilce:x[B_ILCE], adres:x[B_ADRES], telefon:x[B_TEL],
    email:"", website:""}));
  const veri={_aciklama:`${MD.ad} — sayfadaki düzenleme ekranından alındı.`,
    _kaynak:[MD.satis_kaynak||MD.site||""], _tarih:new Date().toISOString().slice(0,10),
    _duzenlenebilir:true, kayitlar};
  const b=new Blob([JSON.stringify(veri,null,1)],{type:"application/json"});
  const a=document.createElement("a");
  a.href=URL.createObjectURL(b);
  a.download=kat(MD.ad).replace(/ /g,"-")+".json";
  a.click(); URL.revokeObjectURL(a.href);
};

duzeltmeleriUygula();

function yazdirBilgiGuncelle(baslik, adet){
  const et={tum:"tümü",satis:"sadece satış",servis:"sadece servis",ikisi:"satış + servis"};
  $("#yazdirBilgi").textContent =
    `${baslik} · ${adet} kayıt · ${et[ROL]} · ${$("#veriTarih").textContent}`;
}

/* ================= DIŞA AKTARMA ================= */
/* Excel sütunları. Cari kod EN BAŞTA: aynı firma birden çok markada
   geçiyor, koda göre eşleştirme yapılabilsin.
   Kaynak adresleri satış ve servis olarak AYRI iki sütun. */
const BASLIK=["Cari Kod","Marka","Ünvan / Bayi Adı","Rol","İl","İlçe","Adres",
              "Telefon","Veri Durumu","Satış Kaynak Adresi","Servis Kaynak Adresi",
              "Marka Sayfası"];
const EN=[{wch:10},{wch:16},{wch:38},{wch:14},{wch:14},{wch:16},{wch:50},{wch:16},
          {wch:14},{wch:52},{wch:52},{wch:40}];
const MK = ad => (window.OZET_SOZ && window.OZET_SOZ[ad]) || {};
const satirDisa = x => {
  const m = MK(x[B_MARKA]);
  return [x[B_KOD]||"", x[B_MARKA], x[B_AD], ROL_AD[x[B_ROL]]||"", x[B_IL],
          x[B_ILCE], x[B_ADRES], x[B_TEL], x[B_DURUM],
          m.satis_kaynak||"", m.servis_kaynak||"", x[B_GIRIS]];
};

async function xlsxYukle(){
  if(window.XLSX) return true;
  return new Promise(ok=>{const s=document.createElement("script");
    s.src="https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js";
    s.onload=()=>ok(true); s.onerror=()=>ok(false); document.head.appendChild(s);});
}
function sayfaEkle(wb,ad,satirlar,gen){
  const ws=XLSX.utils.aoa_to_sheet(satirlar);
  ws["!cols"]=gen; ws["!freeze"]={xSplit:0,ySplit:1};
  XLSX.utils.book_append_sheet(wb,ws,ad.replace(/[\\\/\?\*\[\]:]/g,"-").slice(0,31));
}
function dosyaAdi(k,uz){
  const d=new Date(),p=n=>String(n).padStart(2,"0");
  return `${k}-${d.getFullYear()}${p(d.getMonth()+1)}${p(d.getDate())}.${uz}`;
}
function indir(blob,ad){
  const u=URL.createObjectURL(blob),a=document.createElement("a");
  a.href=u;a.download=ad;a.click();setTimeout(()=>URL.revokeObjectURL(u),1500);
}
function rolOzeti(veri){
  const s=[["Rol","Nokta Sayısı"]];
  const c={satis:0,servis:0,satis_servis:0};
  veri.forEach(b=>c[b[B_ROL]]++);
  s.push(["Sadece satış",c.satis],["Sadece servis",c.servis],
         ["Satış + Servis (kesişim)",c.satis_servis],[],
         ["TOPLAM SATIŞ NOKTASI",c.satis+c.satis_servis],
         ["TOPLAM SERVİS NOKTASI",c.servis+c.satis_servis],[],
         ["TOPLAM NOKTA",veri.length]);
  return s;
}

async function excelIndir(kap,btn){
  const eski=btn?btn.textContent:"";
  if(btn){btn.disabled=true;btn.textContent="Hazırlanıyor…";}
  if(!(await xlsxYukle())){
    if(btn){btn.textContent="İnternet gerekiyor";
      setTimeout(()=>{btn.textContent=eski;btn.disabled=false;},2500);}
    return;
  }
  const wb=XLSX.utils.book_new();
  let veri,ad;
  if(kap.tip==="marka"){
    veri=D.bayiler.filter(b=>b[B_MARKA]===kap.ad);
    ad=`${kat(kap.ad).replace(/ /g,"-")}-bayi-servis`;
    sayfaEkle(wb,"Rol Özeti",rolOzeti(veri),[{wch:22},{wch:14}]);
    const s={};veri.forEach(b=>s[b[B_IL]||"—"]=(s[b[B_IL]||"—"]||0)+1);
    const k=[["İl","Nokta Sayısı"]];
    Object.entries(s).sort((a,b)=>b[1]-a[1]).forEach(([a,b])=>k.push([a,b]));
    k.push([],["TOPLAM",veri.length]);
    sayfaEkle(wb,"İl Kırılımı",k,[{wch:20},{wch:14}]);
  } else if(kap.tip==="bolge"){
    veri=D.bayiler.filter(b=>b[B_IL]===kap.il&&(!kap.ilce||b[B_ILCE]===kap.ilce));
    ad=`${kat(kap.il).replace(/ /g,"")}${kap.ilce?"-"+kat(kap.ilce).replace(/ /g,""):""}-bayi-servis`;
    sayfaEkle(wb,"Rol Özeti",rolOzeti(veri),[{wch:22},{wch:14}]);
    const s={};veri.forEach(b=>{const m=b[B_MARKA];(s[m]||=[0,0,0]);
      s[m][b[B_ROL]==="satis"?0:b[B_ROL]==="servis"?1:2]++;});
    const k=[["Marka","Yalnız satış","Yalnız servis","Satış+Servis",
              "Toplam satış noktası","Toplam nokta"]];
    Object.entries(s).sort((a,b)=>(b[1][0]+b[1][1]+b[1][2])-(a[1][0]+a[1][1]+a[1][2]))
      .forEach(([m,v])=>k.push([m,v[0],v[1],v[2],v[0]+v[2],v[0]+v[1]+v[2]]));
    sayfaEkle(wb,"Marka Dağılımı",k,
      [{wch:22},{wch:12},{wch:13},{wch:13},{wch:20},{wch:12}]);
    if(!kap.ilce){
      const i={};veri.forEach(b=>{const x=b[B_ILCE]||"—";i[x]=(i[x]||0)+1;});
      const ik=[["İlçe","Nokta Sayısı","Marka Çeşidi"]];
      Object.entries(i).sort((a,b)=>b[1]-a[1]).forEach(([a,b])=>
        ik.push([a,b,new Set(veri.filter(x=>(x[B_ILCE]||"—")===a).map(x=>x[B_MARKA])).size]));
      sayfaEkle(wb,"İlçe Kırılımı",ik,[{wch:22},{wch:14},{wch:14}]);
    }
  } else if(kap.tip==="tum_iller"){
    veri=D.bayiler; ad="il-il-bayi-servis";
    const iller=[...new Set(veri.map(b=>b[B_IL]).filter(Boolean))].sort((a,b)=>a.localeCompare(b,"tr"));
    const o=[["İl","Yalnız satış","Yalnız servis","Satış+Servis",
              "Toplam satış noktası","Marka Çeşidi","İlçe","Toplam nokta"]];
    const say3=a=>[a.filter(b=>b[B_ROL]==="satis").length,
                   a.filter(b=>b[B_ROL]==="servis").length,
                   a.filter(b=>b[B_ROL]==="satis_servis").length];
    iller.forEach(il=>{const a=veri.filter(b=>b[B_IL]===il); const [x,y,z]=say3(a);
      o.push([il,x,y,z,x+z,new Set(a.map(b=>b[B_MARKA])).size,
        new Set(a.map(b=>b[B_ILCE]).filter(Boolean)).size,a.length]);});
    const [tx,ty,tz]=say3(veri);
    o.push([],["TOPLAM",tx,ty,tz,tx+tz,new Set(veri.map(b=>b[B_MARKA])).size,"",veri.length]);
    sayfaEkle(wb,"İl Özeti",o,
      [{wch:20},{wch:12},{wch:13},{wch:13},{wch:20},{wch:13},{wch:9},{wch:12}]);
    sayfaEkle(wb,"Tüm Kayıtlar",[BASLIK,...veri.map(satirDisa)],EN);
    iller.forEach(il=>{const a=veri.filter(b=>b[B_IL]===il);
      if(a.length) sayfaEkle(wb,il,[BASLIK,...a.map(satirDisa)],EN);});
    XLSX.writeFile(wb,dosyaAdi(ad,"xlsx"));
    if(btn){btn.textContent=eski;btn.disabled=false;} return;
  } else {
    veri=D.bayiler; ad="tum-turkiye-bayi-servis";
    const o=[["Marka","Sadece Satış","Sadece Servis","Satış+Servis",
              "Satış Yapan Toplam","Servis Veren Toplam","Nokta Sayısı",
              "İl","İlçe","Veri Durumu",
              "Satış Kaynak Adresi","Servis Kaynak Adresi","Marka Sitesi"]];
    [...OZET].sort((a,b)=>b.toplam-a.toplam||a.ad.localeCompare(b.ad,"tr")).forEach(m=>
      o.push([m.ad,m.satis,m.servis,m.ikisi,
              m.satis+m.ikisi, m.servis+m.ikisi, m.toplam,
              m.iller.size,m.ilceler.size,
              m.tazelik||(m.toplam?"Güncel":"Henüz taranmadı"),
              m.satis_kaynak||m.bayi_link||"", m.servis_kaynak||"", m.site||""]));
    const ts=veri.filter(b=>b[B_ROL]==="satis").length;
    const tv=veri.filter(b=>b[B_ROL]==="servis").length;
    const ti=veri.filter(b=>b[B_ROL]==="satis_servis").length;
    o.push([],["TOPLAM",ts,tv,ti,ts+ti,tv+ti,veri.length,
      new Set(veri.map(b=>b[B_IL]).filter(Boolean)).size,"","",""]);
    sayfaEkle(wb,"Marka Özeti",o,[{wch:20},{wch:13},{wch:13},{wch:13},{wch:20},
                                  {wch:20},{wch:12},{wch:7},{wch:8},{wch:16},
                                  {wch:46},{wch:46},{wch:32}]);
    sayfaEkle(wb,"Tüm Kayıtlar",[BASLIK,...veri.map(satirDisa)],EN);
    [...new Set(veri.map(b=>b[B_MARKA]))].sort((a,b)=>a.localeCompare(b,"tr")).forEach(m=>{
      const a=veri.filter(b=>b[B_MARKA]===m);
      if(a.length) sayfaEkle(wb,m,[BASLIK,...a.map(satirDisa)],EN);});
  }
  if(kap.tip!=="tum_iller"&&kap.tip!=="tum")
    sayfaEkle(wb,"Kayıtlar",[BASLIK,...veri.map(satirDisa)],EN);
  XLSX.writeFile(wb,dosyaAdi(ad,"xlsx"));
  if(btn){btn.textContent=eski;btn.disabled=false;}
}

/* HTML kaydet: sayfanın o anki halini tek dosya olarak indirir */
function htmlKaydet(etiket){
  const kopya=document.documentElement.cloneNode(true);
  kopya.querySelectorAll(".sek,.altbar,.ara").forEach(e=>e.remove());
  const blob=new Blob(["<!doctype html>\n"+kopya.outerHTML],
                      {type:"text/html;charset=utf-8"});
  indir(blob,dosyaAdi(kat(etiket).replace(/ /g,"-")||"liste","html"));
}

$("#btnXls").onclick      = e => excelIndir({tip:"bolge",il:IL.ad,ilce:ILCE},e.target);
$("#btnTumIlXls").onclick = e => excelIndir({tip:"tum_iller"},e.target);
$("#btnOzetXls").onclick  = e => excelIndir({tip:"tum"},e.target);
$("#btnMarkaXls").onclick = e => excelIndir({tip:"marka",ad:MD.ad},e.target);
$("#btnHtml").onclick      = () => htmlKaydet(IL.ad+(ILCE?"-"+ILCE:""));
$("#btnMarkaHtml").onclick = () => htmlKaydet(MD.ad);
$("#btnYaz").onclick=$("#btnMarkaYaz").onclick=$("#btnOzetYaz").onclick=()=>window.print();
$("#btnCsv").onclick=()=>{
  const b=bolgeVeri().filter(rolGecer);
  const csv=[BASLIK,...b.map(satirDisa)]
    .map(r=>r.map(c=>`"${String(c??"").replace(/"/g,'""')}"`).join(";")).join("\r\n");
  indir(new Blob(["\uFEFF"+csv],{type:"text/csv;charset=utf-8"}),
        dosyaAdi(kat(IL.ad).replace(/ /g,""),"csv"));
};

cizOzet();
ekran('vOzet', false);
try{ history.replaceState({ekran:'vOzet'},''); }catch(e){}
</script>
<div class="altozet" id="altOzet">
  <div class="aoust">
    <span class="baslik" id="aoBaslik">Türkiye geneli</span>
    <span class="aonot">Bayi birden çok marka ile çalışsa bile 1 işyeri
      1 adet sayıldı; Şubeler ayrı adresteyse ayrı işyeri olarak
      kabul edildi.</span>
  </div>
  <div class="satir">
    <span class="kutu toplamf"><b id="aoToplam">—</b><i>Satış+<br>Servis</i></span>
    <span class="kutu vurgu"><b id="aoSatisNok">—</b><i>Toplam<br>satış noktası</i></span>
    <span class="kutu"><b id="aoServisNok">—</b><i>Toplam<br>servis noktası</i></span>
    <span class="kutu"><b id="aoSatis">—</b><i>Sadece<br>bayi</i></span>
    <span class="kutu"><b id="aoServis">—</b><i>Sadece<br>servis</i></span>
    <span class="kutu"><b id="aoIkisi">—</b><i>Bayi ve<br>servis</i></span>
  </div>
</div>
<div class="ortu" id="duzenleOrtu" style="display:none">
  <div class="duzenle">
    <h3>Kaydı düzenle</h3>
    <label>Bayi adı<input id="dzAd" type="text"></label>
    <label>Telefon<input id="dzTel" type="text" inputmode="tel"></label>
    <label>İl<input id="dzIl" type="text"></label>
    <label>İlçe<input id="dzIlce" type="text"></label>
    <label>Adres<input id="dzAdres" type="text"></label>
    <label>E-posta<input id="dzMail" type="text" inputmode="email"></label>
    <label>Rol
      <select id="dzRol">
        <option value="satis">Satış</option>
        <option value="servis">Servis</option>
        <option value="satis_servis">Satış + Servis</option>
      </select>
    </label>
    <div class="dzbtn">
      <button class="btn ana" id="dzKaydet">Kaydet</button>
      <button class="btn" id="dzIptal">Vazgeç</button>
    </div>
  </div>
</div>
</body>
</html>
"""


if __name__ == "__main__":
    cikti = sys.argv[1] if len(sys.argv) > 1 else "site/index.html"
    yol, adet, markali = uret(cikti)
    print(f"✓ {yol}  ·  {adet} kayıt  ·  {markali} markada veri var")
