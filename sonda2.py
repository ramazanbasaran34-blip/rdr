#!/usr/bin/env python3
"""İki soruyu yanıtlar:

1. MJ'nin ajax.php'si GET kabul ediyor mu? Ediyorsa brands.yaml'in mevcut
   `iterate` mekanizmasına doğrudan oturur, POST desteği yazmaya gerek kalmaz.
2. Yamaha'nın bayi listesi hangi uçtan geliyor? Sayfa React; veri bir API'den
   çekiliyor, o API'yi bulmamız lazım.
"""

from __future__ import annotations

import gzip
import json
import re
from pathlib import Path
from urllib.parse import quote

import requests

CIKTI = Path("ham")
BASLIK = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "*/*",
    "Accept-Language": "tr-TR,tr;q=0.9",
}
TEL = re.compile(r"0\s*\(?\d{3}\)?[\s\-/]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}")


def mj_get_testi() -> dict:
    """ajax.php GET ile de veri veriyor mu?"""
    o = requests.Session()
    o.headers.update({**BASLIK, "X-Requested-With": "XMLHttpRequest"})
    sonuc = {}
    for ad, taban in [("rks", "https://www.rksmotor.com.tr/ajax.php"),
                      ("kuba", "https://www.kubamotor.com.tr/ajax.php")]:
        b = {}
        p = {"action": "states", "city": "Ankara", "state": "0", "category": "Bayi"}
        try:
            g = o.get(taban, params=p, timeout=45)
            b["GET_kod"] = g.status_code
            b["GET_boyut"] = len(g.text)
            b["GET_tel"] = len(TEL.findall(g.text))
            b["GET_kayit"] = g.text.count("result-item")
        except Exception as e:  # noqa: BLE001
            b["GET_hata"] = str(e)[:120]
        try:
            po = o.post(taban, data=p, timeout=45)
            b["POST_kayit"] = po.text.count("result-item")
        except Exception as e:  # noqa: BLE001
            b["POST_hata"] = str(e)[:120]
        sonuc[ad] = b
    return sonuc


def yamaha_sonda() -> dict:
    """Yamaha bayi API'sini arar."""
    o = requests.Session()
    o.headers.update(BASLIK)
    b = {}

    # AEM model json — sayfanın yapılandırması, API adresini içerebilir
    for ad, u in [
        ("model", "https://www.yamaha-motor.eu/tr/tr/dealer-locator.model.json"),
        ("model_kok", "https://www.yamaha-motor.eu/tr/tr.model.json"),
    ]:
        try:
            r = o.get(u, timeout=45)
            b[f"{ad}_kod"] = r.status_code
            b[f"{ad}_boyut"] = len(r.text)
            CIKTI.mkdir(exist_ok=True)
            (CIKTI / f"yamaha-{ad}.json.gz").write_bytes(
                gzip.compress(r.text.encode("utf-8", "replace")))
            # içindeki api/servis benzeri adresleri çıkar
            b[f"{ad}_uclar"] = sorted(set(re.findall(
                r'"(https?://[^"]*(?:api|dealer|service|locator)[^"]*)"', r.text)))[:12]
        except Exception as e:  # noqa: BLE001
            b[f"{ad}_hata"] = str(e)[:120]

    # Sayfanın kendi HTML'i — gömülü yapılandırma olabilir
    try:
        r = o.get("https://www.yamaha-motor.eu/tr/tr/dealer-locator/", timeout=45)
        b["sayfa_kod"] = r.status_code
        b["sayfa_boyut"] = len(r.text)
        CIKTI.mkdir(exist_ok=True)
        (CIKTI / "yamaha-sayfa.html.gz").write_bytes(
            gzip.compress(r.text.encode("utf-8", "replace")))
        b["sayfa_uclar"] = sorted(set(re.findall(
            r'["\'](https?://[^"\']*(?:api|dealer)[^"\']*)["\']', r.text)))[:15]
        b["sayfa_tel"] = len(TEL.findall(r.text))
    except Exception as e:  # noqa: BLE001
        b["sayfa_hata"] = str(e)[:120]

    # React yükleyicisi küçük; asıl kod webpack parçalarında. Yükleyiciden
    # parça adlarını çıkar, her parçayı indir, bayi API'sini içlerinde ara.
    kok = "https://www.yamaha-motor.eu/etc.clientlibs/yme/clientlibs/"
    js = kok + "clientlib-react.lc-303abadbd343bffdb2b08d014fadf94e-lc.min.js"
    KALIPLAR = (
        r"""[\"'`]((?:https?:)?/[\w./-]*(?:dealer|locator)[\w./-]*)[\"'`]""",
        r"""[\"'`](/services/[\w./-]+)[\"'`]""",
        r"""[\"'`](/bin/[\w./-]+)[\"'`]""",
        r"""[\"'`](/api/[\w./-]+)[\"'`]""",
    )
    try:
        r = o.get(js, timeout=60)
        b["js_kod"] = r.status_code
        metin = r.text
        parcalar = sorted(set(re.findall(r"[\w.-]+\.js", metin)))
        b["parca_sayisi"] = len(parcalar)

        bulunan, tarandi = set(), 0
        for pr in parcalar:
            for taban in (kok + "clientlib-react/resources/", kok):
                try:
                    c = o.get(taban + pr, timeout=45)
                except Exception:  # noqa: BLE001
                    continue
                if c.status_code != 200 or len(c.text) < 500:
                    continue
                tarandi += 1
                for kal in KALIPLAR:
                    bulunan |= set(re.findall(kal, c.text, re.I))
                break
        b["parca_tarandi"] = tarandi
        b["js_uclar"] = sorted(bulunan)[:40]
    except Exception as e:  # noqa: BLE001
        b["js_hata"] = str(e)[:150]

    return b


def main() -> None:
    ozet = {"mj_get": mj_get_testi(), "yamaha": yamaha_sonda()}
    CIKTI.mkdir(exist_ok=True)
    (CIKTI / "sonda2.json").write_text(
        json.dumps(ozet, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(ozet, ensure_ascii=False, indent=1)[:4000])


if __name__ == "__main__":
    main()
