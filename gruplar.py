#!/usr/bin/env python3
"""Markaları paralel tarama için gruplara böler.

Yavaş markaları (tarayıcı modu, il döngüsü) gruplara dengeli dağıtır ki
bir grup diğerlerinden çok uzun sürmesin.

    python gruplar.py 10              → grup sayısını yazdırır
    python gruplar.py 10 --grup 3     → 3. grubun markalarını satır satır yazar

Marka adları satır satır veriliyor; JSON içinde tırnakla taşımak iş akışında
bozuluyordu ("Meka Motor" gibi boşluklu adlar parçalanıyordu).
"""
import sys

from bayiradar.collect import kaynaklari_coz, load_config


def agirlik(cfg):
    """Bu marka kabaca ne kadar sürer?"""
    p = 0
    for k in kaynaklari_coz(cfg):
        p += 20 if k.get("iterate") else 1        # il döngüsü ağır
    return p * (6 if cfg.get("mode") == "browser" else 1)


def bol(sayi):
    c = load_config()["markalar"]
    sirali = sorted(c.items(), key=lambda kv: -agirlik(kv[1]))
    kovalar = [[] for _ in range(sayi)]
    yuk = [0] * sayi
    for ad, cfg in sirali:
        i = yuk.index(min(yuk))
        kovalar[i].append(ad)
        yuk[i] += agirlik(cfg)
    return kovalar


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    kovalar = bol(n)
    if "--grup" in sys.argv:
        i = int(sys.argv[sys.argv.index("--grup") + 1])
        for m in kovalar[i]:
            print(m)
    else:
        print(n)
