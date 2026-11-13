#!/usr/bin/env python3
"""ozel/ altındaki marka toplayıcılarını KAYDEDİLMİŞ sayfalarla dener.

Ağa çıkmaz, saniyeler sürer. Amaç: taramadan önce her markanın kodunun
gerçekten çalıştığını görmek. Site yapısı değişirse tarama başlamadan
burada patlar.

    python ozel_test.py            # hepsi
    python ozel_test.py falcon     # tek modül
"""

from __future__ import annotations

import gzip
import importlib
import json
import sys
from pathlib import Path

from bayiradar.parse import finalize

HAM = Path("ham")

MODULLER = ["falcon", "kral", "vespa", "suzuki", "zelsun",
            "musatti", "csn", "motolux", "isotlar", "nanok", "meka"]

# Marka başına beklenen en az kayıt (saha bilgisi / sayfadaki gerçek sayı)
EN_AZ = {"Falcon": 900, "Kral": 300, "Vespa": 60, "Suzuki": 70,
         "Zelsun": 2, "Musatti": 5, "CSN": 3, "Motolux": 5,
         "Peugeot": 20, "Horwin": 5, "Lambretta": 5,
         "Nanok": 100, "Meka Motor": 100}


def dosya_oku(ad: str, kodlama: str = "utf-8") -> str:
    return gzip.decompress((HAM / f"{ad}.gz").read_bytes()).decode(kodlama, "replace")


def dene(mod_ad: str) -> tuple[int, dict]:
    mod = importlib.import_module(f"ozel.{mod_ad}")
    hata = 0
    toplam: dict[str, list[dict]] = {}

    for (marka, rol), dosya in mod.TEST.items():
        yol = HAM / f"{dosya}.gz"
        if not yol.exists():
            print(f"  · {marka}/{rol}: {dosya} yok, atlandı")
            continue

        govde = dosya_oku(dosya, getattr(mod, "KODLAMA", "utf-8"))
        url = mod.KAYNAKLAR.get(rol, "")
        try:
            ek = {}
            if "il" in mod.coz.__code__.co_varnames[:mod.coz.__code__.co_argcount]:
                ek["il"] = getattr(mod, "TEST_IL", None)
            ham = mod.coz(rol, govde, url, **ek)
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ {marka}/{rol}: {type(e).__name__}: {e}")
            hata += 1
            continue

        cfg = {"il_ilce_birlesik": "konum"} if any("konum" in r for r in ham[:1]) else {}
        kayitlar = []
        for r in ham:
            k = finalize(dict(r), marka, url, cfg)
            if k:
                kayitlar.append(k)
        toplam.setdefault(marka, []).extend(kayitlar)

        ilsiz = sum(1 for x in kayitlar if not x.get("il"))
        telsiz = sum(1 for x in kayitlar if not x.get("telefon"))
        print(f"  {marka:10} {rol:7} ham={len(ham):5} geçerli={len(kayitlar):5} "
              f"(ilsiz {ilsiz}, telefonsuz {telsiz})")
        for x in kayitlar[:2]:
            print(f"        {x['bayi_adi'][:30]:30} | {x.get('il')} / "
                  f"{x.get('ilce')} | {x.get('telefon')} | {x.get('rol')}")
        if ilsiz and rol != "hepsi":
            print("        ✗ ilsiz kayıt var")
            hata += 1

    for marka, k in toplam.items():
        az = EN_AZ.get(marka, 1)
        iller = len({x.get("il") for x in k if x.get("il")})
        print(f"  → {marka}: {len(k)} kayıt, {iller} il")
        if len(k) < az:
            print(f"        ✗ beklenen en az {az}")
            hata += 1
    return hata, toplam


def main() -> None:
    istenen = [a for a in sys.argv[1:] if not a.startswith("-")]
    moduller = istenen or MODULLER
    hata = 0
    for m in moduller:
        print(f"\n=== {m.upper()} ===")
        try:
            h, _ = dene(m)
        except ModuleNotFoundError:
            print(f"  · ozel/{m}.py yok, atlandı")
            continue
        hata += h
    print("\n✓ hepsi geçti" if not hata else f"\n✗ {hata} sorun")
    sys.exit(1 if hata else 0)


if __name__ == "__main__":
    main()
