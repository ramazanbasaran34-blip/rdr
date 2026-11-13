#!/usr/bin/env python3
"""Yamaha bayi bulucusunu gerçek tarayıcıyla kullanır.

Statik analiz tıkandı: React yükleyicisi 15KB'lık bir kabuk, bayi API'sinin
adresi tembel yüklenen bir parçanın içinde. Bunu aramak yerine sayfayı bir
insan gibi kullanıp ağ trafiğini dinliyoruz — hangi uca ne sorulduğu böyle
kendiliğinden ortaya çıkıyor.

Yaptığı:
  1. Bayi bulucuyu açar, çerez uyarısını kapatır
  2. Ülke = Türkiye seçer, kategori = Motosiklet
  3. TÜM ağ isteklerini kaydeder; JSON dönenleri ayrıca saklar
  4. Ekranda oluşan bayi listesini de HTML olarak kaydeder

Çıktı: ham/yamaha-aglar.json, ham/yamaha-json-*.json.gz, ham/yamaha-dom.html.gz
"""

from __future__ import annotations

import gzip
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

CIKTI = Path("ham")
URL = "https://www.yamaha-motor.eu/tr/tr/dealer-locator/?category=MCM"

GURULTU = ("googletagmanager", "google-analytics", "doubleclick", "facebook",
           "hotjar", "visualwebsiteoptimizer", "adobedtm", "gstatic",
           "fonts.", "helix-rum", "mpulse", "/etc.clientlibs/", ".css",
           ".woff", ".png", ".jpg", ".svg", ".webp", "maps.googleapis")


def ilgili(u: str) -> bool:
    return not any(g in u for g in GURULTU)


def main() -> None:
    CIKTI.mkdir(exist_ok=True)
    aglar: list[dict] = []
    kayitli = 0

    with sync_playwright() as pw:
        t = pw.chromium.launch(args=["--no-sandbox"])
        s = t.new_context(locale="tr-TR",
                          viewport={"width": 1400, "height": 1000})
        sayfa = s.new_page()

        def yanit(r):
            nonlocal kayitli
            u = r.url
            if not ilgili(u):
                return
            tip = (r.headers or {}).get("content-type", "")
            kayit = {"url": u[:300], "kod": r.status, "tip": tip[:60]}
            # İsteğin kendisini de kaydet: yöntem, gövde, başlıklar.
            # Ucu sonradan tarayıcısız çağırabilmek için sözleşme bu.
            try:
                istek = r.request
                kayit["yontem"] = istek.method
                kayit["gonderilen"] = (istek.post_data or "")[:1500]
                bl = istek.headers or {}
                kayit["istek_basliklari"] = {
                    k: v[:120] for k, v in bl.items()
                    if k.lower() in ("content-type", "accept", "authorization",
                                     "x-api-key", "apollographql-client-name")}
            except Exception:  # noqa: BLE001
                pass
            try:
                govde = r.text()
                kayit["boyut"] = len(govde)
                # Bayi verisi olma ihtimali: JSON ve içinde adres/telefon geçiyor
                puan = sum(1 for a in ("dealer", "address", "phone", "postalCode",
                                       "latitude", "city") if a.lower() in govde.lower())
                kayit["puan"] = puan
                if "json" in tip and puan >= 2 and len(govde) > 300:
                    kayitli += 1
                    ad = re.sub(r"[^a-zA-Z0-9]+", "-", u.split("?")[0])[-70:]
                    (CIKTI / f"yamaha-json-{kayitli:02d}{ad}.json.gz").write_bytes(
                        gzip.compress(govde.encode("utf-8", "replace")))
                    kayit["kaydedildi"] = True
            except Exception:  # noqa: BLE001
                pass
            aglar.append(kayit)

        sayfa.on("response", yanit)

        sayfa.goto(URL, wait_until="networkidle", timeout=90000)

        # Çerez uyarısı — birkaç olası düğme metni dene
        for metin in ("Tümünü kabul et", "Kabul", "Accept all", "Accept",
                      "Tümünü Kabul Et"):
            try:
                d = sayfa.get_by_role("button", name=re.compile(metin, re.I))
                if d.count():
                    d.first.click(timeout=4000)
                    sayfa.wait_for_timeout(1500)
                    break
            except Exception:  # noqa: BLE001
                continue

        # Ülke seçimi: hem select hem özel açılır liste olabilir
        for deneme in ("Türkiye", "Turkey", "TR"):
            try:
                sec = sayfa.locator("select").first
                if sec.count():
                    sec.select_option(label=deneme, timeout=4000)
                    sayfa.wait_for_timeout(3000)
                    break
            except Exception:  # noqa: BLE001
                continue

        # Konum kutusuna bir il yazıp aramayı tetikle (insan davranışı)
        try:
            kutu = sayfa.locator("input[type=text], input[type=search]").first
            if kutu.count():
                kutu.click(timeout=5000)
                kutu.fill("Istanbul")
                sayfa.wait_for_timeout(2500)
                sayfa.keyboard.press("Enter")
                sayfa.wait_for_timeout(6000)
        except Exception:  # noqa: BLE001
            pass

        sayfa.wait_for_timeout(5000)
        (CIKTI / "yamaha-dom.html.gz").write_bytes(
            gzip.compress(sayfa.content().encode("utf-8", "replace")))
        t.close()

    aglar.sort(key=lambda x: -x.get("puan", 0))
    (CIKTI / "yamaha-aglar.json").write_text(
        json.dumps(aglar[:60], ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"toplam istek: {len(aglar)} | kaydedilen json: {kayitli}")
    for a in aglar[:15]:
        print(f"  puan={a.get('puan',0):2} {a['kod']} {a.get('boyut',0):>8} {a['url'][:105]}")


if __name__ == "__main__":
    main()
