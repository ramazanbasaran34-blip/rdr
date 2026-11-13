"""Kuralkan (Bajaj ve Kanuni) — Next.js flight verisi.

ESKİ TARİF NEDEN EKSİK GELİYORDU
Tarif `?city={sayi}` ile 1..81 gezip tarayıcıyla okuyordu. Oysa
`city` parametresi SUNUCUDA hiç işlenmiyor: hangi il verilirse verilsin
aynı sayfa dönüyor, süzme tamamen tarayıcıda yapılıyor. Tarayıcı
taraması bazı illerde listeyi yakalayamadığı için 98 satış noktasının
yalnızca 87'si geliyordu.

DOĞRUSU
Liste sayfaya gömülü: Next.js içeriği `self.__next_f.push([1,"..."])`
parçaları hâlinde basıyor; parçalar birleştirilince içinde
`"dealers":[{...}]` dizisi çıkıyor. Tek GET yeter, il gezmeye gerek yok.
Sayfa "98 nokta" diye de yazıyor, sağlama için kullanılabilir.

Kayıt alanları rolü doğrudan veriyor:
    shop=true  → satış
    service=true → servis
    spareparts → yedek parça (tek başınaysa nokta sayılmaz)
    type: shop_and_service / shop / service

Bajaj ve Kanuni aynı ağı paylaşıyor (ikisi de Kuralkan markası).
"""

from __future__ import annotations

import json
import re

MARKA = "Bajaj"
MARKALAR = ("Bajaj", "Kanuni")

KAYNAKLAR = {
    "satis":  "https://www.ekuralkan.com/motosiklet-satis-noktalari",
    "servis": "https://www.ekuralkan.com/motosiklet-teslimat-noktalari",
}
TEST = {
    ("Bajaj", "satis"): "kuralkan-satis-hepsi.html",
}

PARCA = re.compile(r'self\.__next_f\.push\(\[1,\s*"((?:[^"\\]|\\.)*)"\]\)')


def _flight_metni(govde: str) -> str:
    """__next_f parçalarını birleştirip düz metne çevirir."""
    out = []
    for p in PARCA.findall(govde):
        try:
            out.append(json.loads('"' + p + '"'))
        except json.JSONDecodeError:
            continue
    return "".join(out)


def _dizi_ayikla(metin: str) -> list[dict]:
    """`"dealers":[...]` dizisini parantez sayarak çıkarır.

    Metin geçerli JSON değil (React flight biçimi), o yüzden diziyi
    baştan sona kendimiz tarıyoruz.
    """
    for anahtar in ('"dealers":', '"points":', '"locations":'):
        i = metin.find(anahtar)
        if i < 0:
            continue
        bas = metin.find("[", i)
        if bas < 0:
            continue
        derinlik, j, tirnak, kacis = 0, bas, False, False
        while j < len(metin):
            c = metin[j]
            if kacis:
                kacis = False
            elif c == "\\":
                kacis = True
            elif c == '"':
                tirnak = not tirnak
            elif not tirnak:
                if c == "[":
                    derinlik += 1
                elif c == "]":
                    derinlik -= 1
                    if derinlik == 0:
                        try:
                            return json.loads(metin[bas:j + 1])
                        except json.JSONDecodeError:
                            return []
            j += 1
    return []


def _rol(x: dict) -> str:
    satis = bool(x.get("shop"))
    servis = bool(x.get("service"))
    if not (satis or servis):
        # yalnızca yedek parça noktası → satış/servis noktası değil
        return ""
    if satis and servis:
        return "satis_servis"
    return "satis" if satis else "servis"


def coz(rol: str, govde: str, url: str) -> list[dict]:
    kayitlar = _dizi_ayikla(_flight_metni(govde))
    out = []
    gorulen = set()
    for x in kayitlar:
        r = _rol(x)
        if not r:
            continue
        ad = re.sub(r"\s+", " ", (x.get("erp_user_name") or x.get("name") or "")).strip()
        if not ad:
            continue
        # Aynı firmanın aynı ilde BİRDEN ÇOK şubesi olabiliyor
        # (Ankara'da Favori Moto, Hatay'da Kenan Uslu gibi). Anahtara
        # ilçe ve adres de girmezse gerçek noktalar eleniyordu.
        anahtar = (ad.casefold(), (x.get("city") or "").casefold(),
                   (x.get("district") or "").casefold(),
                   re.sub(r"\s+", " ", (x.get("address") or "")).strip().casefold())
        if anahtar in gorulen:
            continue
        gorulen.add(anahtar)
        out.append({
            "bayi_adi": ad,
            "il": (x.get("city") or "").strip(),
            "ilce": (x.get("district") or "").strip(),
            "adres": re.sub(r"\s+", " ", (x.get("address") or "")).strip(),
            "telefon": (x.get("phone") or "").strip(),
            "email": (x.get("email") or "").strip(),
            "website": "",
            "rol": r,
        })
    return out
