#!/usr/bin/env python3
"""Hero — POST gerektirmeyen bir GET yolu arar.

Tanılama şunu gösterdi: ilk sayfa yüklemesi engele TAKILMIYOR
("ilk_engel": false), engel yalnızca form POST'unda çıkıyor. Üç yöntem de
(insan gibi tıklama, XHR, adres satırı) POST'a dayandığı için üçü de
engellendi.

O yüzden burada POST'u tamamen bırakıp GET ile ulaşılabilir bir yol
arıyoruz: site haritası, il bazlı adresler, sayfalama, olası JSON uçları.
Hepsi doğrulaması geçilmiş tarayıcı sekmesinden çekiliyor.
"""

from __future__ import annotations

import gzip
import json
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

CIKTI = Path("ham")
KOK = "https://www.heromotor.com.tr"
KULLANICI = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
TEL = re.compile(r"0\s*\(?\d{3}\)?[\s\-/]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}")


def engel_mi(html: str) -> bool:
    d = (html or "").lower()
    return "just a moment" in d or "bir dakika" in d or "cf-challenge" in d


def getir(sayfa, yol: str) -> tuple[int, str]:
    """Doğrulanmış sekmeden aynı kaynağa GET; sekmeden ayrılmıyoruz."""
    try:
        return sayfa.evaluate("""async (u) => {
          const y = await fetch(u, {credentials: 'same-origin'});
          return [y.status, await y.text()];
        }""", yol)
    except Exception as e:  # noqa: BLE001
        return (-1, f"{type(e).__name__}: {e}")


def main() -> None:
    CIKTI.mkdir(exist_ok=True)
    rapor: dict = {}

    with sync_playwright() as pw:
        t = pw.chromium.launch(args=["--disable-blink-features=AutomationControlled"])
        ctx = t.new_context(user_agent=KULLANICI, locale="tr-TR",
                            timezone_id="Europe/Istanbul",
                            viewport={"width": 1366, "height": 900})
        ctx.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
        s = ctx.new_page()
        s.goto(f"{KOK}/bayiler/", wait_until="domcontentloaded", timeout=60000)
        s.wait_for_timeout(2500)
        rapor["giris_engeli"] = engel_mi(s.content())

        # 1) İl adlarını sayfadaki seçiciden al
        iller = s.eval_on_selector_all(
            "select[name=city_box] option",
            "els => els.map(e => [e.value, (e.textContent||'').trim()])"
            ".filter(x => x[0] && x[0] !== '0')")
        rapor["il_sayisi"] = len(iller)

        # 2) Site haritası ve robots — GET, engellenmemeli
        for ad, yol in (("robots", "/robots.txt"),
                        ("sitemap", "/sitemap.xml"),
                        ("sitemap_index", "/sitemap_index.xml")):
            kod, govde = getir(s, KOK + yol)
            rapor[ad] = {"kod": kod, "boyut": len(govde) if isinstance(govde, str) else 0,
                         "engel": engel_mi(govde) if isinstance(govde, str) else None}
            if isinstance(govde, str) and kod == 200 and not engel_mi(govde):
                (CIKTI / f"hero-{ad}.gz").write_bytes(
                    gzip.compress(govde.encode("utf-8", "replace")))
                if "bayi" in govde.lower():
                    baglar = sorted(set(re.findall(
                        r"https?://[^<\s\"']*bayi[^<\s\"']*", govde)))[:40]
                    rapor[ad + "_bayi_baglari"] = baglar

        # 3) Olası GET adres kalıplarını dene (Ankara = 6)
        adaylar = [
            "/bayiler/ankara", "/bayiler/ankara/", "/bayiler/6", "/bayiler/6/",
            "/bayiler/?city_box=6", "/bayiler/index.php?city_box=6",
            "/bayi-ara?city_box=6", "/api/bayiler", "/api/bayiler.php",
            "/wp-json/wp/v2/pages", "/bayiler/?sehir=ankara",
        ]
        rapor["adaylar"] = {}
        for yol in adaylar:
            kod, govde = getir(s, KOK + yol)
            if not isinstance(govde, str):
                continue
            n = len(TEL.findall(govde))
            rapor["adaylar"][yol] = {"kod": kod, "kb": len(govde) // 1024,
                                     "tel": n, "engel": engel_mi(govde)}
            if kod == 200 and n > 0 and not engel_mi(govde):
                (CIKTI / f"hero-aday-{yol.strip('/').replace('/', '_').replace('?', '_')}.html.gz"
                 ).write_bytes(gzip.compress(govde.encode("utf-8", "replace")))
            time.sleep(0.3)

        ctx.close(); t.close()

    (CIKTI / "hero-yol.json").write_text(
        json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rapor, ensure_ascii=False, indent=1)[:2500])


if __name__ == "__main__":
    main()
