#!/usr/bin/env python3
"""Tek bir markayı tarar ve sonucu raporlar.

Akış dosyasının içine gömülü Python blokları kırılgandı: heredoc ile
YAML girintisi birleşince adım sessizce çalışmıyor, sayılar hiç
değişmiyordu. Mantığı buraya taşıdık — hem test edilebilir hem de
hata mesajı Actions ekranında görünür.

    python tek_marka.py "Voge" --db calisma.db

Şişme varsa (kayıt %30'dan fazla arttıysa) 1 ile çıkar; GitHub o
markayı kırmızı gösterir, hangi markanın bozuk olduğu anında belli olur.
"""

from __future__ import annotations

import argparse
import sqlite3
import subprocess
import sys

import yaml


def say(db: str, marka: str) -> int:
    con = sqlite3.connect(db)
    try:
        return con.execute(
            "select count(*) from bayiler where marka=? and durum!='kaldirildi'",
            (marka,)).fetchone()[0]
    finally:
        con.close()


def _cfg(marka: str) -> dict:
    c = yaml.safe_load(open("brands.yaml", encoding="utf-8"))["markalar"]
    return c.get(marka) or {}


def ozel_modul(marka: str) -> str:
    return _cfg(marka).get("ozel") or ""


def ozel_betik(marka: str) -> str:
    """Kendi başına çalışan tarayıcı betiği (ör. yamaha_tara.py)."""
    return _cfg(marka).get("betik") or ""


def elle_dosya(marka: str) -> str:
    """Elle hazırlanmış veri dosyası (Cloudflare korumalı siteler)."""
    c = _cfg(marka)
    return c.get("elle_dosya") or "" if c.get("elle") else ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("marka")
    ap.add_argument("--db", default="bayiler.db")
    ap.add_argument("--sisme", type=float, default=1.30)
    a = ap.parse_args()

    once = say(a.db, a.marka)
    print(f"[{a.marka}] önceki kayıt: {once}", flush=True)

    if (ed := elle_dosya(a.marka)):
        print(f"[{a.marka}] elle veri: elle/{ed}.json", flush=True)
        komut = [sys.executable, "elle_tara.py", ed, "--db", a.db]
    elif (betik := ozel_betik(a.marka)):
        print(f"[{a.marka}] özel betik: {betik}", flush=True)
        komut = [sys.executable, betik, "--db", a.db]
    elif (ozel := ozel_modul(a.marka)):
        print(f"[{a.marka}] özel modül: {ozel}", flush=True)
        komut = [sys.executable, "ozel_tara.py", ozel, "--db", a.db]
    else:
        # DİKKAT: --db alt komuttan ÖNCE gelmeli, sonra değil.
        # "cli.py tara --marka X --db Y" hata veriyordu ve akış
        # sessizce başarısız oluyordu.
        komut = [sys.executable, "cli.py", "--db", a.db,
                 "tara", "--marka", a.marka]

    print(f"[{a.marka}] komut: {' '.join(komut)}", flush=True)
    if subprocess.run(komut).returncode != 0:
        print(f"::error::{a.marka} tarama komutu hata verdi")
        return 1

    sonra = say(a.db, a.marka)
    print(f"[{a.marka}] sonraki kayıt: {sonra}", flush=True)

    # SADECE BU MARKAYI BIRAK.
    # Her iş bayiler.db'nin kopyasıyla başlıyor, yani dosya 62 markanın
    # hepsini içeriyor. Parçalar birleştirilirken aynı kayıtlar 62 kez
    # üst üste biniyordu. Diğer markaları atıyoruz ki her parça yalnızca
    # kendi markasının güncel hâlini taşısın.
    con = sqlite3.connect(a.db)
    try:
        n = con.execute("delete from bayiler where marka<>?", (a.marka,)).rowcount
        con.execute("delete from marka_durum where marka<>?", (a.marka,))
        con.commit()
        con.execute("vacuum")
        print(f"[{a.marka}] parçadan çıkarılan diğer marka kaydı: {n}", flush=True)
    finally:
        con.close()
    print(f"{a.marka}: {once} -> {sonra}")

    # ŞİŞME UYARISI — işi KIRMIYOR.
    #
    # Önce hata veriyordu ve şişen markanın parçası yine yüklenmesine
    # rağmen akış kırmızı görünüyordu; "tarama hatası" ile "şişme"
    # ayırt edilemiyordu. Artık şişme sadece uyarı: iş yeşil kalıyor,
    # sonuç önizlemeye gidiyor, orada inceleyip karar veriyoruz.
    # Canlıya geçişi "Önizlemeyi canlıya al" akışındaki fren engelliyor.
    if once >= 20 and sonra > once * a.sisme:
        print(f"::warning::{a.marka} ŞİŞTİ: {once} -> {sonra} "
              f"({sonra/once:.1f} kat) — önizlemede incele")
    if once >= 20 and sonra < once * 0.6:
        print(f"::warning::{a.marka} çok düştü: {once} -> {sonra}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
