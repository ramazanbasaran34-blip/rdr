#!/usr/bin/env python3
"""ozel/ altındaki marka toplayıcılarını CANLI çalıştırır.

Her marka kendi modülünde; bu betik sadece istekleri atıp sonucu
veritabanına yazar. Üç gezinme biçimi var:

  tek     — tek adres, ülkenin tamamı (Falcon, Nanok, Meka, Kral, Vespa...)
  il_adi  — il adıyla adres (Zelsun, Motolux, CSN)
  il_kodu — plaka koduyla adres (Musatti)

    python ozel_tara.py                 # hepsi
    python ozel_tara.py falcon kral     # seçili
    python ozel_tara.py --kuru          # veritabanına yazma
"""

from __future__ import annotations

import importlib
import json
import sys
import time
from pathlib import Path

import requests

from bayiradar.normalize import ILLER, fold, tr_upper
from bayiradar.parse import finalize
from bayiradar.store import commit_tarama, db, now

BASLIK = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9",
}

PLAKA = {ad: f"{i + 1:02d}" for i, ad in enumerate(ILLER)}

# modül -> gezinme biçimi
GEZINME = {
    "falcon": "tek", "nanok": "tek", "meka": "tek",
    "kral": "tek", "vespa": "tek", "suzuki": "tek", "isotlar": "tek",
    "zelsun": "il_adi", "motolux": "il_adi", "csn": "il_adi",
    "musatti": "il_kodu",
    "leksas": "tek", "indian": "tek",
    "aprilia": "tek", "piaggio": "tek", "kymco": "tek", "yiben": "tek",
    # ASP.NET WebForms: il seçimi ViewState taşıyan POST ile
    "altai": "postback", "regal": "postback",
    # Kimmi ve Lifan aynı modülü paylaşıyor; il listesi sitenin kendi
    # <select id="cities"> kutusundan okunuyor, ILLER sabitinden değil.
    "kimmi_lifan": "cities",
    # Yuki: il listesi sayfadaki `provinces` dizisinden, adres
    # ?province=<slug> parametresiyle. Konum tespiti sadece kısayol.
    "yuki": "province", "rewaco": "tek", "rebat": "tek", "sym": "tek", "kawasaki": "tek",
    # BMW: Borusan Otomotiv il bazli arama sayfasi
    "bmw": "adres_listesi",
    # Kuralkan tek sayfada hem Bajaj hem Kanuni ağını veriyor
    "kuralkan": "cok_marka",
    # STMax: seçenek değeri zaten tam adres
    "stmax": "adres_listesi",
    # ASP.NET WebForms: il seçimi URL'e yansımıyor, ViewState ile POST
    # atmak gerekiyor. Ayrı bir akışla yürüyor (_postback_tara).
    "altai": "postback", "regal": "postback",
}

MODULLER = list(GEZINME)


def _slug(il: str) -> str:
    return fold(il).replace(" ", "-")


