#!/usr/bin/env python3
"""Veri denetimi — toplanan kayıtlardaki hataları marka bazında bulur.

Amaç: "hangi marka doğru geldi" sorusunu göz kararı değil ölçerek yanıtlamak.
Her marka için kayıtları bir dizi kontrolden geçirir ve sorunları sıralar.

Kullanım:
    python denetle.py                 # tüm markalar, özet
    python denetle.py --marka Rutec   # tek markanın ayrıntısı
    python denetle.py --ayrinti       # tüm sorunlu kayıtları listele
"""

import argparse
import re
from collections import Counter, defaultdict

from bayiradar.normalize import IL_BY_FOLD, fold
from bayiradar.otomatik import TEL, tur_coz
from bayiradar.store import db

# Firma adı olamayacak, sayfa gürültüsü olan ifadeler
GURULTU_AD = re.compile(
    r"^(ara|detay|harita|yol tarifi|devam|daha fazla|iletisim|bilgi al|goster|"
    r"adres|telefon|tikla|konum|haritada goster|tumu|tum|filtre|sirala|"
    r"veriler yukleniyor|yukleniyor|sonuc bulunamadi|kayit yok|secim yapin|"
    r"sehir seciniz|il seciniz|ilce seciniz|lutfen bekleyin)$")

# Adres gibi görünmeyen adres
ADRES_ISARET = re.compile(r"(mah|cad|sok|blv|bulv|no\s*:|osb|sanayi|apt|plaza|"
                          r"kat|meydan|yol|cd|sk|mh)", re.I)


def kontroller(kayitlar):
    """Bir markanın kayıtlarını denetler. Sorun listesi döner."""
    sorunlar = defaultdict(list)
    n = len(kayitlar)
    if not n:
        return sorunlar, {}

    for k in kayitlar:
        ad = k["bayi_adi"] or ""
        fad = fold(ad)

        # 1. Firma adı aslında bir tür etiketi mi? ("Yetkili Servis")
        if tur_coz(ad):
            sorunlar["ad_tur_etiketi"].append(k)
        # 2. Firma adı sayfa gürültüsü mü? ("Detay", "Yükleniyor")
        elif GURULTU_AD.match(fad):
            sorunlar["ad_gurultu"].append(k)
        # 3. Firma adı bir il adı mı?
        elif fad in IL_BY_FOLD:
            sorunlar["ad_il_adi"].append(k)
        # 4. Firma adı çok kısa
        elif len(ad.strip()) < 4:
            sorunlar["ad_cok_kisa"].append(k)
        # 5. Firma adı telefon numarası mı
        elif TEL.fullmatch(ad.strip()):
            sorunlar["ad_telefon"].append(k)
        # 6. Firma adı aslında bir konum mu? (adresin içinde geçiyorsa)
        elif (k["adres"] and fad and len(fad.split()) <= 2
              and fad in fold(k["adres"])):
            sorunlar["ad_konum"].append(k)

        # 6. İlçe alanında tür etiketi ya da il adı
        ilce = k["ilce"] or ""
        if ilce:
            if tur_coz(ilce):
                sorunlar["ilce_tur_etiketi"].append(k)
            elif fold(ilce) in IL_BY_FOLD and fold(ilce) != fold(k["il"] or ""):
                sorunlar["ilce_il_adi"].append(k)
            elif GURULTU_AD.match(fold(ilce)):
                sorunlar["ilce_gurultu"].append(k)

        # 7. İl yok
        if not k["il"]:
            sorunlar["il_bos"].append(k)
        # 8. İl gerçek bir il değil
        elif fold(k["il"]) not in IL_BY_FOLD:
            sorunlar["il_gecersiz"].append(k)

        # 9. Ne telefon ne adres
        if not k["telefon"] and not k["adres"]:
            sorunlar["iletisim_yok"].append(k)
        # 10. Adres adrese benzemiyor
        elif k["adres"] and len(k["adres"]) > 8 and not ADRES_ISARET.search(k["adres"]):
            sorunlar["adres_supheli"].append(k)

        # 11. Telefon biçimi bozuk
        if k["telefon"] and not re.fullmatch(r"\+90\d{10}", k["telefon"]):
            sorunlar["telefon_bozuk"].append(k)

    # 12. Aynı ad çok tekrar ediyor mu (tek bir etiket çoğaltılmış olabilir)
    adlar = Counter(fold(k["bayi_adi"]) for k in kayitlar)
    for a, c in adlar.items():
        if c >= max(3, n * 0.15) and a:
            sorunlar["ad_tekrari"].extend(
                [k for k in kayitlar if fold(k["bayi_adi"]) == a][:3])
            break

    ozet = {
        "adet": n,
        "il_kapsama": sum(1 for k in kayitlar if k["il"]) / n,
        "ilce_kapsama": sum(1 for k in kayitlar if k["ilce"]) / n,
        "tel_kapsama": sum(1 for k in kayitlar if k["telefon"]) / n,
        "benzersiz_ad": len(adlar) / n,
        "il_sayisi": len({k["il"] for k in kayitlar if k["il"]}),
    }
    return sorunlar, ozet


