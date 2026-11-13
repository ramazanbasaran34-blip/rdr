"""Taktas — taktas.com.tr

Bayi sayfası tıklanabilir Türkiye haritasına dönüştü; liste HTML'de
yok, harita şu dosyadan besleniyor:

    GET https://taktas.com.tr/turkiyemap/turkiyemap.json
    [{Yetkili, Adres, İl, İlçe, Telefon}, ...]

Genel ayrıştırıcı haritanın il adlarını kayıt sanıyordu ("88 kayıt,
başarılı") ama hiçbiri geçerli değildi; 41 gerçek kayıt
"doğrulanamadı"ya düşmüştü. Uçta 44 kayıt var.

ROL: dosya tür bilgisi taşımıyor. Sayfa "Bayi ve Servis Ağı" başlıklı
tek liste; noktalar satis_servis olarak yazılıyor.
"""

from __future__ import annotations

import json

MARKA = "Taktas"
UC = "https://taktas.com.tr/turkiyemap/turkiyemap.json"
JSON_UC = True          # uç JSON; Accept başlığı istenir
KAYNAKLAR = {"satis_servis": UC}
TEST = {("Taktas", "satis_servis"): "taktas-json-01.json"}


def coz(rol: str, govde: str, url: str, il: str | None = None) -> list[dict]:
    try:
        d = json.loads(govde)
    except json.JSONDecodeError:
        return []
    out = []
    for k in d if isinstance(d, list) else []:
        ad = (k.get("Yetkili") or "").strip()
        if not ad:
            continue
        out.append({
            "bayi_adi": ad,
            "il": (k.get("İl") or k.get("Il") or "").strip().title(),
            "ilce": (k.get("İlçe") or k.get("Ilce") or "").strip().title(),
            "adres": (k.get("Adres") or "").strip(),
            "telefon": (k.get("Telefon") or "").strip(),
            "email": "", "website": "",
            "rol": "satis_servis",
        })
    return out
