#!/usr/bin/env python3
"""Keşif aracı — bir bayi sayfasının yapısını çözer ve seçici önerir.

Sorun: 63 markanın her biri farklı HTML yapısı kullanıyor. Tarifi yazmak için
sayfanın ham HTML'ini görmek gerekiyor.

Bu araç sayfayı çeker, bayi kayıtlarının tekrar ettiği kabı otomatik bulur ve
hazır tarif taslağı basar. Çıktıyı brands.yaml'e yapıştırıp test edebilirsin.

Kullanım:
    python kesfet.py "https://motolux.com.tr/bayiler/sehir/aksaray/"
    python kesfet.py --marka "Motolux"        # brands.yaml'deki URL'i kullanır
"""

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

from bs4 import BeautifulSoup

from bayiradar.fetch import Fetcher

# Bayi kaydının işaretleri
TEL = re.compile(r"(?:\+90|0)?\s*[\(]?\d{3}[\)]?\s*\d{3}\s*\d{2}\s*\d{2}"
                 r"|\b\d{10,11}\b")
ADRES = re.compile(r"\b(mah|mh|cad|cd|sok|sk|blv|bulv|no:|apt|osb)\b[\.\s:]",
                   re.I)
ILCE_IPUCU = re.compile(r"\b(merkez|ilçe|ilce)\b", re.I)

GURULTU = {"script", "style", "noscript", "svg", "head", "meta", "link"}


def _secici(el) -> str:
    """Bir elemana CSS seçici üretir: div.dealer-card gibi."""
    tag = el.name
    sinif = [c for c in (el.get("class") or []) if not re.match(r"^(w|col|row)-", c)]
    if sinif:
        return tag + "." + ".".join(sinif[:3])
    if el.get("id"):
        return f"{tag}#{el['id']}"
    return tag


def _yol(el, derinlik=3) -> str:
    """Ata zincirinden daha ayırt edici bir seçici kurar."""
    parcalar, cur = [], el
    for _ in range(derinlik):
        if cur is None or cur.name in ("html", "[document]"):
            break
        parcalar.append(_secici(cur))
        cur = cur.parent
    return " > ".join(reversed(parcalar))


def _puan(metin: str) -> int:
    """Bu metin bir bayi kaydına ne kadar benziyor?"""
    p = 0
    if TEL.search(metin):
        p += 5
    if ADRES.search(metin):
        p += 4
    if 40 < len(metin) < 900:
        p += 2
    if metin.count("\n") > 1:
        p += 1
    return p


def adaylari_bul(html: str, en_az=3):
    """Kardeşleri aynı yapıda olan, bayi bilgisi içeren kapları bulur."""
    soup = BeautifulSoup(html, "html.parser")
    for g in soup(list(GURULTU)):
        g.decompose()

    gruplar = defaultdict(list)
    for el in soup.find_all(True):
        if el.name in GURULTU or not el.parent:
            continue
        anahtar = (id(el.parent), el.name, tuple(sorted(el.get("class") or [])))
        gruplar[anahtar].append(el)

    adaylar = []
    for (_, tag, sinif), elemanlar in gruplar.items():
        if len(elemanlar) < en_az:
            continue
        metinler = [e.get_text(" ", strip=True) for e in elemanlar]
        telli = sum(1 for m in metinler if TEL.search(m))
        if telli < max(2, len(elemanlar) * 0.4):
            continue
        toplam = sum(_puan(m) for m in metinler) / len(metinler)
        adaylar.append({
            "secici": _yol(elemanlar[0]),
            "basit": _secici(elemanlar[0]),
            "adet": len(elemanlar),
            "puan": round(toplam, 1),
            "ornek": elemanlar[:2],
            "metinler": metinler[:2],
        })

    # Çok kayıt + yüksek puan önce
    adaylar.sort(key=lambda a: (-a["puan"], -a["adet"]))
    return adaylar, soup


