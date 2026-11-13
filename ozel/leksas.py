"""Leksas — WordPress REST ucundaki `locations` dizisi.

Sayfada il/ilçe/hizmet seçicileri var ama liste sunucudan tam geliyor.
Düz sayfa HTML'inde Elementor sarmalayıcısı yüzünden görünmüyor;
WordPress REST ucu içeriği işlenmiş hâlde veriyor:

    /wp-json/wp/v2/pages/72 → content.rendered → const locations = [...]

Her kayıtta il, ilçe, telefon, adres ve `cats` (bayi/servis) hazır.
Rol ayrımı için sayfayı iki kez çekmeye gerek yok.
"""

from __future__ import annotations

import json
import re

from .tr import anahtar

MARKA = "Leksas"

REST = "https://www.leksas.com.tr/wp-json/wp/v2/pages/72"
KAYNAKLAR = {"hepsi": REST}
TEST = {("Leksas", "hepsi"): "leksas-rest.json"}

DIZI = re.compile(r"const\s+locations\s*=\s*(\[.*?\])\s*;", re.S)


def _rol(kayit: dict) -> str:
    """cats: ['bayi'] / ['servis'] / ikisi birden."""
    etiketler = {anahtar(x) for x in (kayit.get("cats") or [])}
    etiketler |= {anahtar(kayit.get("cat_label", ""))}
    satis = any("bayi" in e or "satis" in e or "satici" in e for e in etiketler)
    servis = any("servis" in e for e in etiketler)
    if satis and servis:
        return "satis_servis"
    if servis:
        return "servis"
    return "satis"


def coz(rol: str, govde: str, url: str) -> list[dict]:
    d = json.loads(govde) if isinstance(govde, str) else govde
    icerik = (d.get("content") or {}).get("rendered", "") if isinstance(d, dict) else ""
    if not icerik:
        icerik = govde if isinstance(govde, str) else ""

    m = DIZI.search(icerik)
    if not m:
        return []
    try:
        kayitlar = json.loads(m.group(1))
    except json.JSONDecodeError:
        return []

    out = []
    for x in kayitlar:
        ad = re.sub(r"\s+", " ", (x.get("title") or "")).strip()
        # WordPress başlıkta HTML varlıkları bırakıyor (&#8211; gibi)
        ad = ad.replace("&#8211;", "-").replace("&amp;", "&").strip(" -")
        if not ad:
            continue
        ilce = (x.get("ilce") or "").strip()
        if anahtar(ilce) == "merkez":
            ilce = ""          # "MERKEZ" ilçe adı değil
        out.append({
            "bayi_adi": ad,
            "il": (x.get("il") or "").strip(),
            "ilce": ilce,
            "adres": (x.get("adres") or "").strip(),
            "telefon": (x.get("tel") or "").strip(),
            "email": "",
            "website": "",
            "rol": _rol(x),
        })
    return out
