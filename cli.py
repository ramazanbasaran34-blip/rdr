#!/usr/bin/env python3
"""Bayi Radar komut satırı arayüzü.

Örnekler:
    python cli.py tara                          # tüm markaları tara
    python cli.py tara --marka "Honda" "Yamaha" # sadece bunları tazele
    python cli.py liste --il İstanbul --ilce Kadıköy
    python cli.py liste --il Ankara --format excel pdf
    python cli.py durum                         # hangi marka kaç bayi, ne zaman tarandı
    python cli.py test --marka "Demo Motor"     # seçicileri kaydetmeden dene
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from bayiradar.collect import load_config, plan_olustur, tara_hepsi, tara_marka
from bayiradar.export import to_csv, to_excel, to_pdf
from bayiradar.excel_export import to_excel_full
from bayiradar.html_export import to_html
from bayiradar.fetch import Fetcher
from bayiradar.normalize import fold
from bayiradar.store import db, marka_durumu, son_degisimler, sorgula

CIKTI = Path("ciktilar")


def cmd_plan(a):
    plan = plan_olustur(a.config, a.db, zamanlanmis=a.zamanlanmis)
    if not plan:
        print("Şu an taranması gereken marka yok.")
        return
    print(f"\n{'SAAT':<7}{'MARKA':<22}{'SAYFA':>6}{'SÜRE':>8}   GEREKÇE")
    print("─" * 78)
    for p_ in plan:
        print(f"{p_['baslangic']:%H:%M}  {p_['marka']:<22}{p_['sayfa']:>6}"
              f"{p_['tahmini_dk']:>7.1f}d   {p_['sebep']}")
    son = plan[-1]["baslangic"]
    print(f"\n{len(plan)} marka · tahmini bitiş {son:%H:%M}")


def cmd_tara(a):
    ozet = tara_hepsi(a.config, sadece=a.marka, db_path=a.db,
                      zamanlanmis=a.zamanlanmis)
    print("\n" + "─" * 58)
    print(f"Başarılı : {len(ozet['basarili'])} marka · {ozet['toplam_kayit']} bayi")
    for etiket, anahtar, aciklama in [
        ("Kısmi    ", "kismi", "sayfaların bir kısmı çekilemedi"),
        ("Karantina", "karantina", "kayıt sayısı anormal düştü"),
        ("Hatalı   ", "hatali", "siteye erişilemedi"),
    ]:
        if ozet[anahtar]:
            print(f"{etiket}: {len(ozet[anahtar])} marka ({aciklama})")
            for m, e in ozet[anahtar]:
                print(f"   • {m}: {e[:80]}")
    if ozet["atlanan"]:
        print(f"Atlanan  : {len(ozet['atlanan'])} marka (periyodu dolmamış)")
    if ozet["kismi"] or ozet["karantina"] or ozet["hatali"]:
        print("\n↳ Bu markaların ESKİ VERİSİ KORUNDU. Listelerde 'son başarılı "
              "veri' etiketiyle görünmeye devam ediyorlar.")


def cmd_liste(a):
    with db(a.db) as con:
        kayitlar = sorgula(con, il=a.il, ilce=a.ilce, markalar=a.marka)

    if not kayitlar:
        print("Bu kriterlere uyan bayi bulunamadı.")
        print("İpucu: önce `python cli.py tara` çalıştırdın mı?")
        return

    yer = " / ".join(x for x in (a.il, a.ilce) if x) or "Türkiye geneli"
    baslik = f"Motosiklet Yetkili Bayi Listesi — {yer}"
    print(f"\n{baslik}  ({len(kayitlar)} kayıt)\n")
    for k in kayitlar[:40]:
        print(f"  [{k['marka']:<16}] {k['bayi_adi'][:42]:<42} "
              f"{k['ilce']:<14} {k['telefon']}")
    if len(kayitlar) > 40:
        print(f"  ... ve {len(kayitlar) - 40} kayıt daha")

    CIKTI.mkdir(exist_ok=True)
    damga = datetime.now().strftime("%Y%m%d-%H%M")
    ad = "-".join(fold(x).replace(" ", "") for x in (a.il, a.ilce) if x) or "tumu"
    print()
    for f in a.format:
        p = CIKTI / f"bayiler-{ad}-{damga}.{ 'xlsx' if f=='excel' else f}"
        {"excel": to_excel, "pdf": to_pdf, "csv": to_csv}[f](
            kayitlar, str(p), baslik) if f != "csv" else to_csv(kayitlar, str(p))
        print(f"  ✓ {p}")


SIMGE = {"basarili": "✓", "kismi": "⚠", "karantina": "⚠", "hatali": "✗"}


def _yerel(iso):
    if not iso:
        return "—"
    return datetime.fromisoformat(iso).astimezone().strftime("%d.%m.%Y %H:%M")


def cmd_html(a):
    """Tek dosyalık HTML rehber üretir — kullanıcı sadece buna dokunur."""
    with db(a.db) as con:
        kayitlar = sorgula(con)
        durumlar = marka_durumu(con)
    if not kayitlar:
        print("Veritabanı boş. Önce `python cli.py tara` çalıştırın.")
        return
    CIKTI.mkdir(exist_ok=True)
    yol = CIKTI / a.dosya
    to_html(kayitlar, str(yol), durumlar)
    boyut = yol.stat().st_size / 1024 / 1024
    print(f"\n  ✓ {yol}  ({len(kayitlar)} bayi · {boyut:.1f} MB)")
    print("\n  Bu dosyaya çift tıklayın. Python gerekmez, internet gerekmez.")
    print("  İl/ilçe seçin, Excel veya PDF olarak indirin.")


def cmd_rapor(a):
    """Çift tıklanacak dosyaları üretir: Excel + HTML."""
    with db(a.db) as con:
        kayitlar = sorgula(con)
        durumlar = marka_durumu(con)
    if not kayitlar:
        print("Veritabanı boş. Önce `python cli.py tara` çalıştırın.")
        return
    CIKTI.mkdir(exist_ok=True)
    xl = CIKTI / "BAYI-LISTESI.xlsx"
    to_excel_full(kayitlar, str(xl), durumlar)
    print(f"  ✓ {xl}")
    if not a.sadece_excel:
        hp = CIKTI / "BAYI-REHBERI.html"
        to_html(kayitlar, str(hp), durumlar)
        print(f"  ✓ {hp}")
    print(f"\n  {len(kayitlar)} bayi · {len(durumlar)} marka")


def cmd_durum(a):
    with db(a.db) as con:
        rows = marka_durumu(con)
    if not rows:
        print("Veritabanı boş. `python cli.py tara` ile başla.")
        return

    print(f"\n{'':2}{'MARKA':<20}{'BAYİ':>6}{'ŞÜPHE':>7}   {'SON BAŞARILI':<18}DURUM")
    print("─" * 82)
    for r in rows:
        s_ = SIMGE.get(r["son_deneme_durum"], "?")
        supheli = str(r["supheli"]) if r["supheli"] else "—"
        print(f"{s_:2}{r['marka']:<20}{r['toplam']:>6}{supheli:>7}   "
              f"{_yerel(r['son_basarili']):<18}{r['etiket']}")

    sorunlu = [r for r in rows if r["son_deneme_durum"] != "basarili"]
    print(f"\nTOPLAM: {sum(r['toplam'] for r in rows)} bayi · {len(rows)} marka")
    if sorunlu:
        print(f"\n{len(sorunlu)} markada sorun var — eski verileri korunuyor:")
        for r in sorunlu:
            print(f"  {SIMGE.get(r['son_deneme_durum'],'?')} {r['marka']}")
            print(f"      Son başarılı güncelleme : {_yerel(r['son_basarili'])}")
            print(f"      Son deneme              : {_yerel(r['son_deneme'])}"
                  f"  →  {r['son_deneme_durum'].upper()}")
            if r["son_hata"]:
                print(f"      Sebep                   : {r['son_hata'][:60]}")


def cmd_degisim(a):
    with db(a.db) as con:
        kayitlar = son_degisimler(con, limit=a.adet, marka=(a.marka[0] if a.marka else None))
    if not kayitlar:
        print("Henüz değişim kaydı yok.")
        return
    ikon = {"eklendi": "+", "kaldirildi": "−", "geri_geldi": "↺", "guncellendi": "~"}
    print(f"\nSon {len(kayitlar)} değişiklik:\n")
    for k in kayitlar:
        print(f"  {ikon.get(k['tip'],'?')} [{_yerel(k['tarih'])}] {k['marka']:<14}"
              f"{k['bayi_adi'][:34]:<34} {k['ilce']}")


def cmd_test(a):
    """Yeni bir marka tarifi yazarken seçicileri denemek için — DB'ye yazmaz."""
    conf = load_config(a.config)
    cfg = conf["markalar"].get(a.marka[0])
    if not cfg:
        sys.exit(f"'{a.marka[0]}' brands.yaml içinde yok.")
    f = Fetcher(use_cache=False)
    try:
        kayitlar = tara_marka(a.marka[0], cfg, f, max_age=0)
    finally:
        f.close()
    print(f"\n{len(kayitlar)} kayıt çıktı. İlk 5:\n")
    for k in kayitlar[:5]:
        for alan, deger in k.items():
            if alan != "kaynak_url":
                print(f"   {alan:<10}: {deger or '— BOŞ —'}")
        print()
    bos = [alan for alan in ("il", "ilce", "telefon")
           if sum(1 for k in kayitlar if not k[alan]) > len(kayitlar) * 0.5]
    if bos:
        print(f"⚠ Şu alanlar çoğunlukla boş: {', '.join(bos)} — seçicileri gözden geçir.")