def alan_onerileri(ornek):
    """Örnek kaydın içindeki alanları tahmin eder.

    Yalnızca "yaprak" elemanlara bakar (içinde başka metinli eleman olmayan),
    yoksa telefon 'li' yerine onu saran 'ul'a eşleşir.
    """
    oneri, kullanilan = {}, set()

    yapraklar = []
    for c in ornek.find_all(True):
        if c.find(True) and c.get_text(" ", strip=True) != \
                (c.find(True).get_text(" ", strip=True) if c.find(True) else ""):
            # içinde metinli çocuk var → yaprak değil
            if any(x.get_text(strip=True) for x in c.find_all(True)):
                continue
        m = c.get_text(" ", strip=True)
        if m and len(m) < 300:
            yapraklar.append((c, m))

    # 1. Telefon: tel: bağlantısı en güvenilir kaynak
    tel_link = ornek.select_one("a[href^='tel:']")
    if tel_link:
        oneri["telefon"] = {"sel": "a[href^='tel:']", "attr": "href",
                            "regex": "tel:(.+)"}
    else:
        for c, m in yapraklar:
            if TEL.search(m):
                oneri["telefon"] = _secici(c)
                kullanilan.add(id(c))
                break

    # 2. Adres
    for c, m in yapraklar:
        if id(c) in kullanilan:
            continue
        if ADRES.search(m):
            oneri["adres"] = _secici(c)
            kullanilan.add(id(c))
            break

    # 3. İlçe: kısa, telefon/adres içermeyen, çoğunlukla büyük harf başlık
    for c, m in yapraklar:
        if id(c) in kullanilan or TEL.search(m) or ADRES.search(m):
            continue
        if len(m) <= 28 and (c.name.startswith("h") or m.isupper()):
            oneri["ilce"] = _secici(c)
            kullanilan.add(id(c))
            break

    # 4. Bayi adı: kalan en uzun anlamlı metin
    aday = None
    for c, m in yapraklar:
        if id(c) in kullanilan or TEL.search(m) or ADRES.search(m):
            continue
        if len(m) < 4 or m.lower() in ("ara", "yol tarifi al", "detay", "harita"):
            continue
        if aday is None or len(m) > len(aday[1]):
            aday = (c, m)
    if aday:
        oneri["bayi_adi"] = _secici(aday[0])

    return oneri


def yazdir(url, html, adaylar, kayit_dizini="kesif"):
    Path(kayit_dizini).mkdir(exist_ok=True)
    ad = re.sub(r"[^a-z0-9]+", "-", url.lower())[:80].strip("-")
    dosya = Path(kayit_dizini) / f"{ad}.html"
    dosya.write_text(html, encoding="utf-8")

    print("=" * 74)
    print(f"KEŞİF: {url}")
    print(f"HTML boyutu: {len(html):,} karakter · ham kopya: {dosya}")
    print("=" * 74)

    if not adaylar:
        print("""
Bayi kaydına benzeyen tekrar eden yapı BULUNAMADI.

Muhtemel sebepler:
  • Liste JavaScript ile çiziliyor  → tarifte  mode: browser  dene
  • Sayfa il seçimi bekliyor        → URL'ye il parametresi eklemek gerekiyor
  • Sayfa bir API'den besleniyor    → F12 > Network > XHR sekmesine bak

Ham HTML kaydedildi, içinde 'bayi' veya bir telefon numarası arayabilirsin.
""")
        return

    for i, a in enumerate(adaylar[:4], 1):
        print(f"\n--- ADAY {i} ---  {a['adet']} kayıt · uygunluk {a['puan']}")
        print(f"row: \"{a['basit']}\"")
        if a["basit"] != a["secici"]:
            print(f"   (daha dar: \"{a['secici']}\")")
        for m in a["metinler"]:
            print(f"   ör: {m[:150]}")

        if i == 1:
            print("\n   Önerilen tarif:")
            print(f"    mode: html")
            print(f"    url: \"{url}\"")
            print(f"    row: \"{a['basit']}\"")
            print(f"    fields:")
            for alan, sec in alan_onerileri(a["ornek"][0]).items():
                print(f"      {alan+':':<10} {sec}")

    print("\n" + "=" * 74)
    print("Bu çıktıyı bana gönder, tarifi kesinleştireyim.")
    print("=" * 74)


def main():
    p = argparse.ArgumentParser(description="Bayi sayfası keşif aracı")
    p.add_argument("url", nargs="?", help="İncelenecek adres")
    p.add_argument("--marka", help="brands.yaml'deki markanın URL'ini kullan")
    p.add_argument("--encoding", help="windows-1254 gibi zorla kodlama")
    p.add_argument("--browser", action="store_true",
                   help="Gerçek tarayıcıyla aç (JS ile çizilen sayfalar)")
    a = p.parse_args()

    url = a.url
    if a.marka:
        from bayiradar.collect import load_config
        cfg = load_config().get("markalar", {}).get(a.marka)
        if not cfg:
            sys.exit(f"'{a.marka}' brands.yaml içinde yok.")
        url = cfg["url"].split("{")[0] if "{" in cfg["url"] else cfg["url"]
    if not url:
        sys.exit("Adres ya da --marka vermelisin.")

    f = Fetcher(use_cache=False, delay=0.5)
    try:
        html = (f.render(url, max_age=0) if a.browser
                else f.get(url, max_age=0, encoding=a.encoding))
    finally:
        f.close()

    adaylar, _ = adaylari_bul(html)
    yazdir(url, html, adaylar)


if __name__ == "__main__":
    main()
