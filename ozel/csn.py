"""CSN — il bazlı sayfalar.

Ana sayfada Türkiye haritası var; her ile tıklamak ayrı bir adrese
götürüyor. Haritayı tıklamaya gerek yok, bağlantılar kaynakta duruyor:

    /satis-noktalarimiz/{il-slug}
    /servis-noktalarimiz/{il-slug}

Her kayıt bir `.pxl-grid-item`; başlık "İlçe - Firma Adı" biçiminde,
adres `.pxl-description`, telefon `.pxl-phone` içinde.
İl bilgisi sayfada yazmıyor, URL'den geliyor.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

MARKA = "CSN"

TABAN = {
    "satis":  "https://csnmotor.com.tr/satis-noktalarimiz/{slug}",
    "servis": "https://csnmotor.com.tr/servis-noktalarimiz/{slug}",
}
KAYNAKLAR = TABAN
TEST = {
    ("CSN", "satis"):  "csn-satis-ank.html",
    ("CSN", "servis"): "csn-servis-ank.html",
}
TEST_IL = "Ankara"

# Ana sayfadaki il bağlantıları buradan okunuyor
IL_BAGLANTI = {
    "satis":  re.compile(r'href="(?:https?://[^"]*)?/satis-noktalarimiz/([a-z0-9\-]+)"'),
    "servis": re.compile(r'href="(?:https?://[^"]*)?/servis-noktalarimiz/([a-z0-9\-]+)"'),
}


def il_url(rol: str, slug: str) -> str:
    return TABAN[rol].format(slug=slug)


def il_sluglari(rol: str, govde: str) -> list[str]:
    return sorted(set(IL_BAGLANTI[rol].findall(govde)))


def _m(el) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ")).strip() if el else ""


def coz(rol: str, govde: str, url: str, il: str | None = None) -> list[dict]:
    soup = BeautifulSoup(govde, "html.parser")
    out = []
    for kart in soup.select(".pxl-grid-item"):
        baslik = _m(kart.find(["h5", "h4", "h3"]))
        if not baslik:
            continue

        # "Altındağ - Tayfun Motor" → ilçe + ad
        ilce, ad = "", baslik
        if " - " in baslik:
            sol, sag = baslik.split(" - ", 1)
            if sol and sag:
                ilce, ad = sol.strip(), sag.strip()
        if not ad:
            continue

        adres = _m(kart.select_one(".pxl-description"))
        tel = _m(kart.select_one(".pxl-phone"))
        out.append({
            "bayi_adi": ad,
            "il": il or "",
            "ilce": ilce,
            "adres": adres,
            "telefon": tel,
            "email": "",
            "website": "",
            "rol": rol,
        })
    return out
