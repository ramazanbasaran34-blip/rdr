#!/usr/bin/env python3
"""Yamaha bayi ağını resmi GraphQL ucundan çeker.

Bayi bulucu React uygulaması, şu uca POST atıyor:
    https://www.yamaha-motor.eu/services/api/dealers
    query GetDealersByCountry(country: "tr")

Tarayıcı gerekmiyor, harita tıklamaya da gerek yok — uç ülkenin tamamını
tek yanıtta veriyor. Sayfalama (limit/offset) destekleniyor; burada offset
artırarak sonuna kadar okuyoruz, tek sayfada bittiğini varsaymıyoruz.

Rol: DEVAM.md'deki kurala göre Yamaha'da satış/servis ayrımı yok, tüm
kayıtlar satis_servis. Yine de serviceIds okunuyor: MCSER (servis) ve
MC (motosiklet satış) kodları raporlanıyor ki ileride ayrım istenirse hazır olsun.

    python yamaha_tara.py           # veritabanına işler
    python yamaha_tara.py --kuru    # sadece rapor
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import requests

from bayiradar.parse import finalize
from bayiradar.store import commit_tarama, db, now

UC = "https://www.yamaha-motor.eu/services/api/dealers"
SAYFA = "https://www.yamaha-motor.eu/tr/tr/dealer-locator/?category=MCM"
MARKA = "Yamaha"

SORGU = """
query GetDealersByCountry($country: String!, $limit: Int, $offset: Int) {
  GetDealersByCountry(country: $country, limit: $limit, offset: $offset) {
    vicinityId
    name
    country
    city
    addressLines
    zipCode
    telephoneNumbers
    email
    websites
    latitude
    longitude
    serviceIds
  }
}
"""

BASLIK = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Origin": "https://www.yamaha-motor.eu",
    "Referer": SAYFA,
}


def sayfa_cek(oturum: requests.Session, offset: int, limit: int = 200) -> list[dict]:
    y = oturum.post(UC, timeout=60, data=json.dumps({
        "query": SORGU,
        "variables": {"country": "tr", "limit": limit, "offset": offset},
    }))
    y.raise_for_status()
    d = y.json()
    if d.get("errors"):
        raise RuntimeError(str(d["errors"])[:200])
    return d.get("data", {}).get("GetDealersByCountry") or []


def hepsini_cek(log=print) -> list[dict]:
    """Sonuç bitene kadar offset ilerletir. Tek sayfa varsayımı yapmıyoruz."""
    oturum = requests.Session()
    oturum.headers.update(BASLIK)

    ham: list[dict] = []
    gorulen: set[str] = set()
    offset = 0
    while True:
        parca = sayfa_cek(oturum, offset)
        if not parca:
            break
        yeni = [x for x in parca if x.get("vicinityId") not in gorulen]
        for x in yeni:
            gorulen.add(x.get("vicinityId"))
        ham.extend(yeni)
        log(f"  offset={offset} → {len(parca)} geldi, {len(yeni)} yeni "
            f"(toplam {len(ham)})")
        if len(yeni) == 0 or len(parca) < 200:
            break
        offset += len(parca)
        time.sleep(0.3)
    return ham


def _adres(d: dict) -> str:
    satir = [s.strip() for s in (d.get("addressLines") or []) if s and s.strip()]
    posta = (d.get("zipCode") or "").strip()
    sehir = (d.get("city") or "").strip()
    parcalar = satir + ([posta] if posta else []) + ([sehir] if sehir else [])
    return " ".join(parcalar)


def _telefon(d: dict) -> str:
    for t in d.get("telephoneNumbers") or []:
        t = (t or "").strip()
        if t:
            return t
    return ""


def cevir(ham: list[dict]) -> list[dict]:
    cfg: dict = {}
    out = []
    for d in ham:
        ad = re.sub(r"\s+", " ", (d.get("name") or "")).strip()
        rec = {
            "bayi_adi": ad,
            "il": (d.get("city") or "").strip(),
            "ilce": "",
            "adres": _adres(d),
            "telefon": _telefon(d),
            "email": (d.get("email") or "").strip(),
            "website": next(iter(d.get("websites") or []), ""),
            # Honda ve Yamaha'da satış/servis ayrımı yok (kullanıcı kuralı).
            "rol": "satis_servis",
        }
        k = finalize(rec, MARKA, SAYFA, cfg)
        if k:
            out.append(k)
    return out


def main() -> None:
    kuru = "--kuru" in sys.argv
    basladi = now()

    ham = hepsini_cek()
    kayitlar = cevir(ham)

    iller = sorted({k.get("il", "") for k in kayitlar if k.get("il")})
    rapor = {
        "ham": len(ham),
        "kayit": len(kayitlar),
        "il": len(iller),
        "ilsiz": sum(1 for k in kayitlar if not k.get("il")),
        "ilcesiz": sum(1 for k in kayitlar if not k.get("ilce")),
        "telefonsuz": sum(1 for k in kayitlar if not k.get("telefon")),
    }
    print(json.dumps(rapor, ensure_ascii=False, indent=1))

    if kuru:
        print("(kuru çalışma — veritabanına yazılmadı)")
    else:
        with db() as con:
            sonuc = commit_tarama(con, MARKA, kayitlar, 1.0, basladi)
        rapor["db"] = str(sonuc)[:200]
        print("db:", rapor["db"])

    Path("ham").mkdir(exist_ok=True)
    Path("ham/yamaha-tarama.json").write_text(
        json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
