#!/usr/bin/env python3
"""elle/ klasöründeki hazır veri dosyalarını veritabanına işler.

NEDEN VAR
Bazı markaların siteleri Cloudflare korumalı ve GitHub Actions'ın veri
merkezi IP'lerinden 403 dönüyor. Tarayıcı taklidi, gerçek Chrome, sanal
ekran, insan gibi gezinme — hepsi denendi, sorun tarayıcı değil IP
itibarı. Bu markaların verisi sitenin KENDİ resmi sayfalarından alınıp
elle/<marka>.json dosyasına yazılıyor.

Dosya biçimi:
    {
      "_aciklama": "...",           # neden elle girildiği
      "_kaynak": ["https://..."],   # alındığı resmi adresler
      "_tarih": "2026-09-01",
      "kayitlar": [
        {"marka": "Ducati", "rol": "satis", "bayi_adi": "...",
         "il": "...", "ilce": "...", "adres": "...", "telefon": "...",
         "email": "...", "website": ""}
      ]
    }

Kayıtlar normal tarama gibi finalize()'dan geçiyor ve commit_tarama ile
işleniyor; yani rol birleştirme, il/ilçe doğrulama, veri koruma hepsi
aynı şekilde çalışıyor.

    python elle_tara.py            # hepsi
    python elle_tara.py korlas     # seçili
    python elle_tara.py --kuru     # veritabanına yazmadan
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

from bayiradar.parse import finalize
from bayiradar.store import commit_tarama, db, now

KLASOR = Path("elle")


def dosyayi_oku(yol: Path) -> tuple[dict[str, list[dict]], str]:
    veri = json.loads(yol.read_text(encoding="utf-8"))
    kaynaklar = veri.get("_kaynak") or []
    kaynak_url = kaynaklar[0] if kaynaklar else ""

    marka_kayit: dict[str, list[dict]] = defaultdict(list)
    for ham in veri.get("kayitlar", []):
        marka = ham.get("marka")
        if not marka:
            continue
        r = {k: v for k, v in ham.items() if k != "marka"}
        k = finalize(r, marka, kaynak_url, {})
        if k:
            marka_kayit[marka].append(k)
    return marka_kayit, kaynak_url


def main() -> None:
    kuru = "--kuru" in sys.argv
    istenen = [a.lower() for a in sys.argv[1:] if not a.startswith("-")]

    dosyalar = sorted(KLASOR.glob("*.json"))
    if istenen:
        dosyalar = [d for d in dosyalar if d.stem.lower() in istenen]
    if not dosyalar:
        print("elle/ altında işlenecek dosya yok")
        return

    basladi = now()
    rapor: dict = {}
    for yol in dosyalar:
        marka_kayit, kaynak = dosyayi_oku(yol)
        print(f"\n=== {yol.name}  ({kaynak})")
        for marka, kayitlar in sorted(marka_kayit.items()):
            iller = len({k["il"] for k in kayitlar if k.get("il")})
            print(f"  {marka:10} {len(kayitlar):4} kayıt, {iller} il")
            rapor[marka] = {"kayit": len(kayitlar), "il": iller,
                            "kaynak": kaynak}
            if kuru:
                continue
            with db() as con:
                sonuc = commit_tarama(con, marka, kayitlar, 1.0, basladi)
            rapor[marka]["db"] = str(sonuc)[:200]
            print(f"             db: {rapor[marka]['db']}")

    if kuru:
        print("\n(kuru çalışma — veritabanına yazılmadı)")
    Path("ham").mkdir(exist_ok=True)
    Path("ham/elle-tarama.json").write_text(
        json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
