"""BMW Motorrad — kaynak Borusan Otomotiv (distribütör).

NEDEN BMW'NİN KENDİ SİTESİ KULLANILMIYOR
bmw-motorrad.com.tr/tr/ssl/yetkili-satici-ve-servisler.html BOŞ BİR
KABUK: HTML'de sadece bir spinner var, içerik iframe'e başka kaynaktan
yükleniyor. GitHub Actions'tan istek 180 saniyede bile yanıtsız kaldı.
Engelleme değil, sayfanın yapısı böyle.

GERÇEK KAYNAK
BMW Motorrad'ın Türkiye distribütörü Borusan Otomotiv. Yetkili satıcı
ve servis listesi kendi sitesinde, il bazlı DÜZ GET ile:

    /yetkili-satici-ve-servisler/arama?city=<il>

Sayfada `subeListe([...])` diye geçerli bir JSON dizisi var ve her
kayıtta hangi markaların satış/servisinin verildiği yazıyor:

    {"Sehir":"İstanbul","BayiAdi":"Borusan Oto Ataşehir",
     "Adres":"...","Tel":"...","Email":"...",
     "Satis":"BMW,BMW i,MINI,BMW Motorrad","Servis":"..."}

Borusan aynı zamanda BMW, MINI, Land Rover, Jaguar da satıyor; bu
yüzden yalnızca "BMW Motorrad" geçen kayıtlar alınıyor ve rol o
kaydın Satis/Servis alanlarından çıkarılıyor.

İl listesi harita sayfasındaki bağlantılardan okunuyor (23 il).
"""

from __future__ import annotations

import json
import re

from .tr import anahtar

MARKA = "BMW"

HARITA = "https://www.borusanotomotiv.com/yetkili-satici-ve-servisler/harita"
TABAN = "https://www.borusanotomotiv.com/yetkili-satici-ve-servisler/arama?city={il}"

KAYNAKLAR = {"hepsi": HARITA}
TEST = {("BMW", "hepsi"): "borusan-istanbul.html"}
TEST_IL = "İstanbul"

DIZI = re.compile(r"subeListe\(\s*(\[.*?\])\s*\)", re.S)

# Harita sayfasındaki il bağlantıları JS ile üretiliyor, HTML'de yok.
# Borusan'ın hizmet verdiği 23 il sabit; site büyürse buraya eklenir.
ILLER = ["Adana", "Ankara", "Antalya", "Bursa", "Denizli", "Diyarbakir",
         "Elazig", "Erzurum", "eskisehir", "Gaziantep", "istanbul", "izmir",
         "Kayseri", "Kocaeli", "Konya", "Manisa", "Mugla", "Sakarya",
         "Samsun", "sanliurfa", "tekirdag", "Trabzon", "Van"]

# Bu markayı arıyoruz; "BMW" tek başına otomobil demek, karıştırmayalım.
HEDEF = "bmw motorrad"


def il_sluglari(govde: str = "") -> list[tuple[str, str]]:
    """[(tam adres, il adı), ...] — koşucu tam adres bekliyor."""
    return [(TABAN.format(il=x), x.title()) for x in ILLER]


def il_url(rol: str, slug: str) -> str:
    return TABAN.format(il=slug)


def _var_mi(alan: str) -> bool:
    return HEDEF in anahtar(alan or "")


def coz(rol: str, govde: str, url: str, il: str | None = None) -> list[dict]:
    m = DIZI.search(govde)
    if not m:
        return []
    try:
        kayitlar = json.loads(m.group(1))
    except json.JSONDecodeError:
        return []

    out: list[dict] = []
    gorulen: set[tuple[str, str]] = set()

    for x in kayitlar:
        satis = _var_mi(x.get("Satis"))
        servis = _var_mi(x.get("Servis"))
        if not (satis or servis):
            continue          # bu nokta BMW Motorrad vermiyor

        ad = re.sub(r"\s+", " ", (x.get("BayiAdi") or "")).strip()
        if not ad:
            continue

        sehir = re.sub(r"\s+", " ", (x.get("Sehir") or "")).strip() or (il or "")
        anahtar_kayit = (anahtar(ad), anahtar(sehir))
        if anahtar_kayit in gorulen:
            continue
        gorulen.add(anahtar_kayit)

        out.append({
            "bayi_adi": ad,
            "il": sehir,
            "ilce": "",
            "adres": re.sub(r"\s+", " ", (x.get("Adres") or "")).strip(),
            "telefon": (x.get("Tel") or "").strip(),
            "email": (x.get("Email") or "").strip(),
            "website": (x.get("WebAdresi") or "").strip(),
            "rol": ("satis_servis" if (satis and servis)
                    else ("satis" if satis else "servis")),
        })
    return out
