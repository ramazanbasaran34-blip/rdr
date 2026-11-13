"""Aprilia — gömülü `stores` GeoJSON.

Piaggio grubu (Vespa, Aprilia, Piaggio) ve Kymco/Suzuki aynı altyapıyı
kullanıyor: sayfa il seçtirip haritada gösteriyor ama listenin tamamı
kaynağa gömülü. Tarayıcı gerekmiyor, iki GET yeter.
"""

from __future__ import annotations

from .geojson_stores import coz_stores

MARKA = "Aprilia"

KAYNAKLAR = {
    "satis":  "https://www.aprilia.com.tr/tr/yetkili-saticilar.html",
    "servis": "https://www.aprilia.com.tr/tr/yetkili-servisler.html",
}
TEST = {
    ("Aprilia", "satis"):  "aprilia-satis.html",
    ("Aprilia", "servis"): "aprilia-servis.html",
}


def coz(rol: str, govde: str, url: str) -> list[dict]:
    return coz_stores(rol, govde)
