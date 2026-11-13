"""Suzuki — satış ve servis, gömülü `stores` GeoJSON.

Kymco / Vespa ile aynı altyapı: sayfa il seçtirip haritadan konum
gösteriyor ama listenin tamamı kaynağa gömülü, tarayıcı gerekmiyor.

DİKKAT — adres tuzağı: `/motosiklet/satis.html` sayfasında bayi listesi
YOK (yalnızca test sürüşü ve destek metni, 2 telefon). Yetkili satıcı
listesi ayrı adreste:

    satış  → /tr/motosiklet/yetkili-saticilar.html    (36 satıcı)
    servis → /tr/motosiklet/yetkili-servisler.html    (41 servis)
"""

from __future__ import annotations

from .geojson_stores import coz_stores

MARKA = "Suzuki"

KAYNAKLAR = {
    "satis":  "https://www.suzuki.com.tr/tr/motosiklet/yetkili-saticilar.html",
    "servis": "https://www.suzuki.com.tr/tr/motosiklet/yetkili-servisler.html",
}
TEST = {
    ("Suzuki", "satis"):  "suzuki-satici.html",
    ("Suzuki", "servis"): "suzuki-servis.html",
}


def coz(rol: str, govde: str, url: str) -> list[dict]:
    return coz_stores(rol, govde)
