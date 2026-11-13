"""Türkçe metin normalleştirme ve rol sözlüğü — bütün markalar için ortak.

İKİ TUZAK VAR, ikisi de sahada kayıp veriye yol açtı:

1) TÜRKÇE "İ" ve casefold()
   "BAYİ".casefold() → "bayi̇"  — sonda birleştirici bir nokta (U+0307)
   kalıyor ve "bayi" ile karşılaştırma TUTMUYOR. Motolux'te sekme
   başlıkları bu yüzden tanınmadı, marka 0 kayıt verdi. Aynı şekilde
   "I".lower() → "i" olurken Türkçe'de "ı" olmalı.
   Çözüm: önce Türkçe harfleri elle çevir, sonra küçült, kalan
   birleştirici işaretleri at → anahtar()

2) ROL KELİMELERİ
   Siteler aynı şeye farklı adlar veriyor:
     satış  → bayi, bayii, satıcı, yetkili satıcı, satış noktası,
              satış merkezi, showroom, dealer, mağaza
     servis → servis, yetkili servis, teknik servis, servis noktası
   Hepsi tek yerden tanınsın diye burada toplandı; marka modülleri
   kendi kelime listesini tutmuyor.
"""

from __future__ import annotations

import unicodedata

# Türkçe'ye özgü harf eşlemesi (casefold'dan ÖNCE uygulanır)
_TR = str.maketrans({
    "İ": "I", "I": "I", "ı": "i",
    "Ç": "C", "ç": "c", "Ğ": "G", "ğ": "g",
    "Ö": "O", "ö": "o", "Ş": "S", "ş": "s", "Ü": "U", "ü": "u",
    "Â": "A", "â": "a", "Î": "I", "î": "i", "Û": "U", "û": "u",
})


def anahtar(metin: str) -> str:
    """Karşılaştırma için güvenli anahtar üretir.

    'BAYİ', 'Bayi', 'bayii' → 'bayi' benzeri, aksansız, küçük harf.
    """
    if not metin:
        return ""
    t = " ".join(str(metin).split()).translate(_TR).lower()
    t = unicodedata.normalize("NFKD", t)
    return "".join(c for c in t if not unicodedata.combining(c))


# --------------------------------------------------------------- rol sözlüğü
# Kullanıcı kuralı: "satıcı", "bayi", "satış noktası" hepsi SATIŞ demek.
SATIS_SOZ = (
    "yetkili satici", "yetkili bayi", "satis noktasi", "satis noktalari",
    "satis merkezi", "satici", "bayii", "bayi", "showroom", "dealer",
    "magaza", "satis",
)
SERVIS_SOZ = (
    "yetkili servis", "teknik servis", "servis noktasi", "servis noktalari",
    "servis merkezi", "servisler", "servis",
)


# Motosiklet satış/servis noktası SAYILMAYAN etiketler.
# "Yedek Parça Bayi" bir bayi gibi görünse de araç satmıyor; Motolux'te
# ayrı bir sekme, Falcon'da ayrı bir bayrak (yp) olarak geliyor.
YOKSAY_SOZ = (
    "yedek parca", "aksesuar bayi", "aksesuar noktasi",
    "bayilik basvuru", "servislik basvuru", "bayi girisi", "bayi portali",
)


def yoksay_mi(metin: str) -> bool:
    """Motosiklet satış/servis noktası olmayan etiket mi?"""
    a = anahtar(metin)
    return bool(a) and any(k in a for k in YOKSAY_SOZ)


def rol_coz(metin: str, varsayilan: str = "") -> str:
    """Bir etiketten rol çıkarır: satis | servis | satis_servis | varsayılan.

    Hem satış hem servis kelimesi geçiyorsa ikisi birden kabul edilir
    ("Bayi ve Servis", "Satış + Servis" gibi başlıklar için).
    """
    a = anahtar(metin)
    if not a:
        return varsayilan
    if yoksay_mi(metin):
        return ""          # nokta sayılmaz

    satis = any(k in a for k in SATIS_SOZ)
    servis = any(k in a for k in SERVIS_SOZ)

    if satis and servis:
        return "satis_servis"
    if servis:
        return "servis"
    if satis:
        return "satis"
    return varsayilan


def esit(a: str, b: str) -> bool:
    """İki metin Türkçe farkları gözetilmeden aynı mı."""
    return anahtar(a) == anahtar(b)
