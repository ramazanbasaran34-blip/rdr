#!/usr/bin/env python3
"""BMW ve Korlas (Ducati/Triumph) — tarayıcıyla yakalar.

NEDEN TARAYICI GEREKİYOR
  · BMW: düz istek 120 sn'de bile yanıt vermiyor (ReadTimeout). Bu bir
    yavaşlık değil; sunucu tarayıcı olmayan istemciyi bekletip düşürüyor.
    Keşif raporuna göre sayfanın ilk yanıtında 77 telefon / ~52 kayıt var,
    yani veri sayfada duruyor — sadece alabilmek gerekiyor.
  · Korlas: Cloudflare "Just a moment..." ara sayfası (Turnstile yok,
    yani JS doğrulaması; gerçek tarayıcı genelde geçer).

Gerçek Chrome'u sanal ekranda görünür kipte çalıştırıyoruz; Hero'da da
kullanılan yöntem. Fark: burada il seçimi yok, sayfa tek seferde tam
listeyi veriyor, o yüzden tek ziyaret yetiyor.

    python bmw_korlas_yakala.py
"""

from __future__ import annotations

import gzip
import json
import random
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

CIKTI = Path("ham")

HEDEFLER = {
    "bmw":            "https://www.bmw-motorrad.com.tr/tr/ssl/yetkili-satici-ve-servisler.html",
    "korlas-bayi":    "https://korlas.com.tr/bayi/",
    "korlas-servis":  "https://korlas.com.tr/servis/",
}

KULLANICI = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

GIZLE = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['tr-TR','tr','en-US']});
Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
window.chrome = {runtime: {}, loadTimes: () => {}, csi: () => {}};
"""

TEL = re.compile(r"0\s*\(?\d{3}\)?[\s\-/]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}")


def ara_sayfada_mi(sayfa) -> bool:
    try:
        b = (sayfa.title() or "").lower()
    except Exception:
        return True
    return any(k in b for k in ("just a moment", "bir dakika",
                                "attention required", "lütfen"))


def oyalan(sayfa) -> None:
    try:
        for _ in range(random.randint(2, 4)):
            sayfa.mouse.move(random.randint(80, 1200), random.randint(120, 700),
                             steps=random.randint(5, 15))
            sayfa.wait_for_timeout(random.randint(150, 450))
        sayfa.mouse.wheel(0, random.randint(300, 900))
    except Exception:
        pass


def cerez_kabul(sayfa) -> None:
    """BMW'de onay katmanı listeyi gizleyebiliyor."""
    for sec in ("button:has-text('Kabul')", "button:has-text('Tümünü kabul')",
                "#onetrust-accept-btn-handler", ".cookie-accept",
                "button[data-testid*='accept']"):
        try:
            el = sayfa.query_selector(sec)
            if el:
                el.click(timeout=2500)
                sayfa.wait_for_timeout(800)
                return
        except Exception:
            continue


def yakala(sayfa, ad: str, url: str) -> dict:
    bilgi: dict = {"url": url}
    try:
        sayfa.goto(url, wait_until="domcontentloaded", timeout=120000)
    except Exception as e:
        bilgi["hata"] = f"{type(e).__name__}: {e}"[:150]
        return bilgi

    # Cloudflare ara sayfası varsa geçmesini bekle
    bitis = time.time() + 75
    while ara_sayfada_mi(sayfa) and time.time() < bitis:
        oyalan(sayfa)
        sayfa.wait_for_timeout(2000)

    cerez_kabul(sayfa)
    oyalan(sayfa)

    # Liste tembel yükleniyor olabilir: sona kadar kaydır
    for _ in range(6):
        try:
            sayfa.mouse.wheel(0, 2500)
        except Exception:
            break
        sayfa.wait_for_timeout(900)
    try:
        sayfa.wait_for_load_state("networkidle", timeout=20000)
    except Exception:
        pass

    html = sayfa.content()
    bilgi["baslik"] = (sayfa.title() or "")[:60]
    bilgi["boyut"] = len(html)
    bilgi["tel"] = len(TEL.findall(html))
    bilgi["ara_sayfa"] = ara_sayfada_mi(sayfa)

    CIKTI.mkdir(exist_ok=True)
    (CIKTI / f"{ad}-tarayici.html.gz").write_bytes(
        gzip.compress(html.encode("utf-8", "replace")))
    return bilgi


def main() -> None:
    CIKTI.mkdir(exist_ok=True)
    rapor: dict = {}
    with sync_playwright() as pw:
        baslat = dict(args=["--disable-blink-features=AutomationControlled",
                            "--no-sandbox", "--disable-dev-shm-usage"],
                      headless=False)
        try:
            t = pw.chromium.launch(channel="chrome", **baslat)
        except Exception:
            t = pw.chromium.launch(**baslat)
        ctx = t.new_context(user_agent=KULLANICI, locale="tr-TR",
                            timezone_id="Europe/Istanbul",
                            viewport={"width": 1366, "height": 768},
                            extra_http_headers={"Accept-Language": "tr-TR,tr;q=0.9"})
        ctx.add_init_script(GIZLE)
        s = ctx.new_page()

        for ad, url in HEDEFLER.items():
            print(f"→ {ad}", flush=True)
            b = yakala(s, ad, url)
            rapor[ad] = b
            if "hata" in b:
                print(f"   ✗ {b['hata'][:80]}")
            else:
                print(f"   {b['boyut']//1024}KB tel={b['tel']} "
                      f"ara_sayfa={b['ara_sayfa']} | {b['baslik'][:40]}")
            s.wait_for_timeout(random.randint(2000, 5000))

        ctx.close(); t.close()

    (CIKTI / "bmw-korlas.json").write_text(
        json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rapor, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
