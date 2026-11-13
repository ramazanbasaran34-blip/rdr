#!/usr/bin/env python3
"""Sayfaların HAM HTTP gövdesini olduğu gibi kaydeder.

Neden ayrı bir betik: yakala.py tarayıcı DOM'unu kaydediyor ve <script>
etiketlerini siliyor (COP_ETIKET). Kuba, RKS, Kymco, BMW gibi sitelerde
bayi verisi sayfaya gömülü bir JS dizisinde duruyor — yani tam olarak
silinen yerde. Bu yüzden o markalarda yıllardır boş dosya kaydediliyordu.

Burada tarayıcı yok, JS yok, kırpma yok. Tek bir GET, gövde ne geldiyse o.
Saniyeler sürer.

    python hamyakala.py            # hepsi
    python hamyakala.py Kuba RKS   # seçili

Çıktı: ham/<ad>.<uzanti>.gz  +  ham/ozet.json
"""

from __future__ import annotations

import gzip
import json
import re
import sys
from pathlib import Path

import requests

CIKTI = Path("ham")

# Tarayıcı gibi görün: bazı sunucular çıplak istemciye kısa sayfa veriyor.
BASLIK = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
}

# ad -> (url, uzanti)
HEDEFLER: dict[str, tuple[str, str]] = {
    # --- verinin sayfaya gömülü olduğu düşünülenler ---
    "kuba":       ("https://www.kubamotor.com.tr/bayi-servis/kubamotor", "html"),
    "rks":        ("https://www.rksmotor.com.tr/bayi-servis/rksmotor.html", "html"),
    "rks-standart": ("https://www.rksmotor.com.tr/page/bayi-servis/standart-bayi-agi.html", "html"),
    "kymco":      ("https://www.kymco.com.tr/tr/satis-servis-agi.html", "html"),
    "bmw":        ("https://www.bmw-motorrad.com.tr/tr/ssl/yetkili-satici-ve-servisler.html", "html"),
    "leksas":     ("https://www.leksas.com.tr/bayi-servis/", "html"),
    "kimmi":      ("https://kimmimotor.com/servisler/", "html"),
    "csn":        ("https://csnmotor.com.tr/servis-noktalarimiz/", "html"),
    "taktas":     ("https://taktas.com.tr/servislerimiz", "html"),

    # --- doğrudan veri uçları (keşif raporundan) ---
    "nanok-api":  ("https://nanok.com.tr/api/dealers", "json"),
    "meka-maps":  ("https://www.mekamotor.com.tr/resman/uploads/maps.xml", "xml"),

    # --- Piaggio grubu: satış ve servis AYRI sayfalarda, ikisi de aynı
    #     gömülü GeoJSON yapısını kullanıyor (Kymco ile birebir aynı).
    "vespa-servis":   ("https://www.vespa.com.tr/tr/yetkili-servisler.html", "html"),
    "aprilia-servis": ("https://www.aprilia.com.tr/tr/yetkili-servisler.html", "html"),
    "piaggio-servis": ("https://www.piaggio.com.tr/tr/yetkili-servisler.html", "html"),
    "suzuki-servis":  ("https://www.suzuki.com.tr/tr/motosiklet/servis.html", "html"),

    # --- MJ Group: Kuba ve RKS'in sahibi, kendi sitelerinden link veriliyor.
    #     Kullanıcı onayıyla resmi kaynak kabul edildi (2026-08).
    "mj-kuba-bayi":   ("https://www.mj.com.tr/bayi-servis-agi/kuba-motor-bayi-agi/", "html"),
    "mj-kuba-servis": ("https://www.mj.com.tr/bayi-servis-agi/kuba-motor-servis-agi/", "html"),
    "mj-rks-bayi":    ("https://www.mj.com.tr/bayi-servis-agi/rks-motor-bayi-agi/", "html"),
    "mj-rks-servis":  ("https://www.mj.com.tr/bayi-servis-agi/rks-motor-servis-agi/", "html"),
    "mj-agi":         ("https://www.mj.com.tr/bayi-servis-agi/", "html"),
    # RKS menüsünden çıkan olası veri ucu
    "rks-services":   ("https://user.rksmotor.com.tr/services.php", "html"),


    # --- öncelikli 8 marka (keşif raporundan çıkan gerçek uçlar) ---
    # Falcon: tek JSON ucu, ülkenin tamamı
    "falcon-api":      ("https://falconmotosiklet.com/api/bayiler.php", "json"),
    # Musatti: il koduyla JSON (örnek il = 06 Ankara)
    "musatti-bayi06":  ("https://musattimotor.com/ajax-bayi-listesi.php?city=06", "json"),
    "musatti-srv06":   ("https://musattimotor.com/ajax-servis-listesi.php?city=06", "json"),
    # Kral: sayfada gömülü (435/469 telefon)
    "kral-satis":      ("https://kralmotor.tr/SalesDealer", "html"),
    "kral-servis":     ("https://kralmotor.tr/Service", "html"),
    # Vespa: sayfada gömülü (266/318)
    "vespa-satis":     ("https://www.vespa.com.tr/tr/yetkili-saticilar.html", "html"),
    "vespa-servis":    ("https://www.vespa.com.tr/tr/yetkili-servisler.html", "html"),
    # Suzuki: servis sayfası gömülü (298); satış ayrı yapı
    # DİKKAT: satis.html bayi listesi İÇERMİYOR (sadece test sürüşü metni).
    # Doğru adres yetkili-saticilar.html — kullanıcı bildirdi.
    "suzuki-satici":   ("https://www.suzuki.com.tr/tr/motosiklet/yetkili-saticilar.html", "html"),
    "suzuki-servis":   ("https://www.suzuki.com.tr/tr/motosiklet/yetkili-servisler.html", "html"),
    # Zelsun: ASP.NET, il URL parametresinde (örnek 34)
    "zelsun-satis34":  ("https://www.zelsunmotor.com/Bayilerimiz.aspx?sehir=%C4%B0STANBUL&ilce=%C4%B0l%C3%A7e%20Se%C3%A7iniz", "html"),
    "zelsun-srv34":    ("https://www.zelsunmotor.com/Servislerimiz.aspx?sehir=%C4%B0STANBUL&ilce=%C4%B0l%C3%A7e%20Se%C3%A7iniz", "html"),
    # CSN: satış zaten geliyor, servis eksik
    "csn-satis2":      ("https://csnmotor.com.tr/satis-noktalarimiz/", "html"),
    "csn-servis2":     ("https://csnmotor.com.tr/servis-noktalarimiz/", "html"),
    # CSN servis, il bağlantılarını /servis-noktalarimiz/<il> biçiminde veriyor;
    # satış ise düz /<il>. Sistem sadece ikinciyi tanıdığı için servis boş kalmıştı.
    "csn-srv-ankara":  ("https://csnmotor.com.tr/servis-noktalarimiz/ankara", "html"),
    "csn-sat-ankara":  ("https://csnmotor.com.tr/ankara", "html"),
    # CSN: il bazlı sayfa (örnek: Ankara)
    "csn-servis-ank":  ("https://csnmotor.com.tr/servis-noktalarimiz/ankara", "html"),
    "csn-satis-ank":   ("https://csnmotor.com.tr/satis-noktalarimiz/ankara", "html"),
    # Motolux: il bazlı tek liste (satış+servis birlikte)
    "motolux-adana":   ("https://motolux.com.tr/bayiler/sehir/adana/", "html"),
    "motolux-agri":    ("https://motolux.com.tr/bayiler/sehir/agri/", "html"),
    "motolux-izmir":   ("https://motolux.com.tr/bayiler/sehir/izmir/", "html"),
    # Hero: POST istiyor; önce GET ile yapıyı görelim
    "hero-satis":      ("https://www.heromotor.com.tr/bayiler/", "html"),
    "hero-servis":     ("https://www.heromotor.com.tr/servisler/", "html"),

    # --- kalan markalar ---
    "arnica-satis":    ("https://arnicamotor.com/bayiler?lang=tr", "html"),
    "arnica-servis":   ("https://arnicamotor.com/servisler?lang=tr", "html"),
    "kimmi-bayi":      ("https://www.kimmimotor.com/bayiler/", "html"),
    "kimmi-servis":    ("https://www.kimmimotor.com/servisler/", "html"),
    "leksas-bs":       ("https://www.leksas.com.tr/bayi-servis/", "html"),
    "taktas-bs":       ("https://taktas.com.tr/bayi-ve-servis", "html"),
    "taktas-servis2":  ("https://taktas.com.tr/servislerimiz", "html"),
    "meka-bs":         ("https://www.mekamotor.com.tr/bayi-ve-servis", "html"),
    "milyon-bs":       ("https://www.milyonmoto.com.tr/bayi-servisler.html", "html"),
    "isotlar-bayi":    ("https://www.isotlarmotor.com/bayiler/", "html"),
    # İsotlar: il seçeneklerinin değeri doğrudan URL; "Tüm İller" seçeneği var
    "isotlar-peugeot": ("https://www.isotlarmotor.com/bayiler/peugeot-motosiklet/", "html"),
    "isotlar-horwin":  ("https://www.isotlarmotor.com/bayiler/horwin-motosiklet/", "html"),
    "isotlar-lambretta": ("https://www.isotlarmotor.com/bayiler/lambretta-motosiklet/", "html"),
    # Arnica: sehir_id parametresi (1 = Adana)
    "arnica-bayi1":    ("https://arnicamotor.com/bayiler?lang=tr&sehir_id=1", "html"),
    "arnica-servis1":  ("https://arnicamotor.com/servisler?lang=tr&sehir_id=1", "html"),
    "nanok-sayfa":     ("https://nanok.com.tr/bayilerimiz", "html"),

    # --- servis verisi hiç gelmeyen markalar ---
    "kimmi-bayi":      ("https://www.kimmimotor.com/bayiler/", "html"),
    "kimmi-srv":       ("https://www.kimmimotor.com/servisler/", "html"),
    "leksas-bs":       ("https://www.leksas.com.tr/bayi-servis/", "html"),
    "taktas-bs":       ("https://taktas.com.tr/bayi-ve-servis", "html"),
    "taktas-srv":      ("https://taktas.com.tr/servislerimiz", "html"),
    "arnica-bayi06":   ("https://arnicamotor.com/bayiler?lang=tr&sehir_id=6", "html"),
    "arnica-srv06":    ("https://arnicamotor.com/servisler?lang=tr&sehir_id=6", "html"),
    "lifan-bayi":      ("https://www.lifanmotor.com.tr/bayiler/", "html"),
    "lifan-srv":       ("https://www.lifanmotor.com.tr/servisler/", "html"),
    "acco-bayi":       ("https://actiomobilite.com/bayiler", "html"),
    "indian-srv":      ("https://www.indianmotorcycle.com.tr/find-a-dealer/list-teknik-servisler/", "html"),

    # WordPress REST ucu: sayfa içeriğini işlenmiş hâlde veriyor.
    # Elementor listesi düz HTML'de görünmediğinde buradan okunuyor.
    "kimmi-rest":      ("https://www.kimmimotor.com/wp-json/wp/v2/pages/850", "json"),
    "lifan-rest":      ("https://www.lifanmotor.com.tr/wp-json/wp/v2/pages/1383", "json"),
    "leksas-rest":     ("https://www.leksas.com.tr/wp-json/wp/v2/pages/72", "json"),
    "indian-satis":    ("https://www.indianmotorcycle.com.tr/find-a-dealer/list-bayiler/", "html"),

    # Kimmi / Lifan: il seçimi düz URL'e gidiyor (/servisler/ankara)
    "kimmi-srv-ank":   ("https://www.kimmimotor.com/servisler/ankara", "html"),
    "kimmi-bayi-ank":  ("https://www.kimmimotor.com/bayiler/ankara", "html"),
    "lifan-srv-ank":   ("https://www.lifanmotor.com.tr/servisler/ankara", "html"),

    # --- hiç veri gelmeyen 15 marka ---
    # Piaggio grubu (Vespa/Kymco ile aynı 'stores' GeoJSON olabilir)
    "aprilia-satis":   ("https://www.aprilia.com.tr/tr/yetkili-saticilar.html", "html"),
    "aprilia-servis":  ("https://www.aprilia.com.tr/tr/yetkili-servisler.html", "html"),
    "piaggio-satis":   ("https://www.piaggio.com.tr/tr/yetkili-saticilar.html", "html"),
    "piaggio-servis":  ("https://www.piaggio.com.tr/tr/yetkili-servisler.html", "html"),
    "kymco-agi":       ("https://www.kymco.com.tr/tr/satis-servis-agi.html", "html"),
    # diğerleri
    "altai-satis":     ("https://www.altai.com.tr/tr/bayiler", "html"),
    "altai-servis":    ("https://www.altai.com.tr/tr/servisler", "html"),
    "regal-satis":     ("https://regalraptor.com.tr/tr/bayiler", "html"),
    "regal-servis":    ("https://regalraptor.com.tr/tr/servisler", "html"),
    "yiben-satis":     ("https://yibenmotosiklet.com.tr/tr/sayfa/bayi-agi", "html"),
    "yiben-servis":    ("https://yibenmotosiklet.com.tr/tr/sayfa/servis-agi", "html"),
    "yuki-satis":      ("https://yukimotor.com.tr/satis-noktalari/", "html"),
    "yuki-servis":     ("https://yukimotor.com.tr/servis-noktalari/", "html"),
    "rewaco-satis":    ("https://rewaco.com.tr/bayiler/", "html"),
    "rewaco-servis":   ("https://rewaco.com.tr/servis/", "html"),
    "stmax-servis":    ("https://stmax.com.tr/yetkili-servisler/", "html"),
    "korlas-bayi":     ("https://korlas.com.tr/bayi/", "html"),
    "korlas-servis":   ("https://korlas.com.tr/servis/", "html"),
    "bmw-moto":        ("https://www.bmw-motorrad.com.tr/tr/ssl/yetkili-satici-ve-servisler.html", "html"),

    # Yuki: konum tespiti sadece kısayol; asıl seçim ?province=<slug>
    "yuki-satis-ank":  ("https://yukimotor.com.tr/satis-noktalari/?province=ankara", "html"),
    "yuki-servis-ank": ("https://yukimotor.com.tr/servis-noktalari/?province=ankara", "html"),
    # Rebat ve Harley — henüz hiç yakalanmadı
    "rebat":           ("https://rebatmotor.com/satis-ve-servisler-cloned-1111/", "html"),
    "harley":          ("https://www.harley-davidson.com/tr/tr/tools/find-a-dealer.html", "html"),
    "stmax-srv":       ("https://stmax.com.tr/yetkili-servisler/", "html"),
    "rewaco-srv2":     ("https://rewaco.com.tr/servis/", "html"),

    # BMW: sayfa listeyi bu servisten çekiyor (kaynaktaki
    # data-gcdm-dealer-data-url). Sayfanın kendisi düz isteğe yanıt
    # vermiyor ama bu uç veriyor.
    "bmw-api":  ("https://c2b-services-i.bmw.com/c2b-localsearch/services/cache/v4/ShowAll?country=tr&category=BD&clientid=UX_NICCE_FORM_DLO", "json"),

    # STMax: il seçimi doğrudan /iller/<slug>/ adresine gidiyor
    "stmax-ankara":    ("https://stmax.com.tr/iller/ankara/", "html"),
    "stmax-adana":     ("https://stmax.com.tr/iller/adana/", "html"),

    # Bajaj/Kanuni (Kuralkan): 98 satış beklenirken 87 geliyor
    "kuralkan-satis-hepsi": ("https://www.ekuralkan.com/motosiklet-satis-noktalari", "html"),
    "kuralkan-satis-34":    ("https://www.ekuralkan.com/motosiklet-satis-noktalari?city=34", "html"),
    "kuralkan-servis":      ("https://www.ekuralkan.com/motosiklet-teslimat-noktalari", "html"),

    # Taranmamış son markalar
    "rebat-servis":    ("https://rebatmotor.com/servis/", "html"),
    "rebat-bayi":      ("https://rebatmotor.com/bayi/", "html"),
    "bmw-yeni":        ("https://www.bmw-motorrad.com.tr/tr/ssl/yetkili-satici-ve-servisler.html", "html"),

    # BMW Motorrad: bmw-motorrad.com.tr boş kabuk (içerik iframe'de).
    # Gerçek kaynak distribütör Borusan Otomotiv; il bazlı düz GET.
    "borusan-istanbul": ("https://www.borusanotomotiv.com/yetkili-satici-ve-servisler/arama?city=istanbul", "html"),
    "borusan-bursa":    ("https://www.borusanotomotiv.com/yetkili-satici-ve-servisler/arama?city=Bursa", "html"),
    "borusan-harita":   ("https://www.borusanotomotiv.com/yetkili-satici-ve-servisler/harita", "html"),

    # SYM: 278 kaydın 126'sı yanlışlıkla Adana'ya atanmış, il ataması bozuk
    "sym-bayiler":     ("https://www.sym-tr.com/bayiler/", "html"),
    "sym-servis":      ("https://www.sym-tr.com/servis/", "html"),

    # Kawasaki: 85 kaydın 79'unda il yanlış (İstanbul'dakiler Ankara görünüyor)
    "kawasaki-satis":  ("https://www.kawasaki.com.tr/Home/YetkiliSatici", "html"),
    "kawasaki-servis": ("https://www.kawasaki.com.tr/Home/YetkiliServis", "html"),

    # Abush: NUR MOTOR "İLBADE MAH." adresiyle İstanbul'a atanmış,
    # İlbade Trabzon'da bir mahalle — il ataması doğrulanacak
    "abush-liste":     ("https://abush.com.tr/tr/bayiler", "html"),

    # --- spormoto ---
    "ktm-servis":       ("https://spormoto.com/ktm/ktm-servisler/", "html"),
    "ktm-satis":        ("https://spormoto.com/ktm/bayiler/", "html"),
    "husqvarna-servis": ("https://spormoto.com/husqvarna/husqvarna-servisler/", "html"),
    "husqvarna-satis":  ("https://spormoto.com/husqvarna/bayiler/", "html"),

    # --- öncelik listesi: Hero, Musatti, CSN, Vespa, Suzuki, Zelsun, Falcon, Kral
    # Keşif raporundan çıkan gerçek veri uçları.
    "falcon-api":      ("https://falconmotosiklet.com/api/bayiler.php", "json"),
    "musatti-bayi06":  ("https://musattimotor.com/ajax-bayi-listesi.php?city=06", "json"),
    "musatti-srv06":   ("https://musattimotor.com/ajax-servis-listesi.php?city=06", "json"),
    "musatti-sayfa":   ("https://musattimotor.com/bayi-bul", "html"),
    "kral-satis":      ("https://kralmotor.tr/SalesDealer", "html"),
    "kral-servis":     ("https://kralmotor.tr/Service", "html"),
    "vespa-satis":     ("https://www.vespa.com.tr/tr/yetkili-saticilar.html", "html"),
    "vespa-servis":    ("https://www.vespa.com.tr/tr/yetkili-servisler.html", "html"),
    # DİKKAT: satis.html bayi listesi İÇERMİYOR (sadece test sürüşü metni).
    # Doğru adres yetkili-saticilar.html — kullanıcı bildirdi.
    "suzuki-satici":   ("https://www.suzuki.com.tr/tr/motosiklet/yetkili-saticilar.html", "html"),
    "suzuki-servis":   ("https://www.suzuki.com.tr/tr/motosiklet/yetkili-servisler.html", "html"),
    "zelsun-satis":    ("https://www.zelsunmotor.com/Bayilerimiz.aspx", "html"),
    "zelsun-servis":   ("https://www.zelsunmotor.com/Servislerimiz.aspx", "html"),
    "zelsun-ist":      ("https://www.zelsunmotor.com/Bayilerimiz.aspx?sehir=%c4%b0STANBUL&ilce=", "html"),
    "hero-satis":      ("https://www.heromotor.com.tr/bayiler/", "html"),
    "hero-servis":     ("https://www.heromotor.com.tr/servisler/", "html"),
    "csn-satis":       ("https://csnmotor.com.tr/satis-noktalarimiz/", "html"),
    "csn-servis2":     ("https://csnmotor.com.tr/servis-noktalarimiz/", "html"),
    # CSN servis, il bağlantılarını /servis-noktalarimiz/<il> biçiminde veriyor;
    # satış ise düz /<il>. Sistem sadece ikinciyi tanıdığı için servis boş kalmıştı.
    "csn-srv-ankara":  ("https://csnmotor.com.tr/servis-noktalarimiz/ankara", "html"),
    "csn-sat-ankara":  ("https://csnmotor.com.tr/ankara", "html"),

}