def _hedefler(mod_ad: str, mod) -> list[tuple[str, str, str, str]]:
    """(marka, rol, url, il) listesi döner."""
    bicim = GEZINME[mod_ad]
    out = []

    if bicim == "tek":
        # İsotlar'da anahtar marka adı, ötekilerde rol
        for anahtar, url in mod.KAYNAKLAR.items():
            if anahtar in ("Peugeot", "Horwin", "Lambretta"):
                out.append((anahtar, "hepsi", url, ""))
            else:
                out.append((mod.MARKA, anahtar, url, ""))
        return out

    if bicim == "cok_marka":
        # Tek kaynak, birden çok marka (Bajaj ve Kanuni aynı ağ).
        for marka in mod.MARKALAR:
            for rol, url in mod.KAYNAKLAR.items():
                out.append((marka, rol, url, ""))
        return out

    if bicim == "adres_listesi":
        # İl açılır kutusundaki değerler doğrudan adres.
        import requests as _r
        for rol, kok in mod.KAYNAKLAR.items():
            try:
                y = _r.get(kok, headers=BASLIK, timeout=45)
                iller = mod.il_sluglari(y.text)
            except Exception:  # noqa: BLE001
                iller = []
            for adres, ad in iller:
                out.append((mod.MARKA, rol, adres, ad))
        return out

    if bicim == "province":
        # Sitenin kendi il listesini kullan (79 il; bazıları ILLER'de yok,
        # bazı adlar iki kez geçiyor — Afyon/Afyonkarahisar gibi).
        import requests as _r
        for rol, kok in mod.KAYNAKLAR.items():
            try:
                y = _r.get(kok, headers=BASLIK, timeout=45)
                iller = mod.il_sluglari(y.text)
            except Exception:  # noqa: BLE001
                iller = []
            for slug, ad in iller:
                out.append((mod.MARKA, rol, mod.il_url(rol, slug), ad.title()))
        return out

    if bicim == "cities":
        # Önce ana sayfayı çekip sitenin YAYINLADIĞI il listesini al.
        # Kimmi 50, Lifan daha az il listeliyor; 81 ili denemek boşuna
        # istek ve 404 demek.
        import requests as _r
        for marka, taban in mod.TABAN.items():
            for rol, kalip in mod.KAYNAKLAR.items():
                kok = kalip.format(taban=taban, slug="").rstrip("/")
                try:
                    y = _r.get(kok + "/", headers=BASLIK, timeout=45)
                    iller = mod.il_sluglari(y.text)
                except Exception:  # noqa: BLE001
                    iller = []
                for slug, ad in iller:
                    out.append((marka, rol, mod.il_url(marka, rol, slug), ad))
        return out

    for il in ILLER:
        if bicim == "il_adi":
            if mod_ad == "zelsun":
                for rol in ("satis", "servis"):
                    out.append((mod.MARKA, rol, mod.il_url(rol, tr_upper(il)), il))
            elif mod_ad == "motolux":
                out.append((mod.MARKA, "hepsi", mod.il_url(_slug(il)), il))
            elif mod_ad == "csn":
                for rol in ("satis", "servis"):
                    out.append((mod.MARKA, rol, mod.il_url(rol, _slug(il)), il))
        else:  # il_kodu
            for rol in ("satis", "servis"):
                out.append((mod.MARKA, rol, mod.il_url(rol, PLAKA[il]), il))
    return out


def _postback_tara(mod_ad: str, mod, log=print) -> tuple[dict, float]:
    """ASP.NET WebForms siteleri: her il için ViewState taşıyarak POST.

    Sunucu her yanıtta YENİ ViewState üretiyor; zincir bozulursa
    "geçersiz durum" hatası gelir. O yüzden gövde her adımda yenileniyor.
    """
    toplam: dict[str, list[dict]] = {}
    denendi = basarili = 0

    for rol, url in mod.KAYNAKLAR.items():
        oturum = requests.Session()
        oturum.headers.update(BASLIK)
        try:
            ilk = oturum.get(url, timeout=60)
            ilk.raise_for_status()
            govde = ilk.text
        except Exception as e:  # noqa: BLE001
            log(f"    ✗ {mod.MARKA}/{rol}: {str(e)[:60]}")
            continue

        for deger, il_adi in mod.il_secenekleri(govde):
            denendi += 1
            try:
                y = oturum.post(url, data=mod.post_govdesi(govde, deger),
                                timeout=60, headers={"Referer": url})
                y.raise_for_status()
                govde = y.text          # zincir: sonraki ViewState
                basarili += 1
            except Exception as e:  # noqa: BLE001
                log(f"    ✗ {mod.MARKA}/{rol}/{il_adi}: {str(e)[:50]}")
                continue

            try:
                for r in mod.coz(rol, govde, url, il=il_adi):
                    k = finalize(dict(r), mod.MARKA, url, {})
                    if k:
                        toplam.setdefault(mod.MARKA, []).append(k)
            except Exception as e:  # noqa: BLE001
                log(f"    ✗ ayrıştırma {il_adi}: {str(e)[:50]}")
            time.sleep(0.3)

    return toplam, (basarili / denendi if denendi else 0.0)


