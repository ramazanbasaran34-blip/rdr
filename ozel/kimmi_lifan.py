"""Kimmi ve Lifan — aynı altyapı, il bazlı düz URL.

Sayfada "İl Seçiniz" açılır kutusu var ama arkasında ajax YOK; seçim
doğrudan adrese gidiyor:

    /bayiler/{il-slug}     /servisler/{il-slug}

İl listesi ana sayfadaki <select id="cities"> içinde duruyor, oradan
okunuyor. Kayıtlar Elementor kutuları hâlinde: firma adı bir başlık,
altında "Adres" başlığı + adres metni, telefon ise `tel:` bağlantısı.

Adres satırının sonu "İlçe/İl" biçiminde ("Altındağ/Ankara"), ilçe
oradan çıkıyor.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .tr import anahtar

TABAN = {
    "Kimmi": "https://www.kimmimotor.com",
    "Lifan": "https://www.lifanmotor.com.tr",
}

MARKA = "Kimmi"      # varsayılan; runner marka adını geçiyor

KAYNAKLAR = {
    "satis":  "{taban}/bayiler/{slug}",
    "servis": "{taban}/servisler/{slug}",
}
TEST = {
    ("Kimmi", "servis"): "kimmi-srv-ank.html",
    ("Kimmi", "satis"):  "kimmi-bayi-ank.html",
    ("Lifan", "servis"): "lifan-srv-ank.html",
}
TEST_IL = "Ankara"

# Kart içinde firma adı sayılmayacak başlıklar
BASLIK_DISI = {"adres", "telefon", "tel", "iletisim", "harita",
               "yol tarifi", "servisler", "bayiler", "il seciniz"}


def il_url(marka: str, rol: str, slug: str) -> str:
    return KAYNAKLAR[rol].format(taban=TABAN[marka], slug=slug)


def il_sluglari(govde: str) -> list[tuple[str, str]]:
    """Ana sayfadaki <select id="cities"> içinden (slug, ad) listesi."""
    soup = BeautifulSoup(govde, "html.parser")
    sec = soup.find("select", id="cities")
    if not sec:
        return []
    out = []
    for o in sec.find_all("option"):
        deger = (o.get("value") or "").strip()
        ad = re.sub(r"\s+", " ", o.get_text(" ")).strip()
        if deger and ad:
            out.append((deger, ad))
    return out


def _m(el) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ")).strip() if el else ""


def coz(rol: str, govde: str, url: str, il: str | None = None) -> list[dict]:
    soup = BeautifulSoup(govde, "html.parser")
    out: list[dict] = []
    gorulen: set[tuple[str, str]] = set()

    # Telefon bağlantısı her kaydın çapası; kaydın kutusu onun atası.
    for a in soup.select("a[href^='tel:']"):
        tel = a.get("href", "")[4:].strip()
        if not tel:
            continue

        kutu = a
        for _ in range(4):
            kutu = kutu.parent
            if kutu is None:
                break
            if kutu.find("p") and len(_m(kutu)) > 40:
                break
        if kutu is None:
            continue

        metin_p = [_m(p) for p in kutu.find_all("p")]
        adres = ""
        for t in metin_p:
            if t and not re.fullmatch(r"[\d\s\(\)\-\+/]{7,}", t) and len(t) > len(adres):
                adres = t

        # Sayfanın kendi iletişim/alt bilgi bloğu kayıt değil.
        if not adres:
            continue

        ad = ""
        for bas in kutu.select(".elementor-heading-title"):
            t = _m(bas)
            if not t or anahtar(t) in BASLIK_DISI:
                continue
            if re.fullmatch(r"[\d\s\(\)\-\+/]{7,}", t):
                continue          # telefon başlığı
            if "@" in t or re.match(r"(?i)^(https?://|www\.)", t):
                continue          # e-posta / site adresi firma adı değil
            if len(t) < 3:
                continue
            ad = t
            break
        if not ad:
            continue

        # Adres "... No:1 Pursaklar/Ankara" ile bitiyor.
        # İlçe = eğik çizgiden ÖNCEKİ SON KELİME(ler); tüm adresi
        # yutmaması için sondan en fazla iki kelime alınıyor.
        ilce = ""
        m = re.search(r"([^/,]{2,40})\s*/\s*([^/,]{2,30})\s*$", adres)
        if m:
            sol = m.group(1).strip()
            kelimeler = sol.split()
            for n in (1, 2):
                aday = " ".join(kelimeler[-n:])
                if aday and not re.search(r"\d|no:|mah\.|blv|cad|sok", aday, re.I):
                    ilce = aday
                    break

        # Aynı firmanın birden çok telefonu olabiliyor (sabit + cep);
        # tekrarı önlemek için anahtar ad+ilçe, telefon değil.
        anahtar_kayit = (anahtar(ad), anahtar(ilce))
        if anahtar_kayit in gorulen:
            continue
        gorulen.add(anahtar_kayit)

        out.append({
            "bayi_adi": ad,
            "il": il or "",
            "ilce": ilce,
            "adres": adres,
            "telefon": tel,
            "email": "",
            "website": "",
            "rol": rol,
        })
    return out