TEL = re.compile(r"0?\s*\(?5?\d{3}\)?[\s\-/]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}")
SCRIPT = re.compile(r"<script[^>]*>(.*?)</script>", re.S | re.I)


def yakala(ad: str, url: str, uzanti: str) -> dict:
    bilgi: dict = {"url": url}
    try:
        # BMW gibi bazı siteler ilk yanıtı 60 sn'ye kadar geciktiriyor;
        # önceki denemede ReadTimeout bu yüzden gelmişti.
        y = requests.get(url, headers=BASLIK, timeout=(15, 120),
                         allow_redirects=True)
    except Exception as e:  # noqa: BLE001
        bilgi["hata"] = f"{type(e).__name__}: {e}"[:200]
        return bilgi

    govde = y.text
    bilgi["kod"] = y.status_code
    bilgi["son_url"] = y.url
    bilgi["boyut"] = len(govde)
    bilgi["tel_toplam"] = len(TEL.findall(govde))
    # Asıl soru: telefonlar script içinde mi? Öyleyse veri gömülü demektir.
    bilgi["tel_script_ici"] = sum(
        len(TEL.findall(s)) for s in SCRIPT.findall(govde)
    )
    if y.url != url:
        bilgi["yonlendi"] = True

    CIKTI.mkdir(exist_ok=True)
    (CIKTI / f"{ad}.{uzanti}.gz").write_bytes(
        gzip.compress(govde.encode("utf-8", "replace"))
    )
    return bilgi


