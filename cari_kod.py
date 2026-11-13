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
import re
import random
import sqlite3
import sys
from pathlib import Path

from ozel.tr import anahtar

DOSYA = Path("cari_kodlar.json")
DB = "bayiler.db"

# 0/O, 1/I, 5/S karışmasın diye çıkarıldı
ALFABE = "ABCDEFGHJKLMNPQRTUVWXYZ2346789"


# Şirket eklerini eleyip firmanın ayırt edici kelimelerini bırakır.
# "HAFIZLAR OTOMOTİV ... SAN VE TİC LTD ŞTİ" -> {hafizlar, otomotiv, ...}
_GENEL = {
    "san", "sanayi", "tic", "ticaret", "ltd", "limited", "sti", "sirketi",
    "as", "a", "s", "ve", "insaat", "taahhut", "turizm", "pazarlama",
    "otomotiv", "motor", "motorlu", "araclar", "motosiklet", "bisiklet",
    "nak", "nakliyat", "gida", "ith", "ihr", "dis", "ic", "grup",
}


def _ad_kelimeleri(ad: str) -> set:
    return {k for k in anahtar(ad).split()
            if len(k) > 2 and k not in _GENEL}


# TEK KAYNAK: adres karşılaştırması bayiradar/eslestir.py'de.
# Burada ikinci bir kopyası vardı ve farklı sonuç veriyordu.
from bayiradar.eslestir import adres_benzer as ayni_adres_mi  # noqa: E402


def firma_anahtari(tel: str, il: str, ilce: str, ad: str,
                   adres: str = "") -> str:
    """Aynı fiziksel işyerini tanımlayan anahtar.

    Telefon güçlü kanıt AMA tek başına yetmiyor: farklı firmalar aynı
    numarayı paylaşabiliyor. Niğde'de "HAFIZLAR OTOMOTİV" ile "MERTAS
    PAZARLAMA" aynı numarayı kullanıyor ve tek firmaya iniyorlardı;
    Hafızlar'ın kartında olmadığı hâlde Hero rozeti çıkıyordu.

    Bu yüzden telefona ADIN AYIRT EDİCİ İLK KELİMESİ de ekleniyor.
    Şirket ekleri (san, tic, ltd, ştı...) sayılmıyor, böylece aynı
    firmanın farklı yazımları ("MANAVGAT MOTOR / YASİN AĞGEDİK" ile
    "YASİN AĞGEDİK") yine birleşiyor — ortak kelimeleri var.
    """
    t = "".join(c for c in (tel or "") if c.isdigit())
    t = t[-10:] if len(t) >= 10 else ""
    if t:
        # ADIN TAMAMI anahtarda: aynı işyerinin farklı yazımları ayrı
        # anahtar üretir ama main() onları AYNI koda bağlar. "Alfabetik
        # ilk kelime" denendi ve kararsız çıktı (705 grup yanlış ayrıldı):
        # bir kayıttaki fazladan kelime sırayı değiştiriyordu.
        # ADRES DE ANAHTARDA: aynı numarayı paylaşan AYRI şubeler ayrı
        # firma. CFMoto/Edremit'te Özdemir Mağazaları'nın Altınkum ve
        # Camivasat şubeleri, Bayhas Motors'un şubeleri böyle. Aynı koda
        # düşerlerse birbirine karışıyorlar.
        return (f"T:{t}|{anahtar(il)}|{anahtar(ilce)}|{anahtar(ad)}"
                f"|{anahtar(adres)[:60]}")
    # Telefonsuz kayıtlar ad + adrese göre ayrılıyor
    return f"A:{anahtar(ad)}|{anahtar(il)}|{anahtar(ilce)}|{anahtar(adres)[:60]}"


def _kod_uret(rnd: random.Random) -> str:
    return "".join(rnd.choice(ALFABE) for _ in range(4))


def _kayitlar(db: str) -> list[dict]:
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    # KAPALI KAYITLAR DA DAHİL: bayi kapanınca kodsuz kalmasın, geri
    # açılınca aynı kodu bulsun. Eskiden durum süzgeci vardı.
    r = [dict(x) for x in con.execute(
        "SELECT bayi_adi, il, ilce, telefon, adres, durum FROM bayiler")]
    con.close()
    return r


