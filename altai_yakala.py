#!/usr/bin/env python3
"""Altai — ASP.NET postback yaparak örnek il sayfası yakalar.

Altai'de il seçimi URL'e yansımıyor; `__doPostBack` ile forma POST
atılıyor. Bu yüzden düz GET ile alınan sayfada HİÇ kayıt yok — ozel_test
0 kayıt göstermesinin sebebi buydu, ayrıştırıcı hatası değil.

Bu betik gerçek postback'i yapıp yanıtı kaydediyor; böylece ayrıştırıcıyı
ağa çıkmadan geliştirebiliyoruz.

    python altai_yakala.py              # birkaç örnek il
    python altai_yakala.py --hepsi      # tüm iller
"""

from __future__ import annotations

import gzip
import json
import sys
import time
from pathlib import Path

import requests

from ozel import altai

CIKTI = Path("ham")
ORNEK = ("Ankara", "İstanbul (Avrupa)", "İzmir")

BASLIK = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Content-Type": "application/x-www-form-urlencoded",
}


def main() -> None:
    hepsi = "--hepsi" in sys.argv
    CIKTI.mkdir(exist_ok=True)
    rapor: dict = {}

    for rol, url in altai.KAYNAKLAR.items():
        o = requests.Session()
        o.headers.update(BASLIK)
        try:
            ilk = o.get(url, timeout=45)
            ilk.raise_for_status()
        except Exception as e:  # noqa: BLE001
            rapor[rol] = {"hata": f"{type(e).__name__}: {e}"[:150]}
            print(f"  ✗ {rol}: {rapor[rol]['hata']}")
            continue

        iller = altai.il_secenekleri(ilk.text)
        rapor[rol] = {"il_sayisi": len(iller), "iller": {}}
        print(f"  {rol}: {len(iller)} il listeleniyor")

        hedefler = iller if hepsi else [x for x in iller if x[1] in ORNEK]
        sayfa = ilk.text

        for deger, ad in hedefler:
            govde = altai.post_govdesi(sayfa, deger)
            try:
                y = o.post(url, data=govde, timeout=60,
                           headers={"Referer": url})
                y.raise_for_status()
            except Exception as e:  # noqa: BLE001
                print(f"    ✗ {ad}: {str(e)[:60]}")
                continue

            # Sunucu her yanıtta YENİ ViewState üretiyor; sıradaki
            # istek bunu kullanmalı, yoksa "geçersiz durum" hatası gelir.
            sayfa = y.text

            tel = len(altai.TEL.findall(y.text))
            guvenli = ad.replace(" ", "_").replace("(", "").replace(")", "")
            (CIKTI / f"altai-{rol}-{guvenli}.html.gz").write_bytes(
                gzip.compress(y.text.encode("utf-8", "replace")))
            print(f"    {ad}: {len(y.text)//1024}KB tel={tel}")
            rapor[rol]["iller"][ad] = tel
            time.sleep(0.6)

    (CIKTI / "altai-yakalama.json").write_text(
        json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rapor, ensure_ascii=False, indent=1)[:700])


if __name__ == "__main__":
    main()
