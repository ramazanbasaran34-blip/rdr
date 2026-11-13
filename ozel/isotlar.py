"""İsotlar Motor — Peugeot, Horwin ve Lambretta'nın ortak bayi ağı.

Üç marka aynı distribütöre bağlı ama HER MARKANIN AĞI AYRI adreste:

    /bayiler/peugeot-motosiklet/
    /bayiler/horwin/
    /bayiler/lambretta/

İl seçici var ama seçeneklerin değeri doğrudan URL ve içinde
"Tüm İller" seçeneği bulunuyor → marka başına TEK istek yeterli,
81 il gezmeye gerek yok.

Rol, listedeki `<li>` sınıfından okunuyor:
    li.Bayi        → yalnız satış
    li.Servis      → yalnız servis
    li.BayiServis  → satış + servis

Sayfa windows-1254 ile kodlanmış; gövde o kodlamayla çözülmeli
(yoksa "Ä°stanbul" gibi bozuk metin çıkıyor).
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

MARKA_URL = {
    "Peugeot":   "https://www.isotlarmotor.com/bayiler/peugeot-motosiklet/",
    "Horwin":    "https://www.isotlarmotor.com/bayiler/horwin-motosiklet/",
    "Lambretta": "https://www.isotlarmotor.com/bayiler/lambretta-motosiklet/",
}
KAYNAKLAR = MARKA_URL
TEST = {
    ("Peugeot", "hepsi"):   "isotlar-peugeot.html",
    ("Horwin", "hepsi"):    "isotlar-horwin.html",
    ("Lambretta", "hepsi"): "isotlar-lambretta.html",
}

# Sayfa UTF-8 servis ediliyor ama metin ÇİFT KODLANMIŞ: kaynak zaten
# bozulmuş hâlde ("MOTOSİKLET"). latin1'e geri sarıp tekrar UTF-8 okumak
# düzeltiyor. Bu yüzden ayrı bir KODLAMA değil, düzeltme fonksiyonu var.
KODLAMA = "utf-8"


def kodlama_duzelt(t: str) -> str:
    """UTF-8 → latin1 → UTF-8 çift kodlamasını geri alır."""
    if "Ä" not in t and "Å" not in t and "Ã" not in t:
        return t
    try:
        return t.encode("latin1", "ignore").decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        return t

SINIF_ROL = {
    "bayiservis": "satis_servis",
    "servisbayi": "satis_servis",
    "bayi": "satis",
    "servis": "servis",
}

TEL = re.compile(r"(?:0|\+90)[\s\(\)\-/\.]*\d{3}[\s\(\)\-/\.]*\d{3}[\s\-/\.]*\d{2}[\s\-/\.]*\d{2}")


def _sade(t: str) -> str:
    return re.sub(r"\s+", " ", t or "").strip()


def _rol(li) -> str:
    sinif = "".join((li.get("class") or [])).casefold()
    for anahtar, rol in SINIF_ROL.items():
        if sinif == anahtar:
            return rol
    # Sınıf tanınmazsa listedeki rozet yazılarına bak
    metin = li.get_text(" ").casefold()
    satici = "satıcı" in metin or "satici" in metin
    servis = "servis" in metin
    if satici and servis:
        return "satis_servis"
    return "servis" if servis else "satis"


def coz(rol: str, govde: str, url: str) -> list[dict]:
    soup = BeautifulSoup(kodlama_duzelt(govde), "html.parser")
    out = []
    for li in soup.select("li.Bayi, li.Servis, li.BayiServis"):
        ad = _sade((li.find(id="Baslik") or li.find(class_="Baslik")
                    or li.find(["h3", "h4"]) or li).get_text(" "))
        if not ad:
            continue
        # Başlık düğümü yoksa tüm metin gelir; ilk satırı al
        ad = ad.split("  ")[0].strip()

        adres, tel = "", ""
        for sp in li.find_all("span"):
            t = _sade(sp.get_text(" "))
            if not t:
                continue
            m = TEL.search(t)
            if m and not tel:
                tel = m.group(0)
                continue
            if sp.find("a", href=True) and "maps" in sp.find("a")["href"]:
                adres = t
            elif not adres and len(t) > len(ad) and not m:
                adres = t

        out.append({
            "bayi_adi": ad,
            "il": "",
            "ilce": "",
            "adres": adres,
            "telefon": tel,
            "email": "",
            "website": "",
            "rol": _rol(li),
        })
    return out
