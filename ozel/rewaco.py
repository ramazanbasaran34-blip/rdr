"""Rewaco — Elementor sekmeleri; her sekme bir il.

Küçük bir ağ (9 nokta). Sayfada il seçici yok; iller sekme başlığı
olarak duruyor ve içerikleri aynı sayfada geliyor. Yani tek GET yeter,
il il gezmeye gerek yok.

Sekme başlıkları: Merkez, İstanbul, Ankara, İzmir, Kayseri, Batman,
Van, Amasya, Kahramanmaraş. "Merkez" firmanın kendi merkezi.

Her panelde Elementor "icon box" kutuları var:
    e-posta · telefon · adres
Adres sonu bazen "İZMİR / BORNOVA" (il önce), bazen "Altındağ/Ankara"
(ilçe önce) biçiminde; il zaten sekmeden bilindiği için diğer parça
ilçe kabul ediliyor.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .tr import anahtar

MARKA = "Rewaco"

KAYNAKLAR = {
    "satis":  "https://rewaco.com.tr/bayiler/",
    "servis": "https://rewaco.com.tr/servis/",
}
TEST = {
    ("Rewaco", "servis"): "rewaco-srv2.html",
}

TEL = re.compile(r"(?:\+90|0)[\s\(\)\-/\.]*\d{3}[\s\(\)\-/\.]*\d{3}[\s\-/\.]*\d{2}[\s\-/\.]*\d{2}")


def _m(el) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ")).strip() if el else ""


def coz(rol: str, govde: str, url: str, il: str | None = None) -> list[dict]:
    soup = BeautifulSoup(govde, "html.parser")

    basliklar = [_m(x) for x in soup.select(".e-n-tab-title, [role=tab]")]
    paneller = soup.select("[role=tabpanel]")
    if not paneller:
        return []

    out: list[dict] = []
    gorulen: set[tuple[str, str]] = set()

    for i, panel in enumerate(paneller):
        sekme_il = basliklar[i] if i < len(basliklar) else ""
        # "Merkez" sekmesi firmanın kendi merkezi; il adı değil.
        panel_il = "" if anahtar(sekme_il) == "merkez" else sekme_il

        kutular = [_m(k) for k in panel.select(
            ".elementor-icon-box-description, .elementor-icon-box-title")]
        kutular = [k for k in kutular if k]
        if not kutular:
            continue

        eposta = next((k for k in kutular if "@" in k), "")
        tel = ""
        for k in kutular:
            m = TEL.search(k)
            if m:
                tel = m.group(0)
                break
        adres = ""
        for k in kutular:
            if "@" in k or TEL.fullmatch(k.strip()):
                continue
            if len(k) > len(adres):
                adres = k
        if not adres and not tel:
            continue

        # Firma adı ÖNCE harita bağlantısından: paneldeki başlık
        # sayfanın genel başlığı ("İletişim Adresleri") olabiliyor.
        ad = ""
        cerceve = panel.find("iframe", src=True)
        if cerceve:
            from urllib.parse import unquote
            # !2s bölümü birden çok kez geçiyor; sonuncular dil kodu
            # ("!2str!2str"). En uzun ve anlamlı olanı seçiyoruz.
            adaylar = [unquote(x).replace("+", " ").strip()
                       for x in re.findall(r"!2s([^!]+)", cerceve["src"])]
            adaylar = [a for a in adaylar
                       if len(a) > 3 and anahtar(a) not in ("tr", "en")]
            if adaylar:
                ad = max(adaylar, key=len)

        if not ad:
            bas = panel.find(["h1", "h2", "h3", "h4", "h5", "h6"])
            aday = _m(bas)
            # Genel sayfa başlıklarını firma adı sayma
            if aday and anahtar(aday) not in ("iletisim adresleri", "iletisim",
                                              "adres", "servis", "bayiler"):
                ad = aday
        if not ad:
            ad = f"Rewaco {sekme_il}".strip()

        # Adres sonundaki "X / Y" — il sekmeden biliniyor, diğeri ilçe
        ilce = ""
        m = re.search(r"([^/,]{2,30})\s*/\s*([^/,]{2,30})\s*$", adres)
        if m:
            sol, sag = m.group(1).strip(), m.group(2).strip()
            ilce = sag if anahtar(sol) == anahtar(panel_il) else sol
            ilce = re.sub(r"^\d+\s*", "", ilce).strip()
            if anahtar(ilce) == anahtar(panel_il):
                ilce = ""

        anahtar_kayit = (anahtar(ad), anahtar(panel_il))
        if anahtar_kayit in gorulen:
            continue
        gorulen.add(anahtar_kayit)

        out.append({
            "bayi_adi": ad,
            "il": panel_il,
            "ilce": ilce,
            "adres": adres,
            "telefon": tel,
            "email": eposta,
            "website": "",
            "rol": rol,
        })
    return out
