#!/usr/bin/env python3
"""KTM / Husqvarna kayıtlarını kaydedilmiş spormoto sayfalarından birebir kurar.

Neden: genel eşleştirici (_ayni_firmayi_bul) farklı noktaları aynı satıra
katıp rol kaybettiriyordu; sayfa KTM'de 25 satış noktası gösteriyordu.
Bu betik iki markanın aktif kayıtlarını 'kaldirildi'ye çeker (silmez),
sonra ozel/spormoto.py (son_isle dahil) çıktısını tekil_key ile yazar.
Fuzzy eşleştirme KULLANILMAZ.

    python spormoto_duzelt.py bayiler.db bayiler_yeni.db
"""
import gzip, sqlite3, sys
from ozel import spormoto as sp
from bayiradar.parse import finalize
from bayiradar.store import tekil_key, now
from bayiradar.normalize import fold


def kayitlar(m):
    hepsi = []
    for rol in ("satis", "servis"):
        h = gzip.decompress(open(f"ham/{m.lower()}-{rol}.html.gz", "rb").read()).decode("utf-8", "replace")
        url = sp.KAYNAKLAR[m][rol]
        hepsi += [x for x in (finalize(r, m, url, {}) for r in sp.coz(rol, h, url)) if x]
    return sp.son_isle(hepsi)


def yaz(db):
    con = sqlite3.connect(db); con.row_factory = sqlite3.Row
    t = now()
    for m in sp.MARKALAR:
        recs = kayitlar(m)
        con.execute("UPDATE bayiler SET durum='kaldirildi' WHERE marka=? AND durum!='kaldirildi'", (m,))
        for r in recs:
            k = tekil_key(r); rol = r["rol"]
            ks = r["kaynak_url"] if rol in ("satis", "satis_servis") else ""
            kv = r["kaynak_url"] if rol in ("servis", "satis_servis") else ""
            if rol == "satis_servis":
                ks, kv = sp.KAYNAKLAR[m]["satis"], sp.KAYNAKLAR[m]["servis"]
            vals = (m, r["bayi_adi"], r["il"], r["ilce"], r["adres"], r["telefon"], r["email"],
                    r["website"], r["kaynak_url"], fold(r["il"]), fold(r["ilce"]))
            row = con.execute("SELECT id FROM bayiler WHERE tekil_key=?", (k,)).fetchone()
            if row:
                con.execute("""UPDATE bayiler SET marka=?,bayi_adi=?,il=?,ilce=?,adres=?,telefon=?,
                    email=?,website=?,kaynak_url=?,il_key=?,ilce_key=?,son_gorulme=?,durum='aktif',
                    kayip_sayaci=0,rol=?,kaynak_satis=?,kaynak_servis=? WHERE id=?""",
                    vals + (t, rol, ks, kv, row["id"]))
            else:
                con.execute("""INSERT INTO bayiler (marka,bayi_adi,il,ilce,adres,telefon,email,website,
                    kaynak_url,il_key,ilce_key,tekil_key,ilk_gorulme,son_gorulme,durum,kayip_sayaci,rol,
                    kaynak_satis,kaynak_servis) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,'aktif',0,?,?,?)""",
                    vals + (k, t, t, rol, ks, kv))
        con.execute("UPDATE marka_durum SET son_basarili_adet=?, karantina=0 WHERE marka=?", (len(recs), m))
        c = dict(con.execute("""SELECT rol,count(*) FROM bayiler WHERE marka=? AND durum!='kaldirildi'
                                GROUP BY rol""", (m,)).fetchall())
        print(db, m, "satış noktası", c.get("satis", 0) + c.get("satis_servis", 0),
              "| servis noktası", c.get("servis", 0) + c.get("satis_servis", 0), c)
    con.commit()


if __name__ == "__main__":
    for db in sys.argv[1:] or ["bayiler.db", "bayiler_yeni.db"]:
        yaz(db)
