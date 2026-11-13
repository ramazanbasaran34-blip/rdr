#!/usr/bin/env python3
"""Öncelikli markalar için marka başına özel ayrıştırıcılar.

Her markanın sitesi farklı bir altyapı kullanıyor, bu yüzden ortak bir tarif
yerine her biri için ayrı fonksiyon yazıldı. Hepsi ÖNCE kaydedilmiş ham
dosyalar üzerinde test edilebiliyor; ağ gerekmiyor, saniyeler sürüyor.

    python ozel_markalar.py --test          # ham/ altındaki dosyalarla dene
    python ozel_markalar.py --test Falcon   # tek marka
    python ozel_markalar.py --kuru          # canlı çek, veritabanına yazma
    python ozel_markalar.py                 # canlı çek + veritabanına işle

Çözülen yapılar:
  Falcon  → /api/bayiler.php tek JSON; typeModel.mb/ms bayrakları rolü veriyor
  Kral    → sayfada window.allDealers = [...] geçerli JSON
  Vespa   → sayfada GeoJSON (Kymco ile aynı altyapı)
  Suzuki  → servis sayfası GeoJSON; satış sayfası ayrı (aşağıya bak)
  CSN     → il il gezilen sayfa
"""

from __future__ import annotations

import gzip
import json
import re
import sys
import time
from pathlib import Path

from bs4 import BeautifulSoup

from bayiradar.normalize import IL_KODU
from bayiradar.parse import finalize

HAM = Path("ham")
BASLIK = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9",
}


def _t(x) -> str:
    return re.sub(r"\s+", " ", str(x or "")).strip()


# --------------------------------------------------------------- FALCON
def falcon_coz(govde: str) -> list[dict]:
    """Falcon: /api/bayiler.php tek seferde tüm ağı JSON veriyor.

    3.737 kaydın hepsi motosiklet noktası DEĞİL; typeModel bayrakları:
        mb = motosiklet bayi (satış)
        ms = motosiklet servis
        yp = yedek parça  → tek başına satış/servis noktası sayılmaz
    Yalnızca mb ya da ms işaretli olanlar alınıyor (~1215 kayıt).
    """
    d = json.loads(govde)
    kayitlar = []
    for x in d.get("tumBayiler", []):
        if not x.get("isAktif", True):
            continue
        t = x.get("typeModel") or {}
        mb, ms = bool(t.get("mb")), bool(t.get("ms"))
        if not (mb or ms):
            continue
        rol = "satis_servis" if (mb and ms) else ("satis" if mb else "servis")
        kayitlar.append({
            "bayi_adi": _t(x.get("Unvani")),
            "il": _t(x.get("Il")),
            "ilce": _t(x.get("Ilce")),
            "adres": _t(x.get("Adres")),
            "telefon": _t(x.get("Tel") or x.get("Gsm")),
            "email": "", "website": "", "rol": rol,
        })
    return kayitlar


# ----------------------------------------------------------------- KRAL
def kral_coz(govde: str, rol: str) -> list[dict]:
    """Kral: sayfada `window.allDealers = [...]` — düpedüz geçerli JSON."""
    m = re.search(r"window\.allDealers\s*=\s*(\[.*?\])\s*;", govde, re.S)
    if not m:
        return []
    kayitlar = []
    for x in json.loads(m.group(1)):
        if not x.get("isActive", True):
            continue
        kayitlar.append({
            "bayi_adi": _t(x.get("name")),
            "il": _t(x.get("city")),
            "ilce": _t(x.get("district")),
            "adres": _t(x.get("address")),
            "telefon": _t(x.get("phone1") or x.get("phone2")),
            "email": "", "website": "", "rol": rol,
        })
    return kayitlar


# -------------------------------------------------- GeoJSON (Vespa, Suzuki)
GEO_KAYIT = re.compile(
    r"\{\s*'type':\s*'(yetkili-[a-z]+)',.*?'properties':\s*\{(.*?)\}\s*\}", re.S)


def _geo_alan(blok: str, ad: str) -> str:
    m = re.search(r"'" + ad + r"':\s*'(.*?)'", blok, re.S)
    return _t(m.group(1)) if m else ""


