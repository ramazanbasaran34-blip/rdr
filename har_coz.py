#!/usr/bin/env python3
"""Chrome HAR kaydından bayi/servis kayıtlarını çıkarır.

NEDEN BU YÖNTEM
Hero'nun sitesi Cloudflare arkasında ve bizim altyapımızdan gelen her PHP
isteğine 403 dönüyor (statik dosyalar 200 dönüyor; farkı ölçtük). Yani
adresi bilsek bile sunucuya doğrudan istek atamıyoruz.

Bu betik sunucuya HİÇ istek atmıyor. Kullanıcının kendi tarayıcısında
zaten gerçekleşmiş isteklerin kaydını (HAR) okuyup içindeki yanıtlardan
kayıtları çıkarıyor. Cloudflare aşılmıyor; onun izin verdiği normal
oturumun çıktısı kullanılıyor.

HAR NASIL ALINIR
  1. Chrome'da https://www.heromotor.com.tr/bayiler/ aç
  2. F12 → Network sekmesi → "Preserve log" işaretle
  3. İl açılır kutusundan bir il seç, Ara'ya bas. Her il için tekrarla.
  4. Network panelinde sağ tık → "Save all as HAR with content"
  5. Aynısını /servisler/ için de yap.

KULLANIM
    python har_coz.py hero-bayiler.har hero-servisler.har
    python har_coz.py *.har --cikti elle/hero.json

Marka adı varsayılan Hero; başka marka için --marka ile değiştir.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, unquote

from bs4 import BeautifulSoup

TEL = re.compile(r"(?:\+90|0)[\s\(\)\-/\.]*\d{3}[\s\(\)\-/\.]*\d{3}[\s\-/\.]*\d{2}[\s\-/\.]*\d{2}")


def _m(el) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ")).strip() if el else ""


def il_haritasi(har: dict) -> dict[str, str]:
    """HAR içindeki sayfa yanıtlarından il kodu → il adı eşlemesi kurar.

    Sayfanın kendi <select name="city_box"> listesi HAR'da olduğu için
    kodları elle yazmaya gerek yok; site sırayı değiştirse bile tutar.
    """
    harita: dict[str, str] = {}
    for e in har.get("log", {}).get("entries", []):
        govde = (e.get("response", {}).get("content", {}) or {}).get("text") or ""
        if "city_box" not in govde:
            continue
        soup = BeautifulSoup(govde, "html.parser")
        for sec in soup.find_all("select"):
            if (sec.get("name") or "") != "city_box":
                continue
            for o in sec.find_all("option"):
                d = (o.get("value") or "").strip()
                ad = re.sub(r"\s+", " ", o.get_text(" ")).strip()
                if d and d != "0" and ad:
                    harita.setdefault(d, ad)
    return harita


def istekten_il(e: dict, harita: dict[str, str]) -> str:
    """İsteğin hangi il için yapıldığını bulur (POST gövdesi ya da adres)."""
    istek = e.get("request", {})

    gonderilen = (istek.get("postData") or {}).get("text") or ""
    for anahtar in ("city_box", "city", "sehir", "il"):
        m = re.search(anahtar + r"=([^&]+)", gonderilen)
        if m:
            deger = unquote(m.group(1))
            return harita.get(deger, deger if not deger.isdigit() else "")

    q = parse_qs((istek.get("url") or "").split("?", 1)[-1])
    for anahtar in ("city_box", "city", "sehir", "il"):
        if anahtar in q:
            deger = q[anahtar][0]
            return harita.get(deger, deger if not deger.isdigit() else "")
    return ""


def rol_bul(e: dict) -> str:
    u = (e.get("request", {}).get("url") or "").lower()
    g = ((e.get("request", {}).get("postData") or {}).get("text") or "").lower()
    if "servis" in u or "service" in u or "servis" in g:
        return "servis"
    return "satis"


def kayitlari_coz(govde: str, il: str, rol: str, marka: str) -> list[dict]:
    """Yanıt gövdesinden kartları çıkarır.

    Telefon bağlantısı her kaydın çapası; kaydın kutusu onun atası.
    Böylece sayfa şablonu değişse de çalışmaya devam ediyor.
    """
    soup = BeautifulSoup(govde, "html.parser")
    out: list[dict] = []
    gorulen: set[tuple[str, str]] = set()

    for a in soup.select("a[href^='tel:']"):
        tel = a.get("href", "")[4:].strip()
        if not tel:
            continue

        kutu = a
        for _ in range(5):
            kutu = kutu.parent
            if kutu is None:
                break
            if len(_m(kutu).split()) > 8:
                break
        if kutu is None:
            continue

        bas = kutu.find(["h1", "h2", "h3", "h4", "h5", "h6", "strong", "b"])
        ad = _m(bas)
        if not ad or TEL.fullmatch(ad):
            continue

        adres = ""
        for el in kutu.find_all(["p", "span", "td", "div"]):
            t = _m(el)
            if t and t != ad and not TEL.fullmatch(t) and len(t) > len(adres):
                adres = t

        # Adres sonu "... NO:65 A EDREMİT / BALIKESİR" biçiminde.
        # Eğik çizginin solundaki SON kelime ilçe; tüm adresi almamak
        # için kelime bazında kırpıp içinde rakam/kısaltma olanları eliyoruz.
        ilce = ""
        m = re.search(r"([^/,]{2,60})\s*/\s*([^/,]{2,30})\s*$", adres)
        if m:
            kelimeler = m.group(1).strip().split()
            for n in (1, 2):
                aday = " ".join(kelimeler[-n:]).strip()
                if aday and not re.search(r"\d|no:|mah\.|cad\.|sok|blv|bulv",
                                          aday, re.I):
                    ilce = aday
                    break

        k = (ad.casefold(), tel)
        if k in gorulen:
            continue
        gorulen.add(k)

        out.append({"marka": marka, "rol": rol, "bayi_adi": ad, "il": il,
                    "ilce": ilce, "adres": adres, "telefon": tel,
                    "email": "", "website": ""})
    return out


def har_isle(yol: Path, marka: str) -> list[dict]:
    har = json.loads(yol.read_text(encoding="utf-8", errors="replace"))
    harita = il_haritasi(har)
    print(f"  {yol.name}: {len(harita)} il eşlemesi bulundu")

    hepsi: list[dict] = []
    for e in har.get("log", {}).get("entries", []):
        icerik = e.get("response", {}).get("content", {}) or {}
        govde = icerik.get("text") or ""
        if not govde or "tel:" not in govde:
            continue
        tip = (icerik.get("mimeType") or "").lower()
        if "html" not in tip and "json" not in tip and "text" not in tip:
            continue

        il = istekten_il(e, harita)
        rol = rol_bul(e)
        k = kayitlari_coz(govde, il, rol, marka)
        if k:
            u = (e.get("request", {}).get("url") or "")[:70]
            print(f"    {rol:7} {il or '(il?)':14} {len(k):3} kayıt  ← {u}")
            hepsi.extend(k)
    return hepsi


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("har", nargs="+", help="HAR dosyaları")
    ap.add_argument("--marka", default="Hero")
    ap.add_argument("--cikti", default="elle/hero.json")
    a = ap.parse_args()

    hepsi: list[dict] = []
    for p in a.har:
        yol = Path(p)
        if not yol.exists():
            print(f"  ✗ {p} bulunamadı"); continue
        hepsi.extend(har_isle(yol, a.marka))

    # Tekilleştir: aynı firma birden çok HAR'da geçebilir
    gorulen, temiz = set(), []
    for k in hepsi:
        anahtar = (k["bayi_adi"].casefold(), k["telefon"], k["rol"])
        if anahtar in gorulen:
            continue
        gorulen.add(anahtar)
        temiz.append(k)

    ilsiz = sum(1 for k in temiz if not k["il"])
    print(f"\n  toplam {len(temiz)} kayıt, "
          f"{len({k['il'] for k in temiz if k['il']})} il"
          + (f", {ilsiz} kayıtta il boş" if ilsiz else ""))
    if not temiz:
        sys.exit("HAR içinde kayıt bulunamadı — 'Save all as HAR with content' "
                 "seçeneğiyle kaydedildiğinden emin ol.")

    veri = {
        "_aciklama": (f"{a.marka} — kullanıcının kendi tarayıcı oturumundan "
                      "alınan HAR kaydından çıkarıldı. Site Cloudflare "
                      "arkasında olduğu için otomatik taranamıyor."),
        "_kaynak": ["https://www.heromotor.com.tr/bayiler/",
                    "https://www.heromotor.com.tr/servisler/"],
        "_tarih": __import__("time").strftime("%Y-%m-%d"),
        "_duzenlenebilir": True,
        "kayitlar": temiz,
    }
    cikti = Path(a.cikti)
    cikti.parent.mkdir(parents=True, exist_ok=True)
    cikti.write_text(json.dumps(veri, ensure_ascii=False, indent=1),
                     encoding="utf-8")
    print(f"  ✓ {cikti}")


if __name__ == "__main__":
    main()
