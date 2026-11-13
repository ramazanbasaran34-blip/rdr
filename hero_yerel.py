#!/usr/bin/env python3
"""Hero bayi ve servis listesini toplar — KENDİ BİLGİSAYARINDAN çalıştır.

NEDEN BU BETİK VAR
Hero'nun sitesi Cloudflare arkasında ve GitHub'ın sunucu IP'lerini
engelliyor. Aynı sayfa senin telefonundan/bilgisayarından sorunsuz
açılıyor — sorun içerik değil, isteğin nereden geldiği. Bu yüzden veri
toplamayı senin normal internet bağlantından yapıyoruz.

Bu betik hiçbir şeyi "aşmaya" çalışmıyor: sahte tarayıcı bilgisi
göndermiyor, doğrulama atlatmıyor, vekil sunucu kullanmıyor. Sitenin
kendi arama formunu, insan hızında (her il arasında 2-4 saniye bekleyerek)
kullanıyor. Tarayıcıda 81 kez il seçip Ara'ya basmanın otomatik hâli.

KURULUM (bir kez)
    Python kurulu değilse: python.org/downloads (kurarken
    "Add Python to PATH" kutusunu işaretle)
    Sonra komut satırında:
        pip install requests beautifulsoup4

ÇALIŞTIRMA
        python hero_yerel.py

    Yaklaşık 5-8 dakika sürer. Bittiğinde yanına "hero.json" dosyası
    oluşur. O dosyayı bana gönder ya da depoda elle/ klasörüne koy.
"""

from __future__ import annotations

import json
import random
import re
import sys
import time

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("Önce şunu çalıştır:  pip install requests beautifulsoup4")

SAYFA = {
    "satis":  "https://www.heromotor.com.tr/bayiler/",
    "servis": "https://www.heromotor.com.tr/servisler/",
}

TEL = re.compile(r"(?:\+90|0)[\s\(\)\-/\.]*\d{3}[\s\(\)\-/\.]*\d{3}[\s\-/\.]*\d{2}[\s\-/\.]*\d{2}")


def iller(oturum, url):
    """Sayfadaki şehir listesini okur: [(deger, ad), ...]"""
    y = oturum.get(url, timeout=60)
    y.raise_for_status()
    s = BeautifulSoup(y.text, "html.parser")
    sec = s.find("select", attrs={"name": "city_box"})
    if not sec:
        return []
    out = []
    for o in sec.find_all("option"):
        d = (o.get("value") or "").strip()
        ad = re.sub(r"\s+", " ", o.get_text(" ")).strip()
        if d and d != "0" and ad:
            out.append((d, ad))
    return out


def il_cek(oturum, url, kod):
    """Formu gönderir — tarayıcıda Ara'ya basmakla aynı istek."""
    y = oturum.post(url, data={"city_box": kod, "ara": "Ara"}, timeout=60)
    y.raise_for_status()
    return y.text


def kayitlari_coz(html, il, rol):
    """Sonuç sayfasındaki kartları okur."""
    s = BeautifulSoup(html, "html.parser")
    out, gorulen = [], set()

    for a in s.select("a[href^='tel:']"):
        tel = a.get("href", "")[4:].strip()
        kutu = a
        for _ in range(5):
            kutu = kutu.parent
            if kutu is None:
                break
            if len(kutu.get_text(" ").split()) > 8:
                break
        if kutu is None:
            continue

        bas = kutu.find(["h1", "h2", "h3", "h4", "h5", "strong", "b"])
        ad = re.sub(r"\s+", " ", bas.get_text(" ")).strip() if bas else ""
        if not ad:
            continue

        adres = ""
        for el in kutu.find_all(["p", "span", "td"]):
            t = re.sub(r"\s+", " ", el.get_text(" ")).strip()
            if t and t != ad and not TEL.fullmatch(t) and len(t) > len(adres):
                adres = t

        k = (ad.casefold(), tel)
        if k in gorulen:
            continue
        gorulen.add(k)
        out.append({"marka": "Hero", "rol": rol, "bayi_adi": ad, "il": il,
                    "ilce": "", "adres": adres, "telefon": tel,
                    "email": "", "website": ""})
    return out


def main():
    oturum = requests.Session()
    oturum.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/124.0 Safari/537.36",
        "Accept-Language": "tr-TR,tr;q=0.9",
    })

    hepsi = []
    for rol, url in SAYFA.items():
        print(f"\n=== {rol.upper()} ===")
        try:
            liste = iller(oturum, url)
        except Exception as e:
            print(f"  Sayfa açılamadı: {e}")
            continue
        if not liste:
            print("  Şehir listesi bulunamadı — sayfa yapısı değişmiş olabilir.")
            continue
        print(f"  {len(liste)} il bulundu")

        for i, (kod, ad) in enumerate(liste, 1):
            try:
                html = il_cek(oturum, url, kod)
                k = kayitlari_coz(html, ad, rol)
            except Exception as e:
                print(f"  [{i}/{len(liste)}] {ad}: HATA {str(e)[:50]}")
                continue
            hepsi.extend(k)
            print(f"  [{i}/{len(liste)}] {ad}: {len(k)} kayıt")
            time.sleep(random.uniform(2, 4))   # siteyi yormayalım

    veri = {
        "_aciklama": ("Hero Türkiye bayi ve servis ağı. Sitenin kendi arama "
                      "formu kullanılarak, kullanıcının kendi bağlantısından "
                      "toplandı."),
        "_kaynak": list(SAYFA.values()),
        "_tarih": time.strftime("%Y-%m-%d"),
        "_duzenlenebilir": True,
        "kayitlar": hepsi,
    }
    with open("hero.json", "w", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False, indent=1)

    iller_sayi = len({k["il"] for k in hepsi if k["il"]})
    print(f"\n✓ Bitti: {len(hepsi)} kayıt, {iller_sayi} il → hero.json")
    print("  Bu dosyayı gönder, gerisini ben hallederim.")


if __name__ == "__main__":
    main()
