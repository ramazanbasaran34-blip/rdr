"""Musatti — il koduna göre JSON, içinde HTML parçası.

İki ayrı uç, plaka koduyla (01..81):
    /ajax-bayi-listesi.php?city=NN
    /ajax-servis-listesi.php?city=NN

Yanıt {"status":true,"count":N,"html":"<div>...</div>"} biçiminde;
asıl veri `html` alanındaki parçada. Her kayıt bir `.faq-contain`,
başlıkta rozet (Bayi/Servis), ad `h2` içinde.
"""

from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup

MARKA = "Musatti"

TABAN = {
    "satis":  "https://musattimotor.com/ajax-bayi-listesi.php?city={kod}",
    "servis": "https://musattimotor.com/ajax-servis-listesi.php?city={kod}",
}
KAYNAKLAR = TABAN
TEST = {
    ("Musatti", "satis"):  "musatti-bayi06.json",
    ("Musatti", "servis"): "musatti-srv06.json",
}
TEST_IL = "Ankara"          # test dosyaları 06 ile alındı

TEL = re.compile(r"(\+?\d[\d\s()\-/]{8,})")


def il_url(rol: str, kod: str) -> str:
    return TABAN[rol].format(kod=kod)


def _metin(el) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ")).strip() if el else ""


def coz(rol: str, govde: str, url: str, il: str | None = None) -> list[dict]:
    d = json.loads(govde) if isinstance(govde, str) else govde
    parca = d.get("html") or ""
    if not parca:
        return []

    soup = BeautifulSoup(parca, "html.parser")
    out = []
    for kart in soup.select(".faq-contain"):
        ad = _metin(kart.find(["h2", "h3"]))
        if not ad:
            continue

        rozet = _metin(kart.select_one(".badge")).casefold()
        if "bayi" in rozet and "servis" in rozet:
            rol_ = "satis_servis"
        elif "servis" in rozet:
            rol_ = "servis"
        elif "bayi" in rozet:
            rol_ = "satis"
        else:
            rol_ = rol

        govde_metin = _metin(kart)
        tel = ""
        a = kart.select_one("a[href^='tel:']")
        if a:
            tel = a.get("href", "")[4:].strip()
        else:
            m = TEL.search(govde_metin)
            tel = m.group(1).strip() if m else ""

        # Adres ikinci <h5>'te; birincisi telefon bağlantısı.
        # Sonunda "İlçe/İl" yazıyor, ilçeyi finalize buradan çıkarıyor.
        adres = ""
        for h5 in kart.find_all("h5"):
            if h5.find("a", href=True) and h5.find("a")["href"].startswith("tel:"):
                continue
            t = _metin(h5)
            if t and t != ad and len(t) > len(adres):
                adres = t
        out.append({
            "bayi_adi": ad,
            "il": il or "",
            "ilce": "",
            "adres": adres,
            "telefon": tel,
            "email": "",
            "website": "",
            "rol": rol_,
        })
    return out