def geojson_coz(govde: str) -> list[dict]:
    """Vespa ve Suzuki, Kymco ile aynı ajansın altyapısını kullanıyor:
    tüm ağ sayfaya GeoJSON olarak gömülü, harita onu okuyor.
    'city' alanı "Adana - Çukurova" biçiminde, il ve ilçe birlikte.
    """
    rol_esle = {"yetkili-satici": "satis", "yetkili-servis": "servis",
                "yetkili-bayi": "satis"}
    kayitlar = []
    for m in GEO_KAYIT.finditer(govde):
        tip, blok = m.group(1), m.group(2)
        ad = _geo_alan(blok, "name")
        if not ad:
            continue
        konum = _geo_alan(blok, "city")
        il, ilce = "", ""
        if "-" in konum:
            il, ilce = [p.strip() for p in konum.split("-", 1)]
        else:
            il = konum
        kayitlar.append({
            "bayi_adi": ad, "il": il, "ilce": ilce,
            "adres": _geo_alan(blok, "address"),
            "telefon": _geo_alan(blok, "phone1"),
            "email": _geo_alan(blok, "mail1"), "website": "",
            "rol": rol_esle.get(tip, "satis"),
        })
    return kayitlar


# ------------------------------------------------------------------ CSN
def csn_coz(govde: str, rol: str) -> list[dict]:
    """CSN: il sayfalarındaki kart ızgarası.

    ÖNEMLİ: satış ve servis FARKLI URL kalıbı kullanıyor —
        satış : csnmotor.com.tr/<il>
        servis: csnmotor.com.tr/servis-noktalarimiz/<il>
    Sistem yalnızca birinci kalıbı tanıdığı için servis hep boş kalıyordu.

    Kart: h5.pxl-item--title içinde "İlçe - Firma", ilçe adın başında.
    """
    soup = BeautifulSoup(govde, "html.parser")
    kayitlar = []
    for kart in soup.select(".pxl-item--inner"):
        b = kart.select_one("h5.pxl-item--title")
        if not b:
            continue
        ham_ad = _t(b.get_text(" "))
        if not ham_ad:
            continue
        # "Çubuk - Arıkan Motors" → ilçe + firma
        ilce, ad = "", ham_ad
        if " - " in ham_ad:
            on, arka = ham_ad.split(" - ", 1)
            if len(on) <= 28:
                ilce, ad = _t(on), _t(arka)
        adres = kart.select_one(".pxl-description")
        tel = kart.select_one(".pxl-phone")
        kayitlar.append({
            "bayi_adi": ad, "il": "", "ilce": ilce,
            "adres": _t(adres.get_text(" ")) if adres else "",
            "telefon": _t(tel.get_text(" ")) if tel else "",
            "email": "", "website": "", "rol": rol,
        })
    return kayitlar


CSN_IL = re.compile(r'href="/(?:servis-noktalarimiz/)?([a-z0-9çğıöşü-]{3,25})"')


def csn_iller(govde: str, servis: bool) -> list[str]:
    """Ana sayfadaki haritadan il kısaltmalarını toplar."""
    if servis:
        return sorted(set(re.findall(
            r'href="/servis-noktalarimiz/([a-z0-9-]{3,25})"', govde)))
    # Satışta düz /<il>; menü bağlantılarını elemek için harita bloğuna bak
    hepsi = re.findall(r'href="/([a-z0-9-]{3,25})"', govde)
    menu = {"bayilik-basvurusu", "fiyat-listesi", "garanti-politikasi",
            "gizlilik-politikasi", "hakkimizda", "iletisim", "kariyer",
            "kullanim-kilavuzlari", "tarihce", "basinda-biz", "bizden-haberler",
            "kullanici-yorumlari", "is-basvuru-formu", "tum-modeller",
            "satis-noktalarimiz", "servis-noktalarimiz"}
    return sorted({x for x in hepsi if x not in menu})


# -------------------------------------------------------------- MUSATTI
def musatti_coz(govde: str, _rol: str) -> list[dict]:
    """Musatti: ajax-(bayi|servis)-listesi.php?city=<plaka> → {html: "..."}.

    Kartın `badge` alanı rolü zaten yazıyor: "Bayi", "Servis", "Bayi & Servis".
    Bu yüzden rolü kaynaktan değil kaydın kendisinden alıyoruz.
    """
    d = json.loads(govde)
    soup = BeautifulSoup(d.get("html", ""), "html.parser")
    rol_esle = {"bayi": "satis", "servis": "servis",
                "bayi & servis": "satis_servis", "bayi ve servis": "satis_servis"}
    kayitlar = []
    for kart in soup.select(".faq-contain"):
        b = kart.select_one("h2")
        if not b:
            continue
        rozet = kart.select_one(".badge")
        etiket = _t(rozet.get_text(" ")).lower() if rozet else ""
        h5 = kart.select("h5")
        tel, adres = "", ""
        a = kart.select_one("a[href^='tel:']")
        if a:
            tel = _t(a.get_text(" ")) or _t(a.get("href", "").replace("tel:", ""))
        for x in h5:
            metin = _t(x.get_text(" "))
            if metin and not x.select_one("a[href^='tel:']"):
                adres = metin
        kayitlar.append({
            "bayi_adi": _t(b.get_text(" ")), "il": "", "ilce": "",
            "adres": adres, "telefon": tel, "email": "", "website": "",
            "rol": rol_esle.get(etiket, "satis"),
        })
    return kayitlar


