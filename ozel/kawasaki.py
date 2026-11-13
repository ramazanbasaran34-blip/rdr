"""Kawasaki — tek sayfada tüm ağ, il bilgisi kartın id'sinde.

NEDEN YENİDEN YAZILDI
Eski tarama 85 kaydın 79'una yanlış il atamıştı (%92). İstanbul'daki
bütün servisler Ankara görünüyordu; ARN Plaza Çekmeköy'de olmasına
rağmen Ankara'ya yazılmıştı. İl bilgisi hiç okunmuyor, sayfadaki
sıraya göre tahmin ediliyordu.

YAPI
    <div class="col-lg-4" id="istanbul" data-type="Motosiklet">   ← İL
      <h3>ARN PLAZA</h3>                                          ← FİRMA
      <div><i class="fa fa-map-marker"></i>Soğukpınar Mah. ...
           Çekmeköy / İstanbul</div>                              ← ADRES
      <a href="tel:0530 410 42 71">...</a>                        ← TELEFON
      <p>istanbul - Motosiklet Yetkili Servisi</p>

İl kartın id'sinde ("istanbul", "ankara"). Yedek olarak adresin
sonundaki "... / İstanbul" da okunuyor; ikisi çelişirse ADRES kazanıyor,
çünkü hatanın kaynağı buydu.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from bayiradar.normalize import ILLER, fold

MARKA = "Kawasaki"

KAYNAKLAR = {
    "satis":  "https://www.kawasaki.com.tr/Home/YetkiliSatici",
    "servis": "https://www.kawasaki.com.tr/Home/YetkiliServis",
}
TEST = {
    ("Kawasaki", "satis"):  "kawasaki-satis.html",
    ("Kawasaki", "servis"): "kawasaki-servis.html",
}

_IL = {fold(x): x for x in ILLER}


def _m(el) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ")).strip() if el else ""


def _il_coz(deger: str) -> str:
    return _IL.get(fold(deger or ""), "")


def coz(rol: str, govde: str, url: str) -> list[dict]:
    soup = BeautifulSoup(govde, "html.parser")
    out: list[dict] = []
    gorulen: set[tuple[str, str]] = set()

    # Her kaydın çapası <h3> başlık. Kartın kendisi başlığın en yakın
    # kutusu; il bilgisi ise id taşıyan üst kapsayıcıda ("istanbul").
    for bas in soup.find_all(["h3", "h4"]):
        ad = _m(bas)
        if not ad:
            continue

        kutu = bas.find_parent("div")
        if kutu is None:
            continue

        # Adres: harita simgesini taşıyan blokların EN KISASI
        # (dıştaki bloklar başlığı da içine alıyor)
        adaylar = []
        for d in kutu.find_all("div"):
            # NOT: class_ ile lambda kullanmak bu bs4 sürümünde eşleşmiyor;
            # sınıf adını doğrudan vermek gerekiyor.
            if d.find("i", class_="fa-map-marker"):
                t = _m(d)
                if t:
                    adaylar.append(t)
        if not adaylar:
            continue
        adres = min(adaylar, key=len)
        # Başlık adres metnine karışmışsa temizle
        if adres.startswith(ad):
            adres = adres[len(ad):].strip(" -–,")

        # İl: önce adresin sonu, sonra id taşıyan üst kapsayıcı
        son = re.split(r"[/,]", adres)[-1].strip()
        il = _il_coz(son)
        if not il:
            kapsayici = bas.find_parent(id=True)
            il = _il_coz(kapsayici.get("id", "")) if kapsayici else ""
        if not il:
            continue

        a = kutu.select_one("a[href^='tel:']")
        tel = a.get("href", "")[4:].strip() if a else ""

        ilce = ""
        m = re.search(r"([^/,]{2,40})\s*/\s*[^/,]{2,30}\s*$", adres)
        if m:
            kel = m.group(1).strip().split()
            for n in (1, 2):
                aday = " ".join(kel[-n:]).strip()
                if aday and not re.search(r"\d|no:|mah\.|cad\.|sok|blv|sit\.",
                                          aday, re.I):
                    ilce = aday
                    break

        anahtar = (fold(ad), fold(adres))
        if anahtar in gorulen:
            continue
        gorulen.add(anahtar)

        out.append({
            "bayi_adi": ad,
            "il": il,
            "ilce": ilce,
            "adres": adres,
            "telefon": tel,
            "email": "",
            "website": "",
            "rol": rol,
        })

    return out