ACIKLAMA = {
    "ad_tur_etiketi": "Firma adı bir tür etiketi (Yetkili Servis vb.)",
    "ad_gurultu": "Firma adı sayfa gürültüsü (Detay, Yükleniyor vb.)",
    "ad_il_adi": "Firma adı bir il adı",
    "ad_cok_kisa": "Firma adı çok kısa",
    "ad_telefon": "Firma adı telefon numarası",
    "ad_konum": "Firma adı aslında konum (adreste geçiyor)",
    "ilce_tur_etiketi": "İlçe alanında tür etiketi",
    "ilce_il_adi": "İlçe alanında il adı",
    "ilce_gurultu": "İlçe alanında gürültü",
    "il_bos": "İl boş",
    "il_gecersiz": "İl geçersiz",
    "iletisim_yok": "Ne telefon ne adres",
    "adres_supheli": "Adres adrese benzemiyor",
    "telefon_bozuk": "Telefon biçimi bozuk",
    "ad_tekrari": "Aynı ad çok tekrar ediyor",
}
# Kaydı kullanılamaz yapan ağır sorunlar
AGIR = {"ad_tur_etiketi", "ad_gurultu", "ad_il_adi", "ad_cok_kisa",
        "ad_telefon", "iletisim_yok", "ad_tekrari", "ad_konum"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--marka")
    ap.add_argument("--ayrinti", action="store_true")
    ap.add_argument("--db", default="bayiler.db")
    a = ap.parse_args()

    # Saha bilgisinden beklenen aralıklar
    import yaml
    try:
        cfg = yaml.safe_load(open("brands.yaml", encoding="utf-8"))["markalar"]
    except Exception:
        cfg = {}
    beklenen = {m: v["beklenen"] for m, v in cfg.items() if v.get("beklenen")}

    with db(a.db) as con:
        q = "SELECT * FROM bayiler WHERE durum!='kaldirildi'"
        p = []
        if a.marka:
            q += " AND marka=?"
            p.append(a.marka)
        kayitlar = [dict(r) for r in con.execute(q, p)]

    gruplar = defaultdict(list)
    for k in kayitlar:
        gruplar[k["marka"]].append(k)

    print(f"\n{len(kayitlar)} kayıt · {len(gruplar)} marka\n")
    print(f"{'MARKA':<18}{'KAYIT':>6}{'AĞIR':>6}{'HAFİF':>7}  {'İL%':>5}{'İLÇE%':>7}"
          f"{'TEL%':>6}  {'DURUM':<14}BEKLENEN")
    print("─" * 92)

    toplam_agir = 0
    sorunlu_markalar = []
    for marka in sorted(gruplar, key=lambda m: fold(m)):
        ks = gruplar[marka]
        so, oz = kontroller(ks)
        agir = sum(len(v) for t, v in so.items() if t in AGIR)
        hafif = sum(len(v) for t, v in so.items() if t not in AGIR)
        toplam_agir += agir
        oran = agir / oz["adet"] if oz["adet"] else 0
        durum = ("BOZUK" if oran > 0.5 else "sorunlu" if oran > 0.1
                 else "kontrol" if agir else "temiz")
        # Beklenen sayıyla karşılaştır: sayfa açıldı ama yarısı alındıysa
        # kayıtlar temiz görünür, eksiklik ancak burada yakalanır.
        bek = beklenen.get(marka)
        if bek:
            if oz["adet"] < bek[0] * 0.5:
                durum = "ÇOK AZ"
            elif oz["adet"] > bek[1] * 2:
                durum = "ÇOK FAZLA"
            elif not (bek[0] * 0.7 <= oz["adet"] <= bek[1] * 1.4) and durum == "temiz":
                durum = "sayı şüpheli"
        if durum != "temiz":
            sorunlu_markalar.append((marka, so, oz, oran))
        bek_str = f"{bek[0]}-{bek[1]}" if bek else ""
        print(f"{marka:<18}{oz['adet']:>6}{agir:>6}{hafif:>7}  "
              f"{oz['il_kapsama']*100:>4.0f}%{oz['ilce_kapsama']*100:>6.0f}%"
              f"{oz['tel_kapsama']*100:>5.0f}%  {durum:<14}{bek_str}")

    print("─" * 92)
    print(f"Toplam ağır sorunlu kayıt: {toplam_agir} / {len(kayitlar)}")

    if sorunlu_markalar:
        print("\n\nSORUN AYRINTISI\n" + "=" * 92)
        for marka, so, oz, oran in sorted(sorunlu_markalar, key=lambda x: -x[3]):
            print(f"\n{marka}  ({oz['adet']} kayıt)")
            for tip, kayit in sorted(so.items(), key=lambda x: -len(x[1])):
                isaret = "!!" if tip in AGIR else " ·"
                print(f"  {isaret} {ACIKLAMA[tip]:<44}{len(kayit):>5}")
                if a.ayrinti or a.marka:
                    for k in kayit[:3]:
                        print(f"       ad='{(k['bayi_adi'] or '')[:34]}' "
                              f"il='{k['il']}' ilçe='{k['ilce']}' tel='{k['telefon']}'")


if __name__ == "__main__":
    main()