# --------------------------------------------------------------- kayıtlar
# İl il gezilmesi gereken markalar: (taban_url_uretici, rol)
# Tek istekle bitenlerden ayrı tutuluyor çünkü akışları farklı.
CSN_TABAN = "https://csnmotor.com.tr"
MUSATTI_TABAN = "https://musattimotor.com"

# Musatti plaka kodlarıyla çalışıyor (city=06). 81 il.
PLAKALAR = [f"{i:02d}" for i in range(1, 82)]


def csn_marka(oku, canli_mi: bool) -> list[dict]:
    """CSN: önce harita sayfasından il listesi, sonra il il gez."""
    cikan = []
    for servis, kok in ((False, "csn-satis.html"), (True, "csn-servis2.html")):
        rol = "servis" if servis else "satis"
        ana = oku(kok, f"{CSN_TABAN}/{'servis' if servis else 'satis'}-noktalarimiz/")
        if ana is None:
            continue
        iller = csn_iller(ana, servis)
        if not canli_mi:
            # Testte tek örnek il var; onunla yetin.
            iller = ["ankara"]
        for il in iller:
            yol = (f"{CSN_TABAN}/servis-noktalarimiz/{il}" if servis
                   else f"{CSN_TABAN}/{il}")
            dosya = f"csn-{'srv' if servis else 'sat'}-{il}.html"
            # CSN 160+ ardışık istekte bağlantıyı kapatıyor; yavaş ve
            # yeniden denemeli gidiyoruz.
            g = None
            for deneme in range(3):
                try:
                    g = oku(dosya, yol)
                    break
                except Exception:  # noqa: BLE001
                    if canli_mi:
                        time.sleep(3 * (deneme + 1))
            if g is None:
                continue
            if canli_mi:
                time.sleep(0.8)
            for r in csn_coz(g, rol):
                r["il"] = il.replace("-", " ")
                k = finalize(r, "CSN", yol, {})
                if k:
                    cikan.append(k)
    return cikan


def musatti_marka(oku, canli_mi: bool) -> list[dict]:
    """Musatti: her il için iki JSON ucu; rol kaydın rozetinden geliyor."""
    cikan = []
    plakalar = PLAKALAR if canli_mi else ["06"]
    for tur, kisa in (("bayi", "bayi"), ("servis", "srv")):
        for pl in plakalar:
            yol = f"{MUSATTI_TABAN}/ajax-{tur}-listesi.php?city={pl}"
            g = oku(f"musatti-{kisa}{pl}.json", yol)
            if g is None:
                continue
            il_adi = IL_KODU.get(int(pl), "")
            for r in musatti_coz(g, ""):
                # İl adresten çıkarılamayabiliyor; plaka kodu kesin bilgi.
                r["il"] = r.get("il") or il_adi
                k = finalize(r, "Musatti", yol, {})
                if k:
                    cikan.append(k)
    return cikan


IL_IL = {"CSN": csn_marka, "Musatti": musatti_marka}

# marka -> {rol: (ham_dosya_adi, url, cozucu)}
KAYNAKLAR: dict[str, dict] = {
    "Falcon": {
        "tek": ("falcon-api.json", "https://falconmotosiklet.com/api/bayiler.php",
                lambda g, r: falcon_coz(g)),
    },
    "Kral": {
        "satis":  ("kral-satis.html", "https://kralmotor.tr/SalesDealer", kral_coz),
        "servis": ("kral-servis.html", "https://kralmotor.tr/Service", kral_coz),
    },
    "Vespa": {
        "satis":  ("vespa-satis.html",
                   "https://www.vespa.com.tr/tr/yetkili-saticilar.html",
                   lambda g, r: geojson_coz(g)),
        "servis": ("vespa-servis.html",
                   "https://www.vespa.com.tr/tr/yetkili-servisler.html",
                   lambda g, r: geojson_coz(g)),
    },
    "Suzuki": {
        "servis": ("suzuki-servis.html",
                   "https://www.suzuki.com.tr/tr/motosiklet/yetkili-servisler.html",
                   lambda g, r: geojson_coz(g)),
    },
}

