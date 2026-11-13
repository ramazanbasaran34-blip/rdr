#!/usr/bin/env python3
"""ASP.NET WebForms postback gerektiren markaları yakalar.

Altai gibi siteler il seçimini URL'e yansıtmıyor; `__doPostBack` ile
formu POST ediyor. Düz GET işe yaramaz, ViewState taşımak şart.

Sunucu her yanıtta YENİ ViewState üretiyor, o yüzden zincir hâlinde
ilerleniyor: her POST'un yanıtından bir sonrakinin gizli alanları
okunuyor.

    python postback_yakala.py altai            # örnek il (Ankara)
    python postback_yakala.py altai --hepsi    # tüm iller
"""

from __future__ import annotations

import gzip
import importlib
import json
import sys
import time
from pathlib import Path

import requests

CIKTI = Path("ham")

BASLIK = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Content-Type": "application/x-www-form-urlencoded",
}

ORNEK_IL = "Ankara"


def yakala(mod_ad: str, hepsi: bool) -> dict:
    mod = importlib.import_module(f"ozel.{mod_ad}")
    CIKTI.mkdir(exist_ok=True)
    rapor: dict = {}

    for rol, url in mod.KAYNAKLAR.items():
        o = requests.Session()
        o.headers.update(BASLIK)
        try:
            ilk = o.get(url, timeout=45)
            ilk.raise_for_status()
        except Exception as e:  # noqa: BLE001
            rapor[rol] = {"hata": f"{type(e).__name__}: {e}"[:150]}
            continue

        govde = ilk.text
        iller = mod.il_secenekleri(govde)
        rapor[rol] = {"il_sayisi": len(iller), "iller": {}}
        print(f"  {rol}: {len(iller)} il")

        hedefler = iller if hepsi else [x for x in iller
                                        if ORNEK_IL.casefold() in x[1].casefold()][:1]
        if not hedefler and iller:
            hedefler = iller[:1]

        for deger, ad in hedefler:
            try:
                y = o.post(url, data=mod.post_govdesi(govde, deger),
                           timeout=60, headers={"Referer": url})
                y.raise_for_status()
            except Exception as e:  # noqa: BLE001
                print(f"    ✗ {ad}: {str(e)[:60]}")
                continue

            # Zincir: bir sonraki isteğin ViewState'i bu yanıttan gelmeli
            govde = y.text
            dosya = f"{mod_ad}-{rol}-{deger}.html.gz"
            (CIKTI / dosya).write_bytes(gzip.compress(govde.encode("utf-8", "replace")))
            n = len(mod.coz(rol, govde, url, il=ad))
            print(f"    {ad} ({deger}): {len(govde)//1024}KB → {n} kayıt", flush=True)
            rapor[rol]["iller"][ad] = n
            time.sleep(0.8)

    (CIKTI / f"{mod_ad}-postback.json").write_text(
        json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")
    return rapor


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    hepsi = "--hepsi" in sys.argv
    for mod_ad in (args or ["altai"]):
        print(f"=== {mod_ad.upper()} ===")
        r = yakala(mod_ad, hepsi)
        print(json.dumps(r, ensure_ascii=False, indent=1)[:800])


if __name__ == "__main__":
    main()
