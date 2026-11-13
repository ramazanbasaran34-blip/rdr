#!/usr/bin/env python3
"""Her fiziksel firmaya 4 haneli cari kod verir.

FİRMA NEDİR
Bir firma birden çok markanın bayisi olabiliyor (rekor: 14 marka).
Veritabanında her marka×nokta ayrı satır, ama fiziksel firma tek.
Aynı TELEFON + aynı İLÇE = aynı firma kabul ediliyor. Şube başka
ilçedeyse ayrı firma sayılıyor.

Ada göre eşleştirmiyoruz: 1817 firmada aynı numara farklı adla
yazılmış ("YUSUF BAĞCI" / "BAĞCI MOTOR (SEYHAN ŞB.)", ticari unvan
karşısında tabela adı). Ad güvenilmez, telefon güvenilir.

KOD BİÇİMİ
4 karakter, büyük harf + rakam (örn. "K7M2"). Karıştırılabilen
karakterler (0/O, 1/I, 5/S) alfabeden çıkarıldı.

KODLAR SABİT KALIR
Üretilen eşleme cari_kodlar.json'da saklanıyor. Betik tekrar
çalıştığında var olan firmalar kodunu korur, yalnızca yeni firmalara
kod verilir. Böylece bir bayinin kodu zamanla değişmez.

    python cari_kod.py            # eksik kodları tamamla
    python cari_kod.py --rapor    # sadece durum
"""

from __future__ import annotations

import json
import random
import sqlite3
import sys
from pathlib import Path

from ozel.tr import anahtar

DOSYA = Path("cari_kodlar.json")
DB = "bayiler.db"

# 0/O, 1/I, 5/S karışmasın diye çıkarıldı
ALFABE = "ABCDEFGHJKLMNPQRTUVWXYZ2346789"


def firma_anahtari(tel: str, il: str, ilce: str, ad: str) -> str:
    t = "".join(c for c in (tel or "") if c.isdigit())
    t = t[-10:] if len(t) >= 10 else ""
    if t:
        return f"T:{t}|{anahtar(il)}|{anahtar(ilce)}"
    # Telefonsuz kayıtlar (67 firma) ada göre ayrılıyor
    return f"A:{anahtar(ad)}|{anahtar(il)}|{anahtar(ilce)}"


def _kod_uret(rnd: random.Random) -> str:
    return "".join(rnd.choice(ALFABE) for _ in range(4))


def main() -> None:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute(
        "SELECT bayi_adi, il, ilce, telefon FROM bayiler WHERE durum!='kapali'")]
    con.close()

    anahtarlar = {firma_anahtari(r["telefon"], r["il"], r["ilce"], r["bayi_adi"])
                  for r in rows}

    eslesme: dict[str, str] = {}
    if DOSYA.exists():
        eslesme = json.loads(DOSYA.read_text(encoding="utf-8"))

    kullanilan = set(eslesme.values())
    eksik = sorted(anahtarlar - set(eslesme))

    if "--rapor" in sys.argv:
        print(f"firma: {len(anahtarlar)} | kodlu: {len(anahtarlar) - len(eksik)} "
              f"| kodsuz: {len(eksik)}")
        return

    # Sabit tohum: aynı veriyle aynı kodlar
    rnd = random.Random(20260901)
    kapasite = len(ALFABE) ** 4
    if len(anahtarlar) > kapasite * 0.6:
        print(f"UYARI: {len(anahtarlar)} firma, 4 haneli kod kapasitesi "
              f"{kapasite}. Çakışma denemeleri artabilir.")

    for a in eksik:
        for _ in range(10000):
            k = _kod_uret(rnd)
            if k not in kullanilan:
                kullanilan.add(k)
                eslesme[a] = k
                break
        else:
            raise SystemExit("kod havuzu tükendi")

    # Artık kullanılmayan firmaların kodunu SİLMİYORUZ: bayi geri
    # gelirse eski kodunu alsın.
    DOSYA.write_text(json.dumps(eslesme, ensure_ascii=False, indent=0,
                                sort_keys=True), encoding="utf-8")
    print(f"firma: {len(anahtarlar)} | yeni kod: {len(eksik)} "
          f"| dosyadaki toplam: {len(eslesme)}")


if __name__ == "__main__":
    main()