# Marka başına en az beklenen kayıt (site gerçeğine göre, testte eşik)
ESIK = {"Falcon": 900, "Kral": 500, "Vespa": 60, "Suzuki": 35,
        "CSN": 3, "Musatti": 8}   # CSN/Musatti testte tek il ile denenir

TUM_MARKALAR = list(KAYNAKLAR) + list(IL_IL)


def marka_kayitlari(marka: str, oku, canli_mi: bool = False) -> list[dict]:
    """oku(dosya, url) -> gövde metni. Test ve canlı mod aynı kodu paylaşsın."""
    if marka in IL_IL:
        return IL_IL[marka](oku, canli_mi)
    cikan: list[dict] = []
    for rol, (dosya, url, cozucu) in KAYNAKLAR[marka].items():
        govde = oku(dosya, url)
        if govde is None:
            continue
        for r in cozucu(govde, rol if rol != "tek" else "satis"):
            k = finalize(r, marka, url, {})
            if k:
                cikan.append(k)
    return cikan


# ------------------------------------------------------------------ test
def test(secili: list[str]) -> int:
    def oku(dosya, _url):
        yol = HAM / f"{dosya}.gz"
        if not yol.exists():
            print(f"      · {yol} yok")
            return None
        return gzip.decompress(yol.read_bytes()).decode("utf-8", "replace")

    hata = 0
    for marka in TUM_MARKALAR:
        if secili and marka not in secili:
            continue
        k = marka_kayitlari(marka, oku, canli_mi=False)
        ilsiz = sum(1 for x in k if not x.get("il"))
        telsiz = sum(1 for x in k if not x.get("telefon"))
        iller = len({x.get("il") for x in k if x.get("il")})
        roller = {}
        for x in k:
            roller[x.get("rol")] = roller.get(x.get("rol"), 0) + 1
        print(f"  {marka:8} → {len(k):5} kayıt | {iller:2} il | "
              f"ilsiz {ilsiz} | telefonsuz {telsiz} | {roller}")
        for x in k[:2]:
            print(f"        {x['bayi_adi'][:30]:30} | {x.get('il')} / "
                  f"{x.get('ilce')} | {x.get('telefon')}")
        if len(k) < ESIK.get(marka, 1):
            print(f"        ✗ eşiğin altında (en az {ESIK.get(marka)})")
            hata += 1
        if ilsiz:
            print("        ✗ ilsiz kayıt var")
            hata += 1
    return hata


# ----------------------------------------------------------------- canlı
def canli(kuru: bool, secili: list[str]) -> None:
    import requests

    from bayiradar.store import commit_tarama, db, now

    o = requests.Session()
    o.headers.update(BASLIK)
    basladi = now()
    rapor: dict = {}

    def oku(_dosya, url):
        y = o.get(url, timeout=60)
        y.raise_for_status()
        return y.text

    for marka in TUM_MARKALAR:
        if secili and marka not in secili:
            continue
        try:
            k = marka_kayitlari(marka, oku, canli_mi=True)
        except Exception as e:  # noqa: BLE001
            rapor[marka] = {"hata": f"{type(e).__name__}: {e}"[:160]}
            print(f"  {marka}: ✗ {rapor[marka]['hata'][:70]}")
            continue
        rapor[marka] = {"kayit": len(k),
                        "il": len({x.get("il") for x in k if x.get("il")}),
                        "ilsiz": sum(1 for x in k if not x.get("il"))}
        print(f"  {marka}: {len(k)}")
        if not kuru and k:
            with db() as con:
                rapor[marka]["db"] = str(commit_tarama(con, marka, k, 1.0,
                                                       basladi))[:180]
    print(json.dumps(rapor, ensure_ascii=False, indent=1))
    HAM.mkdir(exist_ok=True)
    (HAM / "ozel-tarama.json").write_text(
        json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")


def main() -> None:
    arg = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--test" in sys.argv:
        h = test(arg)
        print("\n✓ test geçti" if not h else f"\n✗ {h} sorun")
        sys.exit(1 if h else 0)
    canli("--kuru" in sys.argv, arg)


if __name__ == "__main__":
    main()
