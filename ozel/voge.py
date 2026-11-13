"""Voge — vogeturkiye.com.tr/yetkili-satici/

NEDEN ÖZEL MODÜL
Site tek sayfada, il gruplarına ayrılmış kartlarla çalışıyor. Rol
kartın SINIFINDA, ilçe/telefon/adres ise tek bir metin bloğunda
etiketli duruyor:

    div.dm-il-group
      div.dm-il-title              → "ADANA (2)"   ← sayaç parantezde
      div.dm-dealer-card
        div.dm-dealer-name         → firma adı
        span.dm-tip-bayi_servis    → satış + servis
        span.dm-tip-servis         → yalnız servis
        span.dm-tip-bayi           → yalnız satış
        div.dm-dealer-meta         → "İlçe: X Tel: Y Adres: Z"

Genel ayrıştırıcı kartların çoğunu alıyordu ama 10 kaydı kaçırıyor ve
ilçe/telefon/adres'i etiketleriyle birlikte tek alana yığıyordu.

KAYIT SAYISI DÜŞÜŞÜ GERÇEK
Depoda 276 kayıt vardı, site şimdi 163 veriyor. Bu bir ayrıştırma
kaybı değil: site yenilenip liste sadeleşmiş. Eski kayıtlar düşüş
korumasıyla donduruluyordu.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

MARKA = "Voge"

KAYNAKLAR = {"satis_servis": "https://www.vogeturkiye.com.tr/yetkili-satici/"}
TEST = {("Voge", "satis_servis"): "m-voge.html"}

# "İlçe: X Tel: Y Adres: Z" — etiketleri ayırıp değerleri alıyoruz
_ETIKET = re.compile(
    r"(İlçe|Ilce|Tel|Telefon|Adres|Adresi)\s*:\s*", re.I)
# İl başlığındaki "(2)" sayacı ad değil
_SAYAC = re.compile(r"\s*\(\s*\d+\s*\)\s*$")


def _sade(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "")).strip()


def _rol(kart) -> str:
    tip = kart.select_one("[class*=dm-tip]")
    s = " ".join(tip.get("class")) if tip else ""
    if "bayi_servis" in s:
        return "satis_servis"
    if "dm-tip-servis" in s:
        return "servis"
    if "dm-tip-bayi" in s:
        return "satis"
    return "satis_servis"          # etiketsiz kart: sayfanın varsayılanı


# Türkçe "İ".casefold() birleşik noktalı harfe dönüşüyor ve "ilçe" ile
# karşılaştırma tutmuyordu; etiketleri bu tabloyla sadeleştiriyoruz.
_TR = str.maketrans({"İ": "i", "I": "i", "ı": "i", "Ç": "c", "ç": "c",
                     "Ğ": "g", "ğ": "g", "Ö": "o", "ö": "o",
                     "Ş": "s", "ş": "s", "Ü": "u", "ü": "u"})


def _etiket_sade(t: str) -> str:
    return _sade(t).translate(_TR).lower().strip(": ")


def _meta(kutu) -> dict:
    """Meta bloğunu YAPIDAN okur: <div><strong>İlçe:</strong> değer</div>.

    Metni etiketlere göre bölmek kırılgandı; ayrıca telefon <a href='tel:'>
    içinde geldiği için yapıdan okumak daha güvenli.
    """
    d: dict = {}
    for satir in kutu.find_all("div"):
        et = satir.find(["strong", "b"])
        if not et:
            continue
        anahtar = _etiket_sade(et.get_text(" ", strip=True))
        deger = _sade(satir.get_text(" ", strip=True)[len(
            _sade(et.get_text(" ", strip=True))):])
        if not deger:
            continue
        if anahtar.startswith("ilce"):
            d["ilce"] = deger
        elif anahtar.startswith("tel"):
            d["telefon"] = deger
        elif anahtar.startswith("adres"):
            d["adres"] = deger
    return d


def coz(rol: str, govde: str, url: str, il: str | None = None) -> list[dict]:
    s = BeautifulSoup(govde, "html.parser")
    out = []
    for kart in s.select("div.dm-dealer-card"):
        ad_et = kart.select_one(".dm-dealer-name")
        ad = _sade(ad_et.get_text(" ", strip=True)) if ad_et else ""
        if not ad:
            continue

        grup = kart.find_parent(class_="dm-il-group")
        bas = grup.select_one(".dm-il-title") if grup else None
        il_ad = _SAYAC.sub("", _sade(bas.get_text(" ", strip=True))) if bas else ""

        meta_et = kart.select_one(".dm-dealer-meta")
        alan = _meta(meta_et) if meta_et else {}

        out.append({
            "bayi_adi": ad,
            "il": il_ad,
            "ilce": alan.get("ilce", ""),
            "adres": alan.get("adres", ""),
            "telefon": alan.get("telefon", ""),
            "email": "",
            "website": "",
            "rol": _rol(kart),
        })
    return out
