"""Yuki — il parametreli sayfa, düz tablo.

Sayfa "konumumu kullan" düğmesiyle tarayıcı konumu istiyor, ama bu
sadece bir KISAYOL: konum alınınca en yakın il bulunup
`?province=<slug>` adresine yönlendiriliyor. Yani konum izni olmadan
her ile doğrudan gidilebiliyor.

İl listesi ana sayfadaki `provinces` dizisinde duruyor; üstelik il
başına kayıt sayısını da veriyor (kapsam kontrolü için kullanışlı).

    satış  → /satis-noktalari/?province=<slug>
    servis → /servis-noktalari/?province=<slug>

Tablo düzeni her iki sayfada aynı:
    firma | ilçe | telefon | adres | (buton)
"""

from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup

from .tr import anahtar

MARKA = "Yuki"

TABAN = {
    "satis":  "https://yukimotor.com.tr/satis-noktalari/",
    "servis": "https://yukimotor.com.tr/servis-noktalari/",
}
KAYNAKLAR = TABAN
TEST = {
    ("Yuki", "satis"):  "yuki-satis-ank.html",
    ("Yuki", "servis"): "yuki-servis-ank.html",
}
TEST_IL = "Ankara"

PROVINCES = re.compile(r"provinces\s*=\s*(\[.*?\])\s*;", re.S)
# Başlık satırını ayıklamak için: ilk hücrede marka adı geçiyor
BASLIK_IZ = ("yuki motor", "ilce", "telefon", "adres")


def il_url(rol: str, slug: str) -> str:
    return f"{TABAN[rol]}?province={slug}"


def il_sluglari(govde: str) -> list[tuple[str, str]]:
    """Ana sayfadaki `provinces` dizisinden (slug, ad)."""
    m = PROVINCES.search(govde)
    if not m:
        return []
    ham = m.group(1)
    # Dizi geçerli JSON değil (anahtarlar tırnaksız); alanları tek tek çek.
    out = []
    for blok in re.finditer(r"\{[^{}]*\}", ham):
        b = blok.group(0)
        ad = re.search(r"name\s*:\s*[\"']([^\"']+)", b)
        slug = re.search(r"slug\s*:\s*[\"']([^\"']+)", b)
        if ad and slug:
            out.append((slug.group(1), ad.group(1)))
    return out


def _m(el) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ")).strip() if el else ""


def coz(rol: str, govde: str, url: str, il: str | None = None) -> list[dict]:
    soup = BeautifulSoup(govde, "html.parser")
    out: list[dict] = []
    gorulen: set[tuple[str, str]] = set()

    for tr in soup.select("table tr"):
        hucre = tr.find_all("td")
        if len(hucre) < 4:
            continue                      # başlık satırı ya da eksik satır

        ad = _m(hucre[0])
        ilce = _m(hucre[1])
        tel_ham = _m(hucre[2])
        adres = _m(hucre[3])

        if not ad or anahtar(ad).startswith(BASLIK_IZ[0]):
            continue

        # Hücrede iki numara olabiliyor ("0312 ... 0535 ..."); ilkini al.
        tel = ""
        m = re.search(r"(?:\+90|0)[\s\(\)\-/\.]*\d{3}[\s\(\)\-/\.]*"
                      r"\d{3}[\s\-/\.]*\d{2}[\s\-/\.]*\d{2}", tel_ham)
        if m:
            tel = m.group(0)

        anahtar_kayit = (anahtar(ad), anahtar(ilce))
        if anahtar_kayit in gorulen:
            continue
        gorulen.add(anahtar_kayit)

        out.append({
            "bayi_adi": ad,
            "il": il or "",
            "ilce": ilce,
            "adres": adres,
            "telefon": tel,
            "email": "",
            "website": "",
            "rol": rol,
        })
    return out
