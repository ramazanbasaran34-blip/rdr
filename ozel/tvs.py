"""TVS — turkiye.tvsmotor.com (Uğur Motorlu Araçlar A.Ş.)

NEDEN ÖZEL MODÜL
Bayi bulucu sayfası listeyi kendi içinde tutmuyor; ayrı bir uygulamaya
yönlendiriyor (location.tvsmotor.com) ve o da veriyi resmî API'den
çekiyor. Sayfayı ayrıştırmaya çalışmak boşuna; doğrudan API okunuyor.

    POST https://apim.tvsmotor.com/location-master/api/v1/dealer-search
    {"countryCode":"TR","dealerFilterType":"TWO_WHEELER_SALES"}

ÜÇ KATEGORİ VAR, ÜÇÜNCÜSÜ ALINMIYOR
    TWO_WHEELER_SALES    → satış      (sitede "Satış")
    TWO_WHEELER_SERVICE  → servis     (sitede "Servis")
    TWO_WHEELER_APS      → YEDEK PARÇA — listeye GİRMEZ

Yedek parça bayisi motosiklet satmıyor, servis de vermiyor. Falcon'da
aynı hatayı yaşadık: yedek parça noktaları satış sayılınca liste
gerçeğin katlarına çıkmıştı.

Aynı firma hem satış hem servis listesinde olabiliyor; dealerCode ile
eşleştirilip tek kayıtta "satis_servis" olarak birleştiriliyor.
"""

from __future__ import annotations

import json

MARKA = "TVS"

UC = "https://apim.tvsmotor.com/location-master/api/v1/dealer-search"

# Bu modül kendi isteğini atıyor (POST + JSON gövde), o yüzden KAYNAKLAR
# yalnızca kayıt amaçlı; asıl iş getir() içinde.
JSON_UC = True          # uç JSON; Accept başlığı istenir
KAYNAKLAR = {"satis_servis": UC}

KATEGORI = {
    "TWO_WHEELER_SALES": "satis",
    "TWO_WHEELER_SERVICE": "servis",
    # TWO_WHEELER_APS bilerek YOK: yedek parça bayisi sayılmaz
}


def _kayitlar(govde: str) -> list[dict]:
    try:
        d = json.loads(govde)
    except json.JSONDecodeError:
        return []
    veri = d.get("data") if isinstance(d, dict) else d
    if isinstance(veri, dict):
        for v in veri.values():
            if isinstance(v, list):
                veri = v
                break
    return veri if isinstance(veri, list) else []


def _telefon(kayit: dict) -> str:
    ilet = kayit.get("contacts") or {}
    for t in ilet.get("phoneNumbers") or []:
        v = (t.get("value") or "").strip()
        if v:
            return v
    return ""


def coz(rol: str, govde: str, url: str, il: str | None = None) -> list[dict]:
    """Tek bir kategorinin yanıtını kayda çevirir."""
    out = []
    for k in _kayitlar(govde):
        ad = (k.get("dealershipName") or "").strip()
        if not ad:
            continue
        yer = k.get("location") or {}
        out.append({
            "bayi_adi": ad,
            # API'de province = il, city = ilçe
            "il": (yer.get("province") or "").strip(),
            "ilce": (yer.get("city") or "").strip(),
            "adres": (yer.get("address") or "").strip(),
            "telefon": _telefon(k),
            "email": "",
            "website": "",
            "rol": rol,
            "_kod": (k.get("dealerCode") or "").strip(),
        })
    return out


def getir(oturum) -> list[dict]:
    """İki kategoriyi çekip aynı firmayı tek kayıtta birleştirir.

    ozel_tara bu fonksiyonu görürse kendi GET'i yerine bunu kullanır;
    uç POST + JSON gövde istediği için gerekli.
    """
    birlesik: dict = {}
    for tip, rol in KATEGORI.items():
        y = oturum.post(UC, json={"countryCode": "TR", "dealerFilterType": tip},
                        timeout=60)
        y.raise_for_status()
        for k in coz(rol, y.text, UC):
            anahtar = k.pop("_kod") or f"{k['bayi_adi']}|{k['telefon']}"
            var = birlesik.get(anahtar)
            if var is None:
                birlesik[anahtar] = k
            elif var["rol"] != k["rol"]:
                var["rol"] = "satis_servis"
    for k in birlesik.values():
        k.pop("_kod", None)
    return list(birlesik.values())
