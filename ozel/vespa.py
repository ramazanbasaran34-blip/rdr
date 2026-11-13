"""Vespa — gömülü `stores` GeoJSON (Kymco/Suzuki ile aynı altyapı)."""

from __future__ import annotations

from .geojson_stores import coz_stores

MARKA = "Vespa"

KAYNAKLAR = {
    "satis":  "https://www.vespa.com.tr/tr/yetkili-saticilar.html",
    "servis": "https://www.vespa.com.tr/tr/yetkili-servisler.html",
}
TEST = {
    ("Vespa", "satis"):  "vespa-satis.html",
    ("Vespa", "servis"): "vespa-servis.html",
}


def coz(rol: str, govde: str, url: str) -> list[dict]:
    return coz_stores(rol, govde)
