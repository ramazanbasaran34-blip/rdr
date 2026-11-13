"""Kymco — gömülü `stores` GeoJSON, tek sayfada satış ve servis birlikte.

Aprilia/Piaggio/Vespa/Suzuki ile aynı altyapı. Farkı: Kymco satış ve
servisi TEK sayfada veriyor, rol ayrımı kayıttaki 'type' alanından
geliyor (yetkili-satici / yetkili-servis).
"""

from __future__ import annotations

from .geojson_stores import coz_stores

MARKA = "Kymco"

KAYNAKLAR = {"hepsi": "https://www.kymco.com.tr/tr/satis-servis-agi.html"}
TEST = {("Kymco", "hepsi"): "kymco-agi.html"}


def coz(rol: str, govde: str, url: str) -> list[dict]:
    return coz_stores("satis", govde)
