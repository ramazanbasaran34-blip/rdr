#!/usr/bin/env python3
"""Parça veritabanlarını tek veritabanında birleştirir.

Tarama paralel çalışıyor: markalar 10 gruba bölünüp aynı anda taranıyor,
her grup kendi parça dosyasına yazıyor. Bu araç parçaları birleştirir.

Kullanım:  python birlestir.py parcalar/ bayiler.db
"""

import sqlite3
import sys
from pathlib import Path

from bayiradar.store import SCHEMA, _goc

BAYI_SUTUN = ("marka,bayi_adi,il,ilce,adres,telefon,email,website,kaynak_url,"
              "il_key,ilce_key,tekil_key,ilk_gorulme,son_gorulme,durum,"
              "kayip_sayaci,rol,kaynak_satis,kaynak_servis")


def birlestir(parca_dizini="parcalar", hedef="bayiler.db"):
    parcalar = sorted(Path(parca_dizini).glob("*.db"))
    if not parcalar:
        print("Parça bulunamadı.")
        return 0

    # isolation_level=None: otomatik işlem açılmasın.
    # Açık bir işlem varken ATTACH/DETACH "database is locked" veriyor;
    # ilk parça geçiyor, ikincisinde çöküyordu.
    con = sqlite3.connect(hedef, isolation_level=None)
    con.row_factory = sqlite3.Row
    try:
        con.executescript(SCHEMA)
        _goc(con)

        for p in parcalar:
            try:
                con.execute("ATTACH DATABASE ? AS parca", (str(p),))
            except sqlite3.Error as e:
                print(f"  ! {p.name} açılamadı: {e}")
                continue
            try:
                oncesi = con.execute("SELECT COUNT(*) FROM bayiler").fetchone()[0]
                var = {r["name"] for r in con.execute("PRAGMA parca.table_info(bayiler)")}
                sutun = ",".join(c for c in BAYI_SUTUN.split(",") if c in var)
                con.execute("BEGIN")
                con.execute(f"""
                    INSERT INTO bayiler ({sutun})
                    SELECT {sutun} FROM parca.bayiler WHERE true
                    ON CONFLICT(tekil_key) DO UPDATE SET
                        bayi_adi=excluded.bayi_adi, il=excluded.il, ilce=excluded.ilce,
                        adres=excluded.adres, telefon=excluded.telefon,
                        il_key=excluded.il_key, ilce_key=excluded.ilce_key,
                        son_gorulme=excluded.son_gorulme, durum=excluded.durum,
                        rol=excluded.rol,
                        kaynak_satis=COALESCE(excluded.kaynak_satis, kaynak_satis),
                        kaynak_servis=COALESCE(excluded.kaynak_servis, kaynak_servis)
                """)
                for tablo in ("marka_durum", "tarama_log", "degisim_log"):
                    try:
                        hedef_s = [r["name"] for r in
                                   con.execute(f"PRAGMA table_info({tablo})")]
                        kaynak_s = {r["name"] for r in
                                    con.execute(f"PRAGMA parca.table_info({tablo})")}
                        alan = ",".join(x for x in hedef_s
                                        if x != "id" and x in kaynak_s)
                        if not alan:
                            continue
                        fiil = "INSERT OR REPLACE" if tablo == "marka_durum" else "INSERT"
                        con.execute(f"{fiil} INTO {tablo} ({alan}) "
                                    f"SELECT {alan} FROM parca.{tablo}")
                    except sqlite3.Error:
                        pass
                con.execute("COMMIT")
                sonrasi = con.execute("SELECT COUNT(*) FROM bayiler").fetchone()[0]
                print(f"  + {p.name}: +{sonrasi - oncesi} yeni "
                      f"(toplam {sonrasi})")
            except sqlite3.Error as e:
                try:
                    con.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                print(f"  ! {p.name}: {e}")
            finally:
                try:
                    con.execute("DETACH DATABASE parca")
                except sqlite3.Error as e:
                    print(f"  ! {p.name} kapatılamadı: {e}")

        son = con.execute("SELECT COUNT(*) FROM bayiler").fetchone()[0]
        marka = con.execute("SELECT COUNT(DISTINCT marka) FROM bayiler").fetchone()[0]
    finally:
        con.close()

    print(f"\n{len(parcalar)} parça · {son} kayıt · {marka} marka")
    if son == 0:
        print("HATA: hiç kayıt birleşmedi.")
        sys.exit(1)
    return son


if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else "parcalar"
    h = sys.argv[2] if len(sys.argv) > 2 else "bayiler.db"
    birlestir(d, h)
