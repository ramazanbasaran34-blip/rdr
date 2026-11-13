#!/usr/bin/env python3
"""Altai ve Regal Raptor için ASP.NET postback akışını canlı dener.

Bu iki markanın modülü yazılmış ama ozel_tara.py'nin gezinme tablosuna
eklenmediği için hiç çalıştırılmamış. Burada gerçek istekle doğruluyoruz:

  1. Sayfayı GET et, gizli alanları (ViewState) oku
  2. Bir il için POST at
  3. Dönen HTML'den kaç kayıt çıktığını raporla

Tarayıcı yok; oturumlu düz istek yeterli. Birkaç saniye sürer.

    python aspnet_sonda.py
"""

from __future__ import annotations

import gzip
import importlib
import json
import sys
from pathlib import Path

import requests

from bayiradar.parse import finalize

CIKTI = Path("ham")

BASLIK = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Content-Type": "application/x-www-form-urlencoded",
}

# modül -> denenecek il adı
DENEME = {"altai": "Ankara", "regal": "Ankara"}


def sonda(mod_ad: str, il_adi: str) -> dict:
    mod = importlib.import_module(f"ozel.{mod_ad}")
    rapor: dict = {"marka": getattr(mod, "MARKA", mod_ad)}

    for rol, url in mod.KAYNAKLAR.items():
        o = requests.Session()
        o.headers.update(BASLIK)
        try:
            ilk = o.get(url, timeout=45)
            ilk.raise_for_status()
        except Exception as e:  # noqa: BLE001
            rapor[rol] = {"hata": f"GET: {type(e).__name__}: {e}"[:140]}
            continue

        secenekler = mod.il_secenekleri(ilk.text)
        gizli = mod.gizli_alanlar(ilk.text)
        bilgi = {
            "il_sayisi": len(secenekler),
            "viewstate": bool(gizli.get("__VIEWSTATE")),
            "ornek": secenekler[:3],
        }

        hedef = next((d for d, ad in secenekler
                      if ad.casefold().startswith(il_adi.casefold())), None)
        if hedef is None and secenekler:
            hedef = secenekler[0][0]
            il_adi = secenekler[0][1]

        if hedef is None:
            bilgi["hata"] = "il seçeneği bulunamadı"
            rapor[rol] = bilgi
            continue

        try:
            y = o.post(url, data=mod.post_govdesi(ilk.text, hedef), timeout=60)
            y.raise_for_status()
        except Exception as e:  # noqa: BLE001
            bilgi["hata"] = f"POST: {type(e).__name__}: {e}"[:140]
            rapor[rol] = bilgi
            continue

        bilgi["yanit_boyut"] = len(y.text)
        ham = mod.coz(rol, y.text, url, il=il_adi)
        kayitlar = [finalize(dict(x), rapor["marka"], url, {}) for x in ham]
        kayitlar = [x for x in kayitlar if x]
        bilgi["ham"] = len(ham)
        bilgi["gecerli"] = len(kayitlar)
        bilgi["ornek_kayit"] = [
            f"{x['bayi_adi'][:28]} | {x.get('il')}/{x.get('ilce')} | {x.get('telefon')}"
            for x in kayitlar[:3]]

        CIKTI.mkdir(exist_ok=True)
        (CIKTI / f"{mod_ad}-{rol}-post.html.gz").write_bytes(
            gzip.compress(y.text.encode("utf-8", "replace")))
        rapor[rol] = bilgi
    return rapor


def main() -> None:
    istenen = [a for a in sys.argv[1:] if not a.startswith("-")]
    hedefler = {k: v for k, v in DENEME.items() if not istenen or k in istenen}
    ozet = {ad: sonda(ad, il) for ad, il in hedefler.items()}
    CIKTI.mkdir(exist_ok=True)
    (CIKTI / "aspnet-sonda.json").write_text(
        json.dumps(ozet, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(ozet, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