def marka_tara(mod_ad: str, log=print) -> dict[str, list[dict]]:
    mod = importlib.import_module(f"ozel.{mod_ad}")
    if GEZINME.get(mod_ad) == "postback":
        toplam, kapsam = _postback_tara(mod_ad, mod, log)
        for marka in toplam:
            log(f"  {marka}: {len(toplam[marka])} kayıt (kapsam %{kapsam*100:.0f})")
        return toplam
    kodlama = getattr(mod, "KODLAMA", None)
    oturum = requests.Session()
    oturum.headers.update(BASLIK)

    toplam: dict[str, list[dict]] = {}
    denendi = basarili = 0
    ilk_il_kotu = 0

    for marka, rol, url, il in _hedefler(mod_ad, mod):
        denendi += 1
        try:
            y = oturum.get(url, timeout=60)
            if y.status_code >= 400:
                raise RuntimeError(f"HTTP {y.status_code}")
            govde = y.content.decode(kodlama, "replace") if kodlama else y.text
        except Exception as e:  # noqa: BLE001
            log(f"    ✗ {marka}/{rol}/{il or '-'}: {str(e)[:50]}")
            ilk_il_kotu += 1
            if ilk_il_kotu > 12:
                log("    ✗ çok fazla hata, bu marka bırakılıyor")
                break
            continue
        basarili += 1

        try:
            ek = {}
            degiskenler = mod.coz.__code__.co_varnames[:mod.coz.__code__.co_argcount]
            if "il" in degiskenler:
                ek["il"] = il
            ham = mod.coz(rol, govde, url, **ek)
        except Exception as e:  # noqa: BLE001
            log(f"    ✗ ayrıştırma {marka}/{il}: {str(e)[:60]}")
            continue

        cfg = {"il_ilce_birlesik": "konum"} if ham and "konum" in ham[0] else {}
        for r in ham:
            k = finalize(dict(r), marka, url, cfg)
            if k:
                toplam.setdefault(marka, []).append(k)

        if il:
            time.sleep(0.25)

    kapsam = basarili / denendi if denendi else 0.0
    for marka in toplam:
        log(f"  {marka}: {len(toplam[marka])} kayıt "
            f"(kapsam %{kapsam * 100:.0f})")
    return toplam


def main() -> None:
    kuru = "--kuru" in sys.argv
    istenen = [a for a in sys.argv[1:] if not a.startswith("-")]
    moduller = istenen or MODULLER

    rapor: dict = {}
    basladi = now()

    for mod_ad in moduller:
        print(f"\n=== {mod_ad.upper()} ===")
        try:
            sonuc = marka_tara(mod_ad)
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ {type(e).__name__}: {e}")
            rapor[mod_ad] = {"hata": str(e)[:150]}
            continue

        for marka, kayitlar in sonuc.items():
            iller = {k.get("il") for k in kayitlar if k.get("il")}
            r = {"kayit": len(kayitlar), "il": len(iller),
                 "ilsiz": sum(1 for k in kayitlar if not k.get("il"))}
            if not kuru and kayitlar:
                with db() as con:
                    r["db"] = str(commit_tarama(con, marka, kayitlar, 1.0, basladi))[:180]
            rapor[marka] = r
            print(f"  → {marka}: {json.dumps(r, ensure_ascii=False)[:150]}")

    Path("ham").mkdir(exist_ok=True)
    Path("ham/ozel-tarama.json").write_text(
        json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n" + json.dumps(rapor, ensure_ascii=False, indent=1)[:1500])


if __name__ == "__main__":
    main()
