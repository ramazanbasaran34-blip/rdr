"""FCM — fcmmotor.com

NEDEN ÖZEL MODÜL
Sayfa il il sekmelere ayrılmış; İL bilgisi kartın içinde DEĞİL, kartı
saran sekmenin üstünde:

    div[role=tabpanel][data-alias="adana"]
      <h2>ADANA Satış Noktalarımız</h2>
      div.card
        p.c-ff        → İLÇE  (SEYHAN, CEYHAN, KOZAN ...)
        p.text-black  → firma adı
        p.c-7a        → adres
        a[href^=tel:] → telefon

Genel tarif kartları alabiliyor ama üstteki sekmeyi göremiyor: 417
kaydın 372'sinin ili BOŞ kalıyordu. Adana'da 13 satış noktası varken
listede 5 görünüyordu, çünkü kalan 8'i "ilsiz" havuzdaydı.

Adreslerde il/ilçe yazmıyor ("ÇINARLI MAH. TURHAN CEMAL BERİKER BLV. -
58 A"), yani konum adresten de çıkarılamıyor; tek kaynak sekme başlığı.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from bayiradar.normalize import ILLER, fold

MARKA = "FCM"

KAYNAKLAR = {
    "satis": "https://fcmmotor.com/bayiler",
    "servis": "https://fcmmotor.com/yetkili-servisler",
}
TEST = {("FCM", "satis"): "m-fcm.html"}

_IL_FOLD = {fold(i): i for i in ILLER}
# "ADANA Satış Noktalarımız" / "AFYONKARAHİSAR Satış Noktaları"
_BASLIK_EK = re.compile(
    r"\s*(satış|satis|servis|yetkili)\s*(noktalarımız|noktalari|noktaları|"
    r"noktalarimiz|servislerimiz)?\s*$", re.I)


def _sade(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "")).strip()


def _il_bul(panel) -> str:
    """Sekmenin ilini bulur: önce başlık, olmazsa data-alias.

    İstanbul sitede ikiye ayrılmış: "İSTANBUL ASYA" ve "İSTANBUL
    AVRUPA". Bunlar ayrı il değil; başlığın ilk kelimesi il adıysa
    onu kullanıyoruz, yoksa 7 kayıt ilsiz kalıyordu.
    """
    adaylar = []
    h = panel.find(["h1", "h2", "h3"])
    if h:
        adaylar.append(_BASLIK_EK.sub("", _sade(h.get_text(" ", strip=True))))
    if panel.get("data-alias"):
        adaylar.append(panel["data-alias"].replace("-", " "))
    for a in adaylar:
        if fold(a) in _IL_FOLD:
            return _IL_FOLD[fold(a)]
        # "İSTANBUL ASYA" -> ilk kelime il adı mı?
        ilk = a.split()[0] if a.split() else ""
        if fold(ilk) in _IL_FOLD:
            return _IL_FOLD[fold(ilk)]
    return ""


def coz(rol: str, govde: str, url: str, il: str | None = None) -> list[dict]:
    s = BeautifulSoup(govde, "html.parser")
    out = []
    for panel in s.select("div[role=tabpanel]"):
        il_ad = _il_bul(panel)
        for kart in panel.select("div.card"):
            ad_et = kart.select_one("p.text-black")
            ad = _sade(ad_et.get_text(" ", strip=True)) if ad_et else ""
            if not ad:
                continue
            ilce_et = kart.select_one("p.c-ff")
            adres_et = kart.select_one("p.c-7a")
            tel_et = kart.select_one("a[href^='tel:']")
            tel = ""
            if tel_et:
                m = re.search(r"tel:\s*([0-9+ ()]+)", tel_et.get("href", ""))
                tel = _sade(m.group(1)) if m else ""
            out.append({
                "bayi_adi": ad,
                "il": il_ad,
                "ilce": _sade(ilce_et.get_text(" ", strip=True)) if ilce_et else "",
                "adres": _sade(adres_et.get_text(" ", strip=True)) if adres_et else "",
                "telefon": tel,
                "email": "",
                "website": "",
                "rol": "servis" if rol == "servis" else "satis",
            })
    return out
