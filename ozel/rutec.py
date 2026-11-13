"""Rutec — rutec.com.tr (Çetur Çelebi).

Site 2026 Eylül başında tamamen yenilendi. Bayi sayfası artık
"Veriler yükleniyor…" diyor: liste JavaScript ile şu uçtan geliyor:

    GET https://team.cetur.com.tr/api/Rutec/GetSatisNoktalari
    {"Code":..,"Message":..,"Data":[{Id, Ad, Sehir, Adres, Tur:[..], Telefon}]}

Eski statik sayfa gidince genel ayrıştırıcı kör kaldı; 160 kayıt
"doğrulanamadı"ya düşüyordu. Kayıtlar siteden düşmemişti, biz
göremiyorduk.

TÜRLER (Tur listesi, bir kayıtta birden çok olabilir):
    Satış Noktası  → satis
    Bölge Bayisi   → satis   (bölge bayisi de satış noktasıdır)
    Yetkili Servis → servis
"""

from __future__ import annotations

import json

MARKA = "Rutec"
UC = "https://team.cetur.com.tr/api/Rutec/GetSatisNoktalari"
JSON_UC = True          # uç JSON; Accept başlığı istenir
KAYNAKLAR = {"satis_servis": UC}
TEST = {("Rutec", "satis_servis"): "rutec-json-01.json"}

SATIS = {"satış noktası", "satis noktasi", "bölge bayisi", "bolge bayisi"}
SERVIS = {"yetkili servis"}


def _rol(turler) -> str:
    t = {str(x).strip().casefold() for x in (turler or [])}
    s = bool(t & SATIS)
    v = bool(t & SERVIS)
    return "satis_servis" if (s and v) else ("satis" if s else ("servis" if v else ""))


def coz(rol: str, govde: str, url: str, il: str | None = None) -> list[dict]:
    try:
        d = json.loads(govde)
    except json.JSONDecodeError:
        return []
    veri = d.get("Data") if isinstance(d, dict) else d
    out = []
    for k in veri or []:
        ad = (k.get("Ad") or "").strip()
        r = _rol(k.get("Tur"))
        if not ad or not r:
            continue
        out.append({
            "bayi_adi": ad,
            "il": (k.get("Sehir") or "").strip(),
            "ilce": "",                       # adresten çıkarılıyor
            "adres": (k.get("Adres") or "").strip(),
            "telefon": (k.get("Telefon") or "").strip(),
            "email": "", "website": "",
            "rol": r,
        })
    return out
