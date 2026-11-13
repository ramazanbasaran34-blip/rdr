#!/usr/bin/env python3
"""Kuba ve RKS'in bayi/servis ağını ajax.php üzerinden toplar.

Neden ayrı betik: bu iki marka brands.yaml'in GET tabanlı kaynak modeline
oturmuyor. Sayfadaki üçlü seçim (kategori → il → ilçe → ARA) arka planda
şuraya POST atıyor:

    POST /ajax.php  {action: states, city: <il>, state: 0, category: Bayi|Servis}

Üç kritik ayrıntı:

  1. İlçe listesinde "Tüm İlçeler" seçeneğinin değeri 0. Yani il başına TEK
     istek yeter — 973 ilçeyi dolaşmaya gerek yok. 81 il × 2 kategori = 162
     istek, birkaç dakika.

  2. Sayfada <base href="https://.../"> var. Göreli "ajax.php" alt dizine
     DEĞİL, site köküne çözülüyor. Alt dizinde denenirse 404 alınır.

  3. Uç markayı ayırmıyor: Kuba, RKS, Skyjet, Benelli, Ape Ryder, Segway,
     Zontes hepsi aynı listede geliyor. Ayrım her kaydın "Yetkileri"
     satırında yazıyor ("Kuba Motor Bayisi" / "RKS Motor Bayisi"), süzme
     oradan yapılıyor.

Sonuç doğrudan bayiler.db'ye işlenir; store.commit_tarama kullanıldığı için
veri koruma, anomali karantinası ve rol birleştirme aynen geçerli.

    python mj_tara.py            # ikisi de
    python mj_tara.py Kuba       # tek marka
    python mj_tara.py --kuru     # veritabanına yazmadan, sadece rapor
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import requests

from bayiradar.parse import finalize, kayit_suzgeci, parse_html
from bayiradar.store import commit_tarama, db, now

BASLIK = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "*/*",
}

# Sayfadan gelen HTML her iki sitede de aynı kalıpta.
SATIR_TARIFI = {
    "row": "div.result-item",
    "fields": {
        "bayi_adi": "div.location-name h5",
        "adres": {"sel": "div.text-item p", "index": 0},
        "telefon": {"sel": "a[href^='tel:']", "attr": "href",
                    "regex": r"tel:\s*([0-9 ()]+)"},
    },
    "ekstra_alanlar": {
        "yetkiler": {"sel": "div.text-item div:nth-of-type(2) p"},
    },
}

MARKALAR = {
    "Kuba": {
        "sayfa": "https://www.kubamotor.com.tr/bayi-servis/kubamotor",
        "ajax": "https://www.kubamotor.com.tr/ajax.php",
        "icermeli": ["Kuba Motor"],
    },
    "RKS": {
        "sayfa": "https://www.rksmotor.com.tr/bayi-servis/rksmotor.html",
        "ajax": "https://www.rksmotor.com.tr/ajax.php",
        "icermeli": ["RKS Motor"],
    },
}

KATEGORILER = [("Bayi", "satis"), ("Servis", "servis")]


def il_listesi(oturum: requests.Session, sayfa: str) -> list[str]:
    """İl adlarını sayfanın kendi <select>'inden okur.

    Kendi 81 il listemizi kullanmıyoruz: site 'kahramanmaraş' gibi kendi
    yazımını bekliyor, birebir eşleşmezse boş döner.
    """
    y = oturum.get(sayfa, timeout=45)
    y.raise_for_status()
    blok = re.search(r"<select[^>]*id=[\"']city[\"'][^>]*>(.*?)</select>",
                     y.text, re.S | re.I)
    if not blok:
        return []
    iller = re.findall(r"<option[^>]*value=[\"']([^\"']+)[\"']", blok.group(1))
    return [i for i in iller if i.strip() and i.strip() != "0"]


def il_cek(oturum: requests.Session, ajax: str, il: str, kategori: str) -> str:
    """Tek il + kategori için ham HTML. state=0 → 'Tüm İlçeler'."""
    y = oturum.post(ajax, timeout=60, data={
        "action": "states", "city": il, "state": "0", "category": kategori})
    y.raise_for_status()
    return y.text


def marka_tara(marka: str, ayar: dict, log=print) -> tuple[list[dict], float]:
    oturum = requests.Session()
    oturum.headers.update(BASLIK)

    iller = il_listesi(oturum, ayar["sayfa"])
    if not iller:
        raise RuntimeError("il listesi okunamadı — sayfa yapısı değişmiş olabilir")
    log(f"  {len(iller)} il bulundu")

    cfg = {**SATIR_TARIFI,
           "kayit_suzgeci": {"alan": "yetkiler", "icermeli": ayar["icermeli"]}}

    kayitlar: list[dict] = []
    denendi = basarili = 0

    for il in iller:
        for kategori, rol in KATEGORILER:
            denendi += 1
            try:
                govde = il_cek(oturum, ayar["ajax"], il, kategori)
            except Exception as e:  # noqa: BLE001
                log(f"    ✗ {il}/{kategori}: {str(e)[:60]}")
                continue
            basarili += 1
            ham = kayit_suzgeci(parse_html(govde, cfg), cfg)
            for r in ham:
                r["rol"] = rol
                k = finalize(r, marka, ayar["sayfa"], cfg)
                if k:
                    kayitlar.append(k)
            time.sleep(0.3)          # siteyi yormayalım
        log(f"    {il}: toplam {len(kayitlar)}")

    kapsam = basarili / denendi if denendi else 0.0
    return kayitlar, kapsam


def main() -> None:
    arg = [a for a in sys.argv[1:] if not a.startswith("--")]
    kuru = "--kuru" in sys.argv
    secili = {k: v for k, v in MARKALAR.items()
              if not arg or any(a.lower() == k.lower() for a in arg)}

    rapor: dict = {}
    for marka, ayar in secili.items():
        print(f"\n=== {marka} ===")
        basladi = now()
        try:
            kayitlar, kapsam = marka_tara(marka, ayar)
        except Exception as e:  # noqa: BLE001
            print(f"  HATA: {e}")
            rapor[marka] = {"hata": str(e)[:200]}
            continue

        satis = sum(1 for k in kayitlar if k.get("rol") == "satis")
        servis = sum(1 for k in kayitlar if k.get("rol") == "servis")
        iller = len({k.get("il") for k in kayitlar if k.get("il")})
        ilsiz = sum(1 for k in kayitlar if not k.get("il"))
        print(f"  → {len(kayitlar)} kayıt · {satis} satış · {servis} servis "
              f"· {iller} il · ilsiz {ilsiz} · kapsam %{kapsam*100:.0f}")
        rapor[marka] = {"kayit": len(kayitlar), "satis": satis,
                        "servis": servis, "il": iller, "ilsiz": ilsiz,
                        "kapsam": round(kapsam, 3)}

        if kuru:
            print("  (kuru çalışma — veritabanına yazılmadı)")
            continue
        with db() as con:
            sonuc = commit_tarama(con, marka, kayitlar, kapsam, basladi)
        print(f"  veritabanı: {sonuc}")
        rapor[marka]["db"] = str(sonuc)[:200]

    Path("ham").mkdir(exist_ok=True)
    Path("ham/mj-tarama.json").write_text(
        json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
