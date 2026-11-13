"""Indian Motorcycle — düz HTML liste.

Sayfa haritalı görünse de tam liste kaynakta duruyor:
`.dealers-full-list-item` blokları. Tarayıcı gerekmiyor.

    satış  → /find-a-dealer/list-bayiler/
    servis → /find-a-dealer/list-teknik-servisler/

Adres bloğunda ilçe/il birlikte ve satırlar <br> ile ayrılmış:
    "Gürselpaşa Mahallesi, ... No:35/F<br /> 1200 Adana"
Son satırın sonundaki kelime il, öncesi posta kodu.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .tr import anahtar

MARKA = "Indian"

KAYNAKLAR = {
    "satis":  "https://www.indianmotorcycle.com.tr/find-a-dealer/list-bayiler/",
    "servis": "https://www.indianmotorcycle.com.tr/find-a-dealer/list-teknik-servisler/",
}
TEST = {
    ("Indian", "servis"): "indian-srv.html",
}

TEL = re.compile(r"(?:\+90|0)[\s\(\)\-/\.]*\d{3}[\s\(\)\-/\.]*\d{3}[\s\-/\.]*\d{2}[\s\-/\.]*\d{2}")
POSTA_IL = re.compile(r"\b(\d{4,5})\s+([^\d,;]{3,30})\s*$")


def _m(el) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ")).strip() if el else ""


def coz(rol: str, govde: str, url: str) -> list[dict]:
    soup = BeautifulSoup(govde, "html.parser")
    out = []

    for kart in soup.select(".dealers-full-list-item"):
        ad = _m(kart.select_one(".dealers-full-list-item-header h3, h3"))
        # Sıra numarası kutusu boş gelebiliyor, baştaki sayıyı at
        ad = re.sub(r"^\d+\s*", "", ad).strip()
        if not ad:
            continue

        icerik = kart.select_one(".dealers-full-list-item-content") or kart
        metin = _m(icerik)

        # Adres: harita bağlantısının metni
        adres_el = icerik.select_one("a[href*='maps']")
        adres = _m(adres_el) if adres_el else ""

        il = ""
        m = POSTA_IL.search(adres)
        if m:
            il = m.group(2).strip()
            adres = adres[:m.start()].strip(" ,;")

        tel_el = icerik.select_one("a[href^='tel:']")
        tel = tel_el.get("href", "")[4:].strip() if tel_el else ""
        if not tel:
            t = TEL.search(metin)
            tel = t.group(0) if t else ""

        eposta_el = icerik.select_one("a[href^='mailto:']")
        eposta = eposta_el.get("href", "")[7:].strip() if eposta_el else ""

        site_el = icerik.select_one("a[href^='http']:not([href*='maps'])")
        site = site_el.get("href", "").strip() if site_el else ""

        # "SADECE TEKNİK SERVİS HİZMETİ VERMEKTEDİR" gibi notlar rolü kesinleştirir
        kayit_rol = rol
        if "sadece teknik servis" in anahtar(ad):
            kayit_rol = "servis"

        out.append({
            "bayi_adi": re.sub(r"\s*\(.*?\)\s*$", "", ad).strip(),
            "il": il,
            "ilce": "",
            "adres": adres,
            "telefon": tel,
            "email": eposta,
            "website": site,
            "rol": kayit_rol,
        })
    return out
