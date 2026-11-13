#!/usr/bin/env python3
"""MJ platformu (RKS, Kuba) ajax.php ucunu yoklar.

Sayfadaki üçlü seçim aslında şuraya POST atıyor:
    POST ajax.php  {action: states, city: <il>, state: <ilce|0>, category: Bayi|Servis}

'Tüm İlçeler' seçeneğinin değeri 0 — yani il başına TEK istek yeter,
973 ilçeyi dolaşmaya gerek yok. Bu betik önce onu doğruluyor.

    python mj_sonda.py
"""

from __future__ import annotations

import gzip
import json
import re
from pathlib import Path

import requests

CIKTI = Path("ham")

# ad -> (sayfa_url, ajax_url)
# Sayfada <base href="/"> var: göreli "ajax.php" DİZİNE değil KÖKE çözülür.
# DİKKAT: user.rksmotor.com.tr E-Bike ağını veriyor ("RKS E-Bike Bayisi").
# Motosiklet ağı asıl sitenin kendi ajax ucunda; ikisi ayrı veri kümesi.
UCLAR = {
    "rks-ebike": ("https://user.rksmotor.com.tr/services.php",
                  "https://user.rksmotor.com.tr/ajax.php"),
    "rks-moto":  ("https://www.rksmotor.com.tr/bayi-servis/rksmotor.html",
                  "https://www.rksmotor.com.tr/ajax.php"),
    "kuba-moto": ("https://www.kubamotor.com.tr/bayi-servis/kubamotor",
                  "https://www.kubamotor.com.tr/ajax.php"),
}

BASLIK = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "*/*",
}

DENEME_IL = "Ankara"


def sonda(ad: str, uc: tuple[str, str]) -> dict:
    sayfa_url, ajax = uc
    b: dict = {"sayfa": sayfa_url, "ajax": ajax}
    o = requests.Session()
    o.headers.update(BASLIK)

    # 1) Sayfa var mı, il listesi geliyor mu
    try:
        s = o.get(sayfa_url, timeout=45)
        b["sayfa_kod"] = s.status_code
        b["il_sayisi"] = len(re.findall(r"<option value=\"[^\"0][^\"]*\"", s.text))
    except Exception as e:  # noqa: BLE001
        b["hata"] = f"sayfa: {type(e).__name__}: {e}"[:150]
        return b

    # 2) İlçe listesi (action=district)
    try:
        d = o.post(ajax, data={"action": "district", "name": DENEME_IL}, timeout=45)
        b["district_kod"] = d.status_code
        b["district_ornek"] = d.text[:160]
    except Exception as e:  # noqa: BLE001
        b["district_hata"] = str(e)[:120]

    # 3) Asıl veri — "Tüm İlçeler" = 0 ile tek istek
    for kat in ("Bayi", "Servis"):
        try:
            r = o.post(ajax, data={"action": "states", "city": DENEME_IL,
                                   "state": "0", "category": kat}, timeout=60)
            b[f"{kat}_kod"] = r.status_code
            b[f"{kat}_boyut"] = len(r.text)
            b[f"{kat}_tel"] = len(re.findall(
                r"0\s*\(?\d{3}\)?[\s\-/]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}", r.text))
            CIKTI.mkdir(exist_ok=True)
            (CIKTI / f"{ad}-ajax-{kat.lower()}.html.gz").write_bytes(
                gzip.compress(r.text.encode("utf-8", "replace")))
        except Exception as e:  # noqa: BLE001
            b[f"{kat}_hata"] = str(e)[:120]
    return b


def main() -> None:
    ozet = {ad: sonda(ad, uc) for ad, uc in UCLAR.items()}
    CIKTI.mkdir(exist_ok=True)
    (CIKTI / "mj-sonda.json").write_text(
        json.dumps(ozet, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(ozet, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
