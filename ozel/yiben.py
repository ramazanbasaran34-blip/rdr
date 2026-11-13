"""Yiben — sayfaya gömülü `rawDealers` JSON dizisi.

Sayfa il seçtiriyor gibi görünse de liste sunucudan tam geliyor;
JS onu sadece süzüyor. Kaynakta geçerli JSON olarak duruyor:

    const rawDealers = [{"company":"SELÇUK MOTOR","city":"KONYA",
                         "district":"SELÇUKLU","address":"...",
                         "phone":"05415568229","email":"...",
                         "status":"active"}, ...]

Satış ve servis ayrı sayfalarda, rol kaynaktan geliyor.
`status` alanı "active" değilse kayıt alınmıyor.
"""

from __future__ import annotations

import json
import re

from bayiradar.normalize import ILLER, fold

MARKA = "Yiben"

KAYNAKLAR = {
    "satis":  "https://yibenmotosiklet.com.tr/tr/sayfa/bayi-agi",
    "servis": "https://yibenmotosiklet.com.tr/tr/sayfa/servis-agi",
}
TEST = {
    ("Yiben", "satis"):  "yiben-satis.html",
    ("Yiben", "servis"): "yiben-servis.html",
}

# Satış sayfası rawDealers, servis sayfası rawServices kullanıyor.
DIZI = re.compile(r"raw(?:Dealers|Services)\s*=\s*(\[.*?\])\s*;", re.S)

# Adres sonu "... ORTAHİSAR/TRABZON" ya da "... ADAPAZARI / SAKARYA"
SON_KONUM = re.compile(r"([A-ZÇĞİÖŞÜa-zçğıöşü\.]+)\s*/\s*([A-ZÇĞİÖŞÜa-zçğıöşü\.]+)\s*$")

# city alanı güvenilmez: bazı kayıtlarda ilçe adı girilmiş
# ("Karatay", "Akdeniz", "Merkez"). Gerçek il listesiyle doğruluyoruz.
_IL_ANAHTAR = {fold(x): x for x in ILLER}


def _gecerli_il(ad: str) -> str:
    return _IL_ANAHTAR.get(fold(ad or ""), "")


def coz(rol: str, govde: str, url: str) -> list[dict]:
    m = DIZI.search(govde)
    if not m:
        return []
    try:
        kayitlar = json.loads(m.group(1))
    except json.JSONDecodeError:
        return []

    out = []
    for x in kayitlar:
        if (x.get("status") or "active") != "active":
            continue
        # Firma adı yoksa kişi adına düş
        ad = (x.get("company") or "").strip()
        if not ad:
            ad = " ".join(p for p in ((x.get("name") or "").strip(),
                                      (x.get("surname") or "").strip()) if p)
        ad = re.sub(r"\s+", " ", ad).strip()
        if not ad:
            continue

        adres = re.sub(r"\s+", " ", (x.get("address") or "")).strip()
        il = (x.get("city") or "").strip()
        ilce = (x.get("district") or "").strip()

        # 58 kayıtta city boş; adresin sonunda "İlçe/İl" yazıyor.
        # Ayrıca bazı kayıtlarda city alanına ilçe adı girilmiş
        # ("Karatay", "Merkez"), bu yüzden adres sonu daha güvenilir.
        m2 = SON_KONUM.search(adres)
        aday_ilce = aday_il = ""
        if m2:
            aday_ilce, aday_il = m2.group(1).strip(), m2.group(2).strip()

        # city gerçek bir il değilse (ilçe yazılmış ya da boşsa)
        # adresin sonundaki ili kullan; city'yi ilçeye kaydır.
        if not _gecerli_il(il):
            if il and not ilce:
                ilce = il
            il = _gecerli_il(aday_il) or ""
            if not ilce:
                ilce = aday_ilce
        else:
            il = _gecerli_il(il)
            if not ilce:
                ilce = aday_ilce
        if ilce.casefold() in ("merkez", "none"):
            ilce = ""

        out.append({
            "bayi_adi": ad,
            "il": il,
            "ilce": ilce,
            "adres": adres,
            "telefon": (x.get("phone") or "").strip(),
            "email": (x.get("email") or "").strip(),
            "website": "",
            "rol": rol,
        })
    return out
