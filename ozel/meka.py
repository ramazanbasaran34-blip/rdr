"""Meka Motor — tek XML dosyası.

Harita `resman/uploads/maps.xml` dosyasını okuyor; ülkenin tamamı orada.
Sayfayı gezmeye, il seçmeye gerek yok.

    <MAGAZA><IL>..</IL><MAGAZATITLE>İLÇE/İL Firma</MAGAZATITLE>
      <MAGAZAKONUM>adres</MAGAZAKONUM><MAGAZATEL>..</MAGAZATEL>
      <ACIKLAMA>BAYİ | SERVİS</ACIKLAMA></MAGAZA>

Önceki tarif yalnızca bayi getiriyordu çünkü ACIKLAMA alanı hiç
okunmuyordu; servis kayıtları da bu dosyada duruyor.
Dosya çift kodlanmış (UTF-8 → latin1 → UTF-8), geri sarmak gerekiyor.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

MARKA = "Meka Motor"
UC = "https://www.mekamotor.com.tr/resman/uploads/maps.xml"
KAYNAKLAR = {"hepsi": UC}
TEST = {("Meka Motor", "hepsi"): "meka-maps.xml"}

ROL_ANAHTAR = [("bayi", "satis"), ("satis", "satis"), ("satici", "satis"),
               ("servis", "servis")]


def _sade(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "")).strip()


def kodlama_duzelt(t: str) -> str:
    if not any(x in t for x in ("Ä", "Å", "Ã")):
        return t
    try:
        return t.encode("latin1", "ignore").decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        return t


def _anahtar(t: str) -> str:
    t = _sade(t)
    for a, b in (("İ", "I"), ("ı", "i"), ("Ç", "C"), ("ç", "c"), ("Ğ", "G"),
                 ("ğ", "g"), ("Ö", "O"), ("ö", "o"), ("Ş", "S"), ("ş", "s"),
                 ("Ü", "U"), ("ü", "u")):
        t = t.replace(a, b)
    return t.lower()


def coz(rol: str, govde: str, url: str) -> list[dict]:
    metin = kodlama_duzelt(govde)
    try:
        kok = ET.fromstring(metin)
    except ET.ParseError:
        # Bozuk karakter varsa kaba temizlik
        metin = re.sub(r"&(?!amp;|lt;|gt;|quot;|apos;|#)", "&amp;", metin)
        kok = ET.fromstring(metin)

    out = []
    for m in kok.iter("MAGAZA"):
        def al(etiket: str) -> str:
            e = m.find(etiket)
            return _sade(e.text if e is not None else "")

        baslik = al("MAGAZATITLE")
        if not baslik:
            continue

        # "SİNANPAŞA/AFYONKARAHİSAR Akdeniz Ticaret" → ilçe + ad
        ilce, ad = "", baslik
        m2 = re.match(r"^\s*([^/]+)/([^\s]+)\s+(.*)$", baslik)
        if m2:
            ilce, ad = _sade(m2.group(1)), _sade(m2.group(3))

        aciklama = _anahtar(al("ACIKLAMA"))
        satis = any(a in aciklama for a, r in ROL_ANAHTAR if r == "satis")
        servis = "servis" in aciklama
        rol_ = ("satis_servis" if (satis and servis)
                else "servis" if servis else "satis")

        out.append({
            "bayi_adi": ad or baslik,
            "il": al("IL"),
            "ilce": ilce,
            "adres": al("MAGAZAKONUM"),
            "telefon": al("MAGAZATEL"),
            "email": "",
            "website": "",
            "rol": rol_,
        })
    return out