def marka_hedefleri(adlar: list[str]) -> dict[str, tuple[str, str]]:
    """markalar.json'daki 'bayi' adreslerinden hedef sözlüğü üretir.

    Böylece her yeni marka için bu dosyayı elle düzenlemek gerekmiyor:
        python hamyakala.py --markalar "Hero,Musatti,Vespa"
    """
    kayit = json.loads(Path("markalar.json").read_text(encoding="utf-8"))
    tablo = {m["ad"]: m for m in kayit}
    out: dict[str, tuple[str, str]] = {}
    for ad in adlar:
        m = tablo.get(ad)
        if not m:
            print(f"  ! markalar.json'da yok: {ad}")
            continue
        anahtar = "m-" + re.sub(r"[^a-z0-9]+", "-", ad.lower()).strip("-")
        out[anahtar] = (m["bayi"], "html")
        # Ana sayfa da işe yarayabilir (bayi bağlantısı değişmiş olabilir)
        if m.get("site") and m["site"].rstrip("/") != m["bayi"].rstrip("/"):
            out[anahtar + "-ana"] = (m["site"], "html")
    return out


def main() -> None:
    argv = sys.argv[1:]
    if "--markalar" in argv:
        i = argv.index("--markalar")
        adlar = [a.strip() for a in argv[i + 1].split(",") if a.strip()]
        secili = marka_hedefleri(adlar)
    else:
        istenen = argv
        if istenen:
            secili = {k: v for k, v in HEDEFLER.items()
                      if any(a.lower() in k for a in istenen)}
        else:
            secili = HEDEFLER

    ozet: dict[str, dict] = {}
    onceki = CIKTI / "ozet.json"
    if onceki.exists():
        try:
            ozet = json.loads(onceki.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            ozet = {}
    for ad, (url, uzanti) in secili.items():
        print(f"→ {ad}", flush=True)
        b = yakala(ad, url, uzanti)
        ozet[ad] = b
        if "hata" in b:
            print(f"   ✗ {b['hata'][:80]}")
        else:
            print(f"   {b['kod']}  {b['boyut']//1024}KB  "
                  f"tel={b['tel_toplam']} (script içi {b['tel_script_ici']})"
                  + ("  [YÖNLENDİ]" if b.get("yonlendi") else ""))

    CIKTI.mkdir(exist_ok=True)
    (CIKTI / "ozet.json").write_text(
        json.dumps(ozet, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n✓ {len(ozet)} hedef → {CIKTI}/")


if __name__ == "__main__":
    main()
