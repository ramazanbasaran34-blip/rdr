"""Vespa ve Suzuki — sayfaya gömülü `stores` GeoJSON'u.

Kymco ile aynı altyapı: harita verisi sayfaya tek tırnaklı bir JS nesnesi
olarak basılıyor, JS onu okuyup haritaya koyuyor. Geçerli JSON olmadığı
için json.loads okuyamaz; kalıpla çıkarıyoruz.

    'type': 'yetkili-satici' | 'yetkili-servis'
    'properties': {'city': 'Adana - Çukurova', 'name': ..., 'address': ...,
                   'phone1': ..., 'mail1': ...}

`city` alanı "İl - İlçe" biçiminde birleşik geliyor.
"""

from __future__ import annotations

import re

KAYIT = re.compile(
    r"\{\s*'type':\s*'(yetkili-[a-z]+)'.*?'properties':\s*\{(.*?)\}\s*\}", re.S)

ROL = {"yetkili-satici": "satis", "yetkili-servis": "servis"}


def _al(p: str, k: str) -> str:
    m = re.search(r"'" + k + r"':\s*'((?:[^'\\]|\\.)*)'", p, re.S)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def coz_stores(rol_varsayilan: str, govde: str) -> list[dict]:
    out = []
    for m in KAYIT.finditer(govde):
        tip, p = m.group(1), m.group(2)
        ad = _al(p, "name")
        if not ad:
            continue
        out.append({
            "bayi_adi": ad,
            "il": "",
            "ilce": "",
            "adres": _al(p, "address"),
            "telefon": _al(p, "phone1") or _al(p, "phone2"),
            "email": _al(p, "mail1"),
            "website": "",
            "konum": _al(p, "city"),          # "İl - İlçe" birleşik
            "rol": ROL.get(tip, rol_varsayilan),
        })
    return out
