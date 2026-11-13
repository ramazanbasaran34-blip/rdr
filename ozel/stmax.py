"""STMax — il bazlı sayfa, `.servis-kart` kartları.

Sayfadaki il açılır kutusu `onchange="location = this.value"` yapıyor;
yani seçenek değerleri doğrudan adres. Ajax yok, ViewState yok:

    https://stmax.com.tr/iller/<il-slug>/

İl listesi /yetkili-servisler/ sayfasındaki <select id="il-secimi">
içinde tam adres olarak duruyor (63 il).

Kart yapısı:
    <div class="servis-kart">
      <h3>MUSTAFA ARIKAN / ARIKAN MOTORS</h3>
      <p><strong>ÇUBUK</strong></p>            ← ilçe
      <p><strong>Adres:</strong><br>...</p>
      <p><strong>Telefon:</strong> <a href="tel:...">...</a></p>

NOT: Sayfa yer yer bozuk kodlanmış Türkçe içeriyor
("CUMHURÝYET" gibi); normalize.fold bunu zaten onarıyor.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .tr import anahtar

MARKA = "STMax"

KAYNAKLAR = {"servis": "https://stmax.com.tr/yetkili-servisler/"}
TEST = {("STMax", "servis"): "stmax-ankara.html"}
TEST_IL = "Ankara"

IL_SECICI = "il-secimi"


def il_sluglari(govde: str) -> list[tuple[str, str]]:
    """(tam adres, il adı) — seçenek değerleri zaten tam adres."""
    soup = BeautifulSoup(govde, "html.parser")
    sec = soup.find("select", id=IL_SECICI)
    if not sec:
        return []
    out = []
    for o in sec.find_all("option"):
        u = (o.get("value") or "").strip()
        ad = re.sub(r"\s+", " ", o.get_text(" ")).strip()
        if u.startswith("http") and ad:
            out.append((u, ad))
    return out


def il_url(rol: str, adres: str) -> str:
    return adres          # değer zaten tam adres


def _m(el) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ")).strip() if el else ""


def coz(rol: str, govde: str, url: str, il: str | None = None) -> list[dict]:
    soup = BeautifulSoup(govde, "html.parser")
    out: list[dict] = []
    gorulen: set[tuple[str, str]] = set()

    for kart in soup.select(".servis-kart"):
        ad = _m(kart.find(["h3", "h2", "h4"]))
        if not ad:
            continue

        ilce = ""
        adres = ""
        for p in kart.find_all("p"):
            metin = _m(p)
            if not metin:
                continue
            etiket = anahtar(_m(p.find("strong")) if p.find("strong") else "")
            if etiket.startswith("adres"):
                adres = re.sub(r"(?i)^adres\s*:?\s*", "", metin).strip()
            elif etiket.startswith(("telefon", "tel")):
                continue
            elif not ilce and len(metin) < 40:
                ilce = metin           # ilçe tek başına kalın yazılmış

        a = kart.select_one("a[href^='tel:']")
        tel = a.get("href", "")[4:].strip() if a else ""

        k = (anahtar(ad), anahtar(ilce))
        if k in gorulen:
            continue
        gorulen.add(k)

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
