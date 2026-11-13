"""Honda — honda.com.tr/motosiklet/bayiler-ve-servisler

Site Qwik framework'e geçti. Bayi listesi HTML'de düz metin değil;
sayfanın <script type="qwik/json"> durumunda saklanıyor. objs dizisinde
her bayi 4 ardışık string olarak duruyor:

    [ad, adres, telefon, '{"lat":..,"lng":..}']

Genel ayrıştırıcı kart/tablo aradığı için sayfayı okuyamıyordu; liste
14 gündür güncellenmiyordu. Koordinat nesnesini çıpa alıp geriye üç
alanı okuyoruz. Rol bilgisi yok — Honda tüm noktaları bayi+servis
olarak sunuyor (satis_servis).
"""

from __future__ import annotations

import json
import re

MARKA = "Honda"
UC = "https://www.honda.com.tr/motosiklet/bayiler-ve-servisler"
KAYNAKLAR = {"satis_servis": UC}
TEST = {("Honda", "satis_servis"): "m-honda.html"}

_QWIK = re.compile(r'<script type="qwik/json"[^>]*>(.*?)</script>', re.S)
_KOORD = re.compile(r'^\{"lat"')


def coz(rol: str, govde: str, url: str, il: str | None = None) -> list[dict]:
    m = _QWIK.search(govde)
    if not m:
        return []
    try:
        objs = json.loads(m.group(1)).get("objs") or []
    except json.JSONDecodeError:
        return []
    out, gorulen = [], set()
    for i, o in enumerate(objs):
        if not (isinstance(o, str) and _KOORD.match(o)) or i < 3:
            continue
        ad, adres, tel = objs[i - 3], objs[i - 2], objs[i - 1]
        if not all(isinstance(x, str) for x in (ad, adres, tel)):
            continue
        ad = ad.strip()
        # Telefon 24 karakterden uzunsa muhtemelen yanlış alan; adres kısa
        # olamaz. Basit tutarlılık.
        if not ad or len(tel) > 30 or len(adres) < 8:
            continue
        anahtar = (ad, tel)
        if anahtar in gorulen:
            continue
        gorulen.add(anahtar)
        out.append({
            "bayi_adi": ad,
            "il": "",            # adresten finalize çıkarır
            "ilce": "",
            "adres": adres.strip(),
            "telefon": tel.strip(),
            "email": "", "website": "",
            "rol": "satis_servis",
        })
    return out
