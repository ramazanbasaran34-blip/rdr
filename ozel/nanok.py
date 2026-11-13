"""Nanok — tek JSON ucu, il il gruplanmış.

Sayfadaki il seçici çalışmıyor ama arkadaki uç ülkenin tamamını veriyor:
    /api/dealers → {"cities":[{"city":..., "locations":[...]}]}

Her kayıtta `type` alanı rolü söylüyor (Bayi / Servis). Aynı firma iki
kez listeleniyorsa (hem Bayi hem Servis) store katmanı birleştiriyor.
`district` alanı "İL / İLÇE" biçiminde birleşik geliyor.
"""

from __future__ import annotations

import json
import re

from .tipler import tip_rol

MARKA = "Nanok"
UC = "https://nanok.com.tr/api/dealers"
KAYNAKLAR = {"hepsi": UC}
TEST = {("Nanok", "hepsi"): "nanok-api.json"}

ROL = {"bayi": "satis", "servis": "servis",
       "bayi ve servis": "satis_servis", "bayi/servis": "satis_servis"}


def _sade(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "")).strip()


def coz(rol: str, govde: str, url: str) -> list[dict]:
    d = json.loads(govde) if isinstance(govde, str) else govde
    out = []
    for il_blok in d.get("cities") or []:
        il = _sade(il_blok.get("city"))
        for x in il_blok.get("locations") or []:
            ad = _sade(x.get("name"))
            if not ad:
                continue
            # "ADANA / CEYHAN" → ilçe sağdaki
            ilce = ""
            ham_ilce = _sade(x.get("district"))
            if "/" in ham_ilce:
                ilce = ham_ilce.split("/")[-1].strip()
            elif ham_ilce and ham_ilce.casefold() != il.casefold():
                ilce = ham_ilce
            rol_ = tip_rol(x.get("type"), ROL, "Nanok")
            if not rol_:
                continue          # yedek parça / tanınmayan kategori
            out.append({
                "bayi_adi": ad,
                "il": il,
                "ilce": ilce,
                "adres": _sade(x.get("address")),
                "telefon": _sade(x.get("phone")),
                "email": "",
                "website": "",
                "rol": rol_,
            })
    return out