def main():
    p = argparse.ArgumentParser(description="Bayi Radar")
    p.add_argument("--db", default="bayiler.db")
    p.add_argument("--config", default="brands.yaml")
    sub = p.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("tara", help="Markaları gezip veritabanını güncelle")
    t.add_argument("--marka", nargs="*", help="Sadece bu markalar")
    t.add_argument("--zamanlanmis", action="store_true",
                   help="Sadece periyodu dolmuş markaları tara (cron için)")
    t.set_defaults(func=cmd_tara)

    pl = sub.add_parser("plan", help="Tarama sırasını ve tahmini saatleri göster")
    pl.add_argument("--zamanlanmis", action="store_true")
    pl.set_defaults(func=cmd_plan)

    dg = sub.add_parser("degisim", help="Bayi ağındaki son değişiklikler")
    dg.add_argument("--marka", nargs=1)
    dg.add_argument("--adet", type=int, default=30)
    dg.set_defaults(func=cmd_degisim)

    l = sub.add_parser("liste", help="Filtrele ve dosyaya aktar")
    l.add_argument("--il", default="")
    l.add_argument("--ilce", default="")
    l.add_argument("--marka", nargs="*")
    l.add_argument("--format", nargs="*", default=["excel", "pdf"],
                   choices=["excel", "pdf", "csv"])
    l.set_defaults(func=cmd_liste)

    rp = sub.add_parser("rapor", help="Excel ve HTML dosyalarını üret")
    rp.add_argument("--sadece-excel", action="store_true", dest="sadece_excel")
    rp.set_defaults(func=cmd_rapor)

    h = sub.add_parser("html", help="Tek dosyalık HTML rehber üret")
    h.add_argument("--dosya", default="BAYI-REHBERI.html")
    h.set_defaults(func=cmd_html)

    d = sub.add_parser("durum", help="Marka bazlı özet ve son hatalar")
    d.set_defaults(func=cmd_durum)

    ts = sub.add_parser("test", help="Tek markanın seçicilerini dene")
    ts.add_argument("--marka", nargs=1, required=True)
    ts.set_defaults(func=cmd_test)

    a = p.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
