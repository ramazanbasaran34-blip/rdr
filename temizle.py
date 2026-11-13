#!/usr/bin/env python3
"""Birleştirme sonrası otomatik temizlik.

Her taramadan sonra çalışır. Yalnızca KESİN durumları ele alır; "sitede
bulunamadı" kayıtlarına DOKUNMAZ (onlar birkaç tarama sonra kendiliğinden
düşer, karar kullanıcının).

Kaldırılan üç sınıf (7 Eylül 2026'da 240 kayıt elle incelenip doğrulandı):
  A) Ayrıştırma artığı: bayi adı yerine etiket/ilçe adı ("MERKEZ",
     "Telefon", "HENDEK / SAKARYA"). Bayi değil.
  B) Aynı bayinin yeni kaydı var: aynı marka + aynı telefon + benzer adresle
     aktif kayıt. Ad/anahtar değişimi sonucu eski satır öksüz kalmış.
  C) Bayi taşınmış: aynı marka + aynı telefon + aynı ad, farklı adresle
     aktif kayıt. Eski adres kaydı.

  D) Siteden düşmüş: markanın sitesi SORUNSUZ (karantina/hata yok) ve
     kayıt, son görülmesinden sonra EN AZ 3 başarılı tam taramada ve en az
     3 gün boyunca bir daha çıkmamış. 7 Eylül'de 60 kayıt bu kuralla elle
     doğrulanıp kullanıcı onayıyla kaldırılmıştı; kural burada kalıcı.

Ayrıca eski bozuk ayrıştırıcıdan kalan yanlış karantina tabanlarını
düzeltir (Taktas: 88 çöp → 44 gerçek).

    python temizle.py bayiler_yeni.db
"""

from __future__ import annotations

import collections
import re
import sqlite3
import sys
from datetime import datetime, timezone

from bayiradar.eslestir import _ayirt_edici, adres_benzer
from bayiradar.ilceler import ilce_mi
from bayiradar.normalize import clean_phone, fold

ETIKET = {"telefon", "adres", "merkez", "tel", "gsm", "bayi", "servis"}

# Eski ayrıştırıcının ürettiği yanlış tabanlar: marka → gerçek adet
TABAN_DUZELT = {"Taktas": 44}


def sinif(r, tel_ix, ad_ix):
    ad = r["bayi_adi"] or ""
    s = fold(ad)
    if s in ETIKET or ilce_mi(ad) or re.fullmatch(r"[\d\s()+/.-]{7,}", ad):
        return "A", "Ayrıştırma artığı — bayi adı değil etiket/ilçe adı"
    t = clean_phone(r["telefon"])
    m = r["marka"]
    ikiz = [a for a in tel_ix.get((m, t), []) if adres_benzer(a["adres"], r["adres"])]
    ikiz = ikiz or [a for a in ad_ix.get((m, fold(ad), fold(r["il"])), [])
                    if adres_benzer(a["adres"], r["adres"])]
    if ikiz:
        return "B", f"Aynı bayinin güncel kaydı aktif: {ikiz[0]['bayi_adi'][:40]}"
    if t:
        es = [a for a in tel_ix.get((m, t), [])
              if (_ayirt_edici(a["bayi_adi"]) & _ayirt_edici(ad)) or fold(a["bayi_adi"]) == s]
        if es:
            return "C", f"Bayi taşınmış — aynı telefon ve ad, yeni adres aktif: {es[0]['adres'][:40]}"
    return None, None


def main(yol: str) -> None:
    con = sqlite3.connect(yol)
    con.row_factory = sqlite3.Row
    t = datetime.now(timezone.utc).isoformat(timespec="seconds")

    aktif = [dict(x) for x in con.execute("SELECT * FROM bayiler WHERE durum='aktif'")]
    tel_ix, ad_ix = collections.defaultdict(list), collections.defaultdict(list)
    for a in aktif:
        tel_ix[(a["marka"], clean_phone(a["telefon"]))].append(a)
        ad_ix[(a["marka"], fold(a["bayi_adi"]), fold(a["il"]))].append(a)

    sayac = collections.Counter()
    for r in con.execute("SELECT * FROM bayiler WHERE durum='dogrulanamadi'").fetchall():
        kod, sebep = sinif(dict(r), tel_ix, ad_ix)
        if not kod:
            continue
        con.execute("UPDATE bayiler SET durum='kaldirildi' WHERE id=?", (r["id"],))
        con.execute("""INSERT INTO degisim_log (tarih, marka, tip, bayi_adi, il, ilce, detay)
                       VALUES (?,?,?,?,?,?,?)""",
                    (t, r["marka"], "kaldirildi", r["bayi_adi"], r["il"], r["ilce"],
                     f"[otomatik temizlik {kod}] {sebep}"))
        sayac[kod] += 1

    # D) Siteden düşmüş — marka sağlıklı, kayıt 3+ başarılı taramada yok
    durum = {r["marka"]: dict(r) for r in con.execute("SELECT * FROM marka_durum")}
    basarili_log = collections.defaultdict(list)
    for r in con.execute("SELECT marka, bitis FROM tarama_log WHERE durum='basarili'"):
        basarili_log[r["marka"]].append(r["bitis"] or "")
    for r in con.execute("SELECT * FROM bayiler WHERE durum='dogrulanamadi'").fetchall():
        d = durum.get(r["marka"]) or {}
        if d.get("karantina") or d.get("son_deneme_durum") != "basarili":
            continue                      # site sorunlu: dokunma
        son = r["son_gorulme"] or ""
        sonraki = [b for b in basarili_log.get(r["marka"], []) if b > son]
        gun = 0
        try:
            gun = (datetime.fromisoformat(t.replace("Z", "+00:00"))
                   - datetime.fromisoformat(son.replace("Z", "+00:00"))).days
        except ValueError:
            pass
        if len(sonraki) >= 3 and gun >= 3:
            con.execute("UPDATE bayiler SET durum='kaldirildi' WHERE id=?", (r["id"],))
            con.execute("""INSERT INTO degisim_log (tarih, marka, tip, bayi_adi, il, ilce, detay)
                           VALUES (?,?,?,?,?,?,?)""",
                        (t, r["marka"], "kaldirildi", r["bayi_adi"], r["il"], r["ilce"],
                         f"[otomatik temizlik D] Sitede bulunamadı — {len(sonraki)} başarılı "
                         f"taramada ve {gun} günde bir daha çıkmadı"))
            sayac["D"] += 1

    for marka, adet in TABAN_DUZELT.items():
        d = con.execute("SELECT son_basarili_adet, karantina FROM marka_durum WHERE marka=?",
                        (marka,)).fetchone()
        if d and (d["son_basarili_adet"] or 0) > adet * 1.5:
            con.execute("""UPDATE marka_durum SET son_basarili_adet=?, karantina=0,
                           son_deneme_durum='basarili', son_hata='' WHERE marka=?""",
                        (adet, marka))
            sayac["taban"] += 1

    con.commit()
    kalan = con.execute("SELECT COUNT(*) FROM bayiler WHERE durum='dogrulanamadi'").fetchone()[0]
    con.close()
    print(f"[temizlik] A={sayac['A']} B={sayac['B']} C={sayac['C']} D={sayac['D']} "
          f"taban={sayac['taban']} · kalan doğrulanamadı={kalan}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "bayiler_yeni.db")
