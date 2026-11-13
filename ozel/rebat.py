"""Rebat — tek sayfada tüm ağ, kart listesi.

Sayfa Türkiye haritası gösteriyor ve ile tıklatıyor ama liste sunucudan
TAM geliyor; JS onu sadece açıp kapatıyor (`switchview`). Tek GET yeter.

DİKKAT — eski adres: brands.yaml'de kayıtlı
`/satis-ve-servisler-cloned-111-2/` 404 veriyordu. Doğrusu `/servis/`.

Kart yapısı:
    <h3>BURSA / MUSTAFAKEMALPAŞA | BAYİ</h3>      ← il / ilçe | rol
    <div class="servisler">
      <h4>SARAÇOĞLU EV BÜRO ...</h4>              ← firma
      <p><span>Adres</span><br>...</p>
      <p><span>Yetkili</span><br>...</p>
      <p><span>GSM</span><br>0 542 438 03 80</p>
      <p><span>E-posta</span><br>...</p>

Sayfa bozuk kodlanmış Türkçe içeriyor ("MUSTAFAKEMALPAÅA"); yakalayıcı
UTF-8 okuduğu için burada onarım yapıyoruz.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .tr import anahtar

MARKA = "Rebat"

KAYNAKLAR = {"hepsi": "https://rebatmotor.com/servis/"}
TEST = {("Rebat", "hepsi"): "rebat-servis.html"}

TEL = re.compile(r"(?:\+90|0)[\s\(\)\-/\.]*\d{3}[\s\(\)\-/\.]*\d{3}[\s\-/\.]*\d{2}[\s\-/\.]*\d{2}")


def _onar(t: str) -> str:
    """Çift kodlanmış Türkçeyi düzeltir (Ã, Å, Ä içeriyorsa)."""
    if not t or not any(c in t for c in "ÃÅÄ"):
        return t
    try:
        return t.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return t


def _m(el) -> str:
    return _onar(re.sub(r"\s+", " ", el.get_text(" ")).strip()) if el else ""


def _alan(kutu, etiket: str) -> str:
    """Etiketli <p> bloğundan değeri çeker (Adres, GSM, E-posta...)."""
    for p in kutu.find_all("p"):
        bas = p.find("span")
        if not bas:
            continue
        if anahtar(_m(bas)).startswith(anahtar(etiket)):
            metin = _m(p)
            return re.sub(r"(?i)^" + re.escape(_m(bas)) + r"\s*", "", metin).strip()
    return ""


def coz(rol: str, govde: str, url: str) -> list[dict]:
    soup = BeautifulSoup(govde, "html.parser")
    out: list[dict] = []
    gorulen: set[tuple[str, str]] = set()

    for baslik in soup.find_all("h3"):
        b = _m(baslik)
        if "/" not in b:
            continue

        # "BURSA / MUSTAFAKEMALPAŞA | BAYİ"
        sol, _, rol_metni = b.partition("|")
        il, _, ilce = sol.partition("/")
        il, ilce = il.strip(), ilce.strip()
        if not il:
            continue

        r = anahtar(rol_metni)
        if "bayi" in r and "servis" in r:
            kayit_rol = "satis_servis"
        elif "servis" in r:
            kayit_rol = "servis"
        elif "bayi" in r:
            kayit_rol = "satis"
        else:
            kayit_rol = "satis_servis"

        kutu = baslik.find_next(class_="servisler") or baslik.parent
        ad = _m(kutu.find("h4"))
        if not ad:
            continue

        tel = _alan(kutu, "GSM") or _alan(kutu, "Telefon")
        t = TEL.search(tel)
        tel = t.group(0) if t else tel

        anahtar_kayit = (anahtar(ad), anahtar(ilce))
        if anahtar_kayit in gorulen:
            continue
        gorulen.add(anahtar_kayit)

        out.append({
            "bayi_adi": ad,
            "il": il,
            "ilce": ilce,
            "adres": _alan(kutu, "Adres"),
            "telefon": tel,
            "email": _alan(kutu, "E-posta"),
            "website": "",
            "rol": kayit_rol,
        })
    return out