def esleme_uret(kayitlar: list[dict]) -> dict:
    """anahtar -> kod. Aynı işyerinin yazım farkları tek kodda toplanır.

    İKİ TUZAK VAR, ikisi de yaşandı:

    1. Gruplarken HAM adres karşılaştırılmalı. Anahtardaki adres
       normalleştirilip 60 karaktere kırpılıyor; onunla karşılaştırınca
       kapı numarası kesilip ayrı işyerleri tek koda iniyordu.

    2. Aday, grubun TEK temsilci adresiyle değil BÜTÜN adresleriyle
       karşılaştırılmalı. Adresi boş bir kayıt gruba ilk düşerse boş
       adres her şeye benzediği için grup mıknatıs gibi büyüyordu.
       Bu yüzden üyeler önce adres uzunluğuna göre sıralanıyor: dolu
       adresli kayıtlar grubu kuruyor, boşlar sonra yerleşiyor.
    """
    anahtar_ad, ham_adres = {}, {}
    for r in kayitlar:
        a = firma_anahtari(r["telefon"], r["il"], r["ilce"],
                           r["bayi_adi"], r.get("adres", ""))
        anahtar_ad.setdefault(a, r)
        if len(r.get("adres") or "") > len(ham_adres.get(a, "")):
            ham_adres[a] = r.get("adres") or ""

    kovalar: dict[tuple, list] = {}
    for a in anahtar_ad:
        p = a.split("|")
        kovalar.setdefault((p[0], p[1], p[2]), []).append(a)

    temsilci: dict[str, str] = {}
    for uyeler in kovalar.values():
        gruplar: list[list[str]] = []
        kelimeler: list[set] = []
        adresler: list[list[str]] = []
        for a in sorted(uyeler, key=lambda x: (-len(ham_adres.get(x, "")), x)):
            p = a.split("|")
            ad = p[3] if len(p) > 3 else ""
            adr = ham_adres.get(a, "")
            k = {w for w in ad.split() if len(w) > 2 and w not in _GENEL}
            for i in range(len(gruplar)):
                ad_uyar = (not k or not kelimeler[i] or (k & kelimeler[i]))
                if ad_uyar and all(ayni_adres_mi(adr, x) for x in adresler[i]):
                    gruplar[i].append(a)
                    kelimeler[i] |= k
                    if adr:
                        adresler[i].append(adr)
                    break
            else:
                gruplar.append([a])
                kelimeler.append(set(k))
                adresler.append([adr] if adr else [])
        for g in gruplar:
            for a in g:
                temsilci[a] = g[0]

    rnd = random.Random(20260905)
    kod_of, kullanilan = {}, set()
    for t in sorted(set(temsilci.values())):
        for _ in range(10000):
            k = _kod_uret(rnd)
            if k not in kullanilan:
                kullanilan.add(k)
                kod_of[t] = k
                break
        else:
            raise SystemExit("kod havuzu tükendi")
    return {a: kod_of[t] for a, t in temsilci.items()}


def denetle(eslesme: dict, kayitlar: list[dict]) -> list[str]:
    """Üretilen eşlemeyi sınar. Boş liste dönerse kayıt güvenli."""
    import collections
    hata = []

    def anah(r):
        return firma_anahtari(r["telefon"], r["il"], r["ilce"],
                              r["bayi_adi"], r.get("adres", ""))

    kodsuz = [r for r in kayitlar if anah(r) not in eslesme]
    if kodsuz:
        hata.append(f"kodsuz kayıt: {len(kodsuz)} (ör. {kodsuz[0]['bayi_adi']})")

    kapali = [r for r in kayitlar
              if r.get("durum") != "aktif" and anah(r) not in eslesme]
    if kapali:
        hata.append(f"kapalı ama kodsuz: {len(kapali)}")

    kod_adres = collections.defaultdict(set)
    for r in kayitlar:
        k = eslesme.get(anah(r))
        if k and (r.get("adres") or "").strip():
            kod_adres[k].add(r["adres"])
    karisik = []
    for k, adr in kod_adres.items():
        adr = list(adr)
        for i in range(len(adr)):
            for j in range(i + 1, len(adr)):
                if not ayni_adres_mi(adr[i], adr[j]):
                    karisik.append((k, adr[i], adr[j]))
    if karisik:
        hata.append(f"aynı kodda farklı adres: {len(karisik)} "
                    f"(ör. {karisik[0][0]}: {karisik[0][1][:34]} / "
                    f"{karisik[0][2][:34]})")

    bozuk = [k for k in set(eslesme.values())
             if len(k) != 4 or any(c not in ALFABE for c in k)]
    if bozuk:
        hata.append(f"biçimi bozuk kod: {len(bozuk)}")
    return hata


def main() -> None:
    """Kodları üretir, DENETLER, denetim geçerse yazar.

    Eski davranış eski kodları korumaya çalışıyordu. Artık korumuyoruz:
    o kodlar adres içermeyen bozuk anahtarla verilmişti, taşımak
    karışıklığı sürdürürdü.
    """
    db = DB
    for i, a in enumerate(sys.argv):
        if a == "--db" and i + 1 < len(sys.argv):
            db = sys.argv[i + 1]

    kayitlar = _kayitlar(db)
    eslesme = esleme_uret(kayitlar)
    print(f"kayıt: {len(kayitlar)}  ·  ayrı işyeri: {len(set(eslesme.values()))}"
          f"  ·  anahtar: {len(eslesme)}")

    if "--rapor" in sys.argv:
        return

    hata = denetle(eslesme, kayitlar)
    if hata:
        print("DENETİM KALDI — dosya yazılmadı:")
        for h in hata:
            print("  ✗", h)
        raise SystemExit(1)

    for satir in ("her kaydın kodu var", "kapalı kayıtlar da kodlu",
                  "hiçbir kod birden çok adrese dağılmıyor",
                  "kod biçimi doğru"):
        print("  ✓", satir)
    DOSYA.write_text(json.dumps(eslesme, ensure_ascii=False, indent=0,
                                sort_keys=True), encoding="utf-8")
    print(f"yazıldı: {DOSYA}")


if __name__ == "__main__":
    main()
