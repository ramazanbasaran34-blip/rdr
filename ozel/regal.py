"""Regal Raptor — ASP.NET WebForms, il seçimi postback ile.

Altai ile BİREBİR aynı altyapı (aynı ajans yapmış olmalı): aynı
`body_drp_il` seçicisi, aynı postback akışı. Bu yüzden Altai modülünün
mantığı olduğu gibi geçerli.

Sayfa il seçince `__doPostBack('ctl00$body$drp_il','')` çağırıyor; bu
formu POST ile geri gönderiyor. Zelsun'un aksine il URL'e YANSIMIYOR,
yani düz GET işe yaramıyor: sunucuya ViewState ile birlikte POST atmak
şart.

Akış:
  1. Sayfayı GET et, gizli alanları oku
     (__VIEWSTATE, __VIEWSTATEGENERATOR, __EVENTVALIDATION).
  2. Her il için aynı gizli alanlarla POST at, dönen HTML'i ayrıştır.
  3. Sunucu her yanıtta YENİ ViewState üretiyor; bir sonraki istekte
     onu kullanmak gerekiyor, yoksa "geçersiz durum" hatası alınır.

İl listesi sayfadaki <select name="ctl00$body$drp_il"> içinde;
değerler plaka kodu değil sitenin kendi numaraları (Düzce=81, Bartın=74).
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

MARKA = "Regal Raptor"

KAYNAKLAR = {
    "satis":  "https://regalraptor.com.tr/tr/bayiler",
    "servis": "https://regalraptor.com.tr/tr/servisler",
}
TEST = {
    ("Regal Raptor", "satis"):  "regal-satis.html",
    ("Regal Raptor", "servis"): "regal-servis.html",
}

IL_SECICI = "ctl00$body$drp_il"
GIZLI = ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION",
         "__EVENTTARGET", "__EVENTARGUMENT", "__LASTFOCUS")

TEL = re.compile(r"(?:\+90|0)[\s\(\)\-/\.]*\d{3}[\s\(\)\-/\.]*\d{3}[\s\-/\.]*\d{2}[\s\-/\.]*\d{2}")


def gizli_alanlar(govde: str) -> dict[str, str]:
    """Formun gizli alanlarını okur; POST'ta aynen geri gönderilecek."""
    soup = BeautifulSoup(govde, "html.parser")
    out = {}
    for gir in soup.select("input[type=hidden]"):
        ad = gir.get("name")
        if ad:
            out[ad] = gir.get("value", "")
    return {k: v for k, v in out.items() if k in GIZLI or k.startswith("__")}


def il_secenekleri(govde: str) -> list[tuple[str, str]]:
    """(deger, il adı) — '0' (İl Seçin) atlanır."""
    soup = BeautifulSoup(govde, "html.parser")
    sec = soup.find("select", attrs={"name": IL_SECICI})
    if not sec:
        return []
    out = []
    for o in sec.find_all("option"):
        deger = (o.get("value") or "").strip()
        ad = re.sub(r"\s+", " ", o.get_text(" ")).strip()
        if deger and deger != "0" and ad:
            out.append((deger, ad))
    return out


def post_govdesi(govde: str, il_degeri: str) -> dict[str, str]:
    """İl seçimi için gönderilecek form gövdesi."""
    d = gizli_alanlar(govde)
    d["__EVENTTARGET"] = IL_SECICI
    d["__EVENTARGUMENT"] = ""
    d[IL_SECICI] = il_degeri
    d["ctl00$body$drp_ilce"] = "0"      # tüm ilçeler
    return d


def _m(el) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ")).strip() if el else ""


def coz(rol: str, govde: str, url: str, il: str | None = None) -> list[dict]:
    """Postback yanıtındaki bayi kartlarını çıkarır."""
    soup = BeautifulSoup(govde, "html.parser")
    out: list[dict] = []
    gorulen: set[tuple[str, str]] = set()

    # Kayıtlar telefon bağlantısı ya da telefon metni taşıyan kutularda.
    adaylar = soup.select(".bayi, .bayi-item, .dealer, .card, li, .row > div")
    for kutu in adaylar:
        metin = _m(kutu)
        if len(metin) < 25 or len(metin) > 600:
            continue
        t = TEL.search(metin)
        if not t:
            continue

        # Sayfa alt bilgisi de telefon taşıyor; kayıt sanılmasın.
        dusuk = metin.casefold()
        if any(k in dusuk for k in ("dil ayarları", "bayi girişi", "@altai.com.tr",
                                    "çerez", "gizlilik", "tüm hakları")):
            continue

        bas = kutu.find(["h1", "h2", "h3", "h4", "h5", "h6", "strong", "b"])
        ad = _m(bas)
        if not ad:
            # Başlık yoksa telefondan önceki ilk satırı ad say
            ad = metin[:t.start()].strip(" -–|·,")
            ad = ad.split("  ")[0][:80].strip()
        if not ad or len(ad) < 3:
            continue

        tel = t.group(0)
        adres = metin.replace(ad, "", 1).replace(tel, " ")
        # "Satış Mağazası" / "Servis" gibi kart etiketi adresin başında
        adres = re.sub(r"^\s*(Satış Mağazası|Servis Noktası|Servis|Bayi)\s*",
                       "", adres, flags=re.I)
        adres = re.sub(r"\s+", " ", adres).strip(" -–|·,")

        anahtar = (ad.casefold(), tel)
        if anahtar in gorulen:
            continue
        gorulen.add(anahtar)

        out.append({
            "bayi_adi": ad,
            "il": il or "",
            "ilce": "",
            "adres": adres[:220],
            "telefon": tel,
            "email": "",
            "website": "",
            "rol": rol,
        })
    return out
