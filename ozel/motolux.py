"""Motolux — il sayfasında ÜÇ SEKME var.

Sayfa tek liste gibi görünüyor ama içinde üç ayrı sekme bulunuyor:

    BAYİ  ·  SERVİS  ·  YEDEK PARÇA BAYİ

Eski tarif sekmeleri hiç ayırmadığı için iki hata birden yapıyordu:
  1. Bütün kayıtlar "satış + servis" sayılıyordu → yalnız-servis sayısı 0.
  2. Sekme başlığı ("YEDEK PARÇA BAYİ") firma adı sanılıp 20 ilde sahte
     kayıt olarak yazılıyordu.

Burada sekmeler `<ul class="hr-tabs-nav">` başlıklarıyla `.tab-pane`
bölmeleri eşleştirilerek okunuyor. Yedek parça sekmesi motosiklet satış
ya da servis noktası olmadığı için tamamen dışarıda bırakılıyor.
"""

from __future__ import annotations

import re
import unicodedata

from bs4 import BeautifulSoup

MARKA = "Motolux"

TABAN = "https://motolux.com.tr/bayiler/sehir/{slug}/"
KAYNAKLAR = {"hepsi": TABAN}
TEST = {("Motolux", "hepsi"): "motolux-adana.html"}
TEST_IL = "Adana"

# Sekme başlığı → rol. Yedek parça bilinçli olarak None (elenir).
SEKME_ROL = {
    "bayi": "satis",
    "servis": "servis",
    "yedek parca bayi": None,
    "yedek parca": None,
}

TEL = re.compile(r"(?:0|\+90)[\s\(\)\-/\.]*\d{3}[\s\(\)\-/\.]*\d{3}[\s\-/\.]*\d{2}[\s\-/\.]*\d{2}")


def il_url(slug: str) -> str:
    return TABAN.format(slug=slug)


def _sade(t: str) -> str:
    return re.sub(r"\s+", " ", t or "").strip()


def _anahtar(t: str) -> str:
    """Sekme başlığını karşılaştırılabilir hâle getirir.

    Dikkat: Türkçe "İ" için casefold() birleşik bir karakter üretiyor
    ("BAYİ" → "bayi̇", sonda U+0307 kalıyor) ve düz karşılaştırma tutmuyor.
    Bu yüzden ÖNCE Türkçe harfleri çeviriyor, SONRA küçültüyoruz; kalan
    birleştirici işaretleri de ayıklıyoruz.
    """
    t = _sade(t)
    for a, b in (("İ", "I"), ("I", "I"), ("ı", "i"), ("Ç", "C"), ("ç", "c"),
                 ("Ğ", "G"), ("ğ", "g"), ("Ö", "O"), ("ö", "o"),
                 ("Ş", "S"), ("ş", "s"), ("Ü", "U"), ("ü", "u")):
        t = t.replace(a, b)
    t = unicodedata.normalize("NFKD", t.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def coz(rol: str, govde: str, url: str, il: str | None = None) -> list[dict]:
    soup = BeautifulSoup(govde, "html.parser")
    out: list[dict] = []

    # Sayfada birden çok sekme grubu var (ilki model menüsü).
    # Doğru grubu başlıklarına bakarak buluyoruz.
    for kap in soup.select(".tabbable"):
        nav = kap.find("ul", class_="hr-tabs-nav")
        if not nav:
            continue
        basliklar = [_anahtar(a.get_text(" ")) for a in nav.find_all("a")]
        if not any(b in SEKME_ROL for b in basliklar):
            continue  # bayi/servis sekmesi değil

        icerik = kap.find("div", class_="tab-content")
        bolmeler = icerik.find_all("div", class_="tab-pane", recursive=False) if icerik else []
        if len(basliklar) != len(bolmeler):
            continue

        for baslik, bolme in zip(basliklar, bolmeler):
            hedef_rol = SEKME_ROL.get(baslik, None)
            if hedef_rol is None:
                continue  # yedek parça ya da tanınmayan sekme

            for kayit in _bolmeden_kayitlar(bolme):
                kayit["rol"] = hedef_rol
                kayit["il"] = il or ""
                out.append(kayit)
    return out


def _bolmeden_kayitlar(bolme) -> list[dict]:
    """Bir sekme bölmesindeki firmaları çıkarır.

    Yapı: `.border-bayi` blokları. Her blokta ilçe başlığı
    (`h3.bayi-ana-baslik`) ve altında birden çok firma sütunu var.
    Firma bilgisi `ul.font-bayi` listesinde satır satır:
        1. satır → firma adı
        2+       → "Gsm : ...", "Telefon : ...", "Adres :..."
    """
    kayitlar = []

    for blok in bolme.select(".border-bayi"):
        bas = blok.select_one("h3.bayi-ana-baslik, .bayi-ana-baslik")
        ilce = _sade(bas.get_text(" ")) if bas else ""

        for liste in blok.select("ul.font-bayi"):
            satirlar = [_sade(li.get_text(" ")) for li in liste.find_all("li")]
            satirlar = [x for x in satirlar if x]
            if not satirlar:
                continue

            ad = satirlar[0]
            tel, adres = "", ""
            for x in satirlar[1:]:
                dusuk = _anahtar(x)
                if dusuk.startswith("adres"):
                    adres = _sade(re.sub(r"(?i)^adres\s*:?", "", x))
                elif dusuk.startswith(("gsm", "telefon", "tel")):
                    if not tel:
                        m = TEL.search(x)
                        tel = m.group(0) if m else _sade(re.sub(r"(?i)^(gsm|telefon|tel)\s*:?", "", x))
                elif not adres:
                    adres = x

            if not ad or _anahtar(ad) in SEKME_ROL:
                continue
            kayitlar.append({"bayi_adi": ad, "ilce": ilce, "adres": adres,
                             "telefon": tel, "email": "", "website": ""})
    return kayitlar
