#!/usr/bin/env python3
"""WordPress admin-ajax kullanan siteleri tarayıcıyla dinler.

Yuki ve STMax listeyi `wp-admin/admin-ajax.php` üzerinden çekiyor ama
`action` adı kaynakta düz metin olarak GEÇMİYOR (paketlenmiş JS içinde).
Adı tahmin etmek yerine sayfayı gerçek tarayıcıda açıp il seçiyoruz ve
giden isteği dinliyoruz. Bir kez öğrendikten sonra tarama düz POST ile
yapılabilir; tarayıcıya bir daha gerek kalmaz.

    python ajax_dinle.py yuki stmax
"""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path
from urllib.parse import parse_qs

from playwright.sync_api import sync_playwright

CIKTI = Path("ham")

HEDEF = {
    "yuki": {
        "url": "https://yukimotor.com.tr/satis-noktalari/",
        "secici": "select, .il-secim select, #il",
    },
    "yuki-servis": {
        "url": "https://yukimotor.com.tr/servis-noktalari/",
        "secici": "select",
    },
    "stmax": {
        "url": "https://stmax.com.tr/yetkili-servisler/",
        "secici": "#il-secimi, select",
    },
}

KULLANICI = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def dinle(ad: str, ayar: dict) -> dict:
    rapor: dict = {"url": ayar["url"], "istekler": []}
    CIKTI.mkdir(exist_ok=True)

    with sync_playwright() as pw:
        t = pw.chromium.launch()
        ctx = t.new_context(user_agent=KULLANICI, locale="tr-TR")
        s = ctx.new_page()

        yakalanan: list[dict] = []

        def istek_izle(istek):
            u = istek.url
            if "admin-ajax.php" not in u and "/wp-json/" not in u:
                return
            kayit = {"url": u, "method": istek.method}
            govde = istek.post_data
            if govde:
                kayit["govde"] = govde[:400]
                try:
                    kayit["alanlar"] = {k: v[0] for k, v in parse_qs(govde).items()}
                except Exception:  # noqa: BLE001
                    pass
            yakalanan.append(kayit)

        def yanit_izle(yanit):
            if "admin-ajax.php" not in yanit.url:
                return
            try:
                metin = yanit.text()
            except Exception:  # noqa: BLE001
                return
            if len(metin) > 200:
                (CIKTI / f"{ad}-ajax-yanit.html.gz").write_bytes(
                    gzip.compress(metin.encode("utf-8", "replace")))
                rapor["yanit_boyut"] = len(metin)

        s.on("request", istek_izle)
        s.on("response", yanit_izle)

        s.goto(ayar["url"], wait_until="networkidle", timeout=60000)
        s.wait_for_timeout(2500)

        # Sayfadaki ilk gerçek seçiciyi bul ve ikinci seçeneği seç
        secildi = False
        for sec in ayar["secici"].split(","):
            sec = sec.strip()
            try:
                el = s.query_selector(sec)
                if not el:
                    continue
                secenekler = s.eval_on_selector_all(
                    f"{sec} option",
                    "els => els.map(e => e.value).filter(v => v && v !== '0')")
                if not secenekler:
                    continue
                s.select_option(sec, value=secenekler[0])
                secildi = True
                rapor["secilen"] = secenekler[0]
                break
            except Exception:  # noqa: BLE001
                continue

        rapor["secim_yapildi"] = secildi
        s.wait_for_timeout(4000)

        # Sonuç sayfada olabilir; kaydet
        icerik = s.content()
        (CIKTI / f"{ad}-secim-sonrasi.html.gz").write_bytes(
            gzip.compress(icerik.encode("utf-8", "replace")))
        rapor["sayfa_boyut"] = len(icerik)
        rapor["istekler"] = yakalanan[:12]

        ctx.close()
        t.close()
    return rapor


def main() -> None:
    istenen = [a for a in sys.argv[1:] if not a.startswith("-")] or list(HEDEF)
    hepsi = {}
    for ad in istenen:
        if ad not in HEDEF:
            continue
        print(f"=== {ad} ===")
        try:
            hepsi[ad] = dinle(ad, HEDEF[ad])
        except Exception as e:  # noqa: BLE001
            hepsi[ad] = {"hata": f"{type(e).__name__}: {e}"[:200]}
        print(json.dumps(hepsi[ad], ensure_ascii=False, indent=1)[:900])

    CIKTI.mkdir(exist_ok=True)
    (CIKTI / "ajax-dinleme.json").write_text(
        json.dumps(hepsi, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
