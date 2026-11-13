"""Arora — arora.com.tr/hizmet-noktalari

8 Eylül 2026'da sayfa değişti: liste artık il seçilmeden görünmüyor
("Şehir Seçin → Ara"), eski tür onay kutusu (B/S/BS) kalktı. Genel
ayrıştırıcı kart bulamayınca 1.003 kayıt "hatalı"ya düştü.

Ama sayfanın içinde bütün Türkiye'nin listesi gömülü duruyor:

    <script> let bayiler = [{id, code, ilce, lat, lng, creator, ad,
                             seflink, var_1, var_2, var_3, summary, sehir}, ...]

    creator: "B" → satis · "S" → servis · "BS" → satis_servis
    var_1   : telefon (var_2 ikinci numara)
    summary : adres
    sehir/ilce: il ve ilçe

Tek istekle 1.247 kayıt; il gezmeye gerek yok.
"""

from __future__ import annotations

import json
import re

MARKA = "Arora"
UC = "https://arora.com.tr/hizmet-noktalari"
KAYNAKLAR = {"satis_servis": UC}
TEST = {("Arora", "satis_servis"): "arora-sayfa.html"}

_DIZI = re.compile(r"\bbayiler\s*=\s*(\[.*?\])\s*;", re.S)
ROL = {"B": "satis", "S": "servis", "BS": "satis_servis"}


def coz(rol: str, govde: str, url: str, il: str | None = None) -> list[dict]:
    m = _DIZI.search(govde)
    if not m:
        return []
    try:
        d = json.loads(m.group(1))
    except json.JSONDecodeError:
        return []
    out = []
    for k in d:
        ad = (k.get("ad") or "").strip()
        r = ROL.get((k.get("creator") or "").strip().upper())
        if not ad or not r:
            continue
        adres = re.sub(r"\s+", " ", (k.get("summary") or "")).strip()
        out.append({
            "bayi_adi": ad,
            "il": (k.get("sehir") or "").strip(),
            "ilce": (k.get("ilce") or "").strip().title(),
            "adres": adres,
            "telefon": (k.get("var_1") or k.get("var_2") or "").strip(),
            "email": "", "website": "",
            "rol": r,
        })
    return out
