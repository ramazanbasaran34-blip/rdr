"""Acco (Actio) — actiomobilite.com

Site Next.js uygulamasına geçti; bayi listesi HTML'de yok, şu uçtan
geliyor:

    GET https://actiomobilite.com/store/dealers
    {"dealers":[{name, address, city, district, phone, is_active, ...}]}

Genel ayrıştırıcı hiç kayıt bulamıyor, 5 kayıt "doğrulanamadı"ya
düşmüştü; oysa uçta 5 kayıt duruyor. Site satış/servis ayrımı
yapmıyor; kayıtlar kaynaktaki role (satis_servis) göre yazılıyor.
Telefon alanında birden çok numara satır sonuyla geliyor; ilki alınır.
"""

from __future__ import annotations

import json

MARKA = "Acco"
UC = "https://actiomobilite.com/store/dealers"
JSON_UC = True          # uç JSON; Accept başlığı istenir
# Uç, tarayıcının gönderdiği genel mağaza anahtarını (Medusa altyapısı,
# ön yüz paketinde açıkça duran "publishable key") istiyor; onsuz HTTP 400.
BASLIKLAR = {
    "x-publishable-api-key":
        "pk_856e935d5de1cc753b322fc824428ddc379db2c947e8bdc16c52bb05f2362580",
    "Referer": "https://actiomobilite.com/bayiler",
    "Origin": "https://actiomobilite.com",
}
KAYNAKLAR = {"satis_servis": UC}
TEST = {("Acco", "satis_servis"): "acco-json-02.json"}


def coz(rol: str, govde: str, url: str, il: str | None = None) -> list[dict]:
    try:
        d = json.loads(govde)
    except json.JSONDecodeError:
        return []
    veri = (d.get("dealers") or d.get("data")) if isinstance(d, dict) else d
    out = []
    for k in veri or []:
        if k.get("is_active") is False:
            continue
        ad = (k.get("name") or "").strip()
        if not ad:
            continue
        tel = (k.get("phone") or "").split("\n")[0].strip()
        out.append({
            "bayi_adi": ad,
            "il": (k.get("city") or "").strip(),
            "ilce": (k.get("district") or "").strip(),
            "adres": (k.get("address") or "").strip(),
            "telefon": tel,
            "email": (k.get("email") or "") or "",
            "website": "",
            "rol": "satis_servis",
        })
    return out
