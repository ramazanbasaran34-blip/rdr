"""Zelsun — il il ASP.NET sayfası, düz tablo.

Sayfa ASP.NET WebForms; il seçimi URL'e yansıyor, o yüzden POST/ViewState
gerekmiyor, düz GET yeter:

    Bayilerimiz.aspx?sehir=İSTANBUL&ilce=İlçe Seçiniz

Liste 4 sütunlu bir tabloda: ad | adres | ilçe | telefon.
İl bilgisi tabloda YOK, URL'den geliyor.
"""

from __future__ import annotations

import re
from urllib.parse import quote

MARKA = "Zelsun"

TABAN = {
    "satis":  "https://www.zelsunmotor.com/Bayilerimiz.aspx",
    "servis": "https://www.zelsunmotor.com/Servislerimiz.aspx",
}
KAYNAKLAR = TABAN
TEST = {
    ("Zelsun", "satis"):  "zelsun-satis34.html",
    ("Zelsun", "servis"): "zelsun-srv34.html",
}

# Test dosyaları İstanbul sayfasından alındı
TEST_IL = "İSTANBUL"

BOS_ILCE = "İlçe Seçiniz"


def il_url(rol: str, il: str) -> str:
    return (f"{TABAN[rol]}?sehir={quote(il)}&ilce={quote(BOS_ILCE)}")


def _hucreler(satir: str) -> list[str]:
    return [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c)).strip()
            for c in re.findall(r"<td[^>]*>(.*?)</td>", satir, re.S)]


def coz(rol: str, govde: str, url: str, il: str | None = None) -> list[dict]:
    if il is None:
        m = re.search(r"[?&]sehir=([^&]+)", url)
        il = m.group(1) if m else TEST_IL
        from urllib.parse import unquote
        il = unquote(il)

    out = []
    for tablo in re.findall(r"<table[^>]*>(.*?)</table>", govde, re.S):
        for satir in re.findall(r"<tr[^>]*>(.*?)</tr>", tablo, re.S):
            h = _hucreler(satir)
            # ad | adres | ilçe | telefon — dördünden azı varsa gezinme tablosu
            if len(h) < 4 or not h[0]:
                continue
            tel = h[3]
            if not re.search(r"\d{7,}", tel.replace(" ", "")):
                continue
            out.append({
                "bayi_adi": h[0],
                "il": il,
                "ilce": h[2],
                "adres": h[1],
                "telefon": tel,
                "email": "",
                "website": "",
                "rol": rol,
            })
    return out
