"""Kral Motor — sayfaya gömülü JSON dizisi.

Sayfada il seçici var ama liste sunucudan tam geliyor; JS onu sadece
süzüyor. Kayıtlar kaynakta düz JSON nesneleri hâlinde duruyor:

    {"id":749,"name":"...","address":"...","district":"ÇUKUROVA",
     "city":"ADANA","phone1":"5375906519","phone2":"", ...}

Satış ve servis AYRI sayfalarda, o yüzden rol kaynaktan geliyor.
Tarayıcı gerekmiyor; iki GET yeter.
"""

from __future__ import annotations

import json
import re

MARKA = "Kral"

KAYNAKLAR = {
    "satis":  "https://kralmotor.tr/SalesDealer",
    "servis": "https://kralmotor.tr/Service",
}
TEST = {
    ("Kral", "satis"):  "kral-satis.html",
    ("Kral", "servis"): "kral-servis.html",
}

# name/address/district/city/phone1 alanlarının hepsini taşıyan nesneler
NESNE = re.compile(
    r'\{"id":\d+,"name":".*?"createdDate":"[^"]*"\}', re.S)


def _al(blok: str, anahtar: str) -> str:
    m = re.search(r'"' + anahtar + r'":"((?:[^"\\]|\\.)*)"', blok)
    if not m:
        return ""
    try:
        return json.loads('"' + m.group(1) + '"').strip()
    except Exception:  # noqa: BLE001
        return m.group(1).strip()


def coz(rol: str, govde: str, url: str) -> list[dict]:
    out = []
    gorulen = set()
    for m in NESNE.finditer(govde):
        blok = m.group(0)
        if '"isActive":false' in blok:
            continue
        ad = _al(blok, "name")
        if not ad:
            continue
        anahtar = (ad, _al(blok, "address"))
        if anahtar in gorulen:
            continue
        gorulen.add(anahtar)
        out.append({
            "bayi_adi": ad,
            "il": _al(blok, "city"),
            "ilce": _al(blok, "district"),
            "adres": _al(blok, "address"),
            "telefon": _al(blok, "phone1") or _al(blok, "phone2"),
            "email": "",
            "website": "",
            "rol": rol,
        })
    return out
