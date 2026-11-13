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
# Kodlama secimi TEK NOKTADAN: bu dosya kendi cekme kodunu kullaniyordu
# ve requests'in varsayilani (baslikta charset yoksa ISO-8859-1) Turkce
# harfleri bozuyordu. 29 ozel modullu marka fetch.py'deki duzeltmeyi
# hic gormuyordu.
from bayiradar.fetch import _en_iyi_coz
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
    # Akeso: Elementor akordeonu, il başlıkları altında düz h2 satırları
    "akeso": "tek",
    # Voge: tek sayfa, il grupları ve kart sınıfında rol
    "voge": "tek",
    # TVS: modül kendi POST isteğini atıyor (getir)
    "tvs": "tek",
    # Yenilenen siteler: liste artık JSON uçlarından geliyor
    "rutec": "tek", "acco": "tek", "taktas": "tek",
    # Arora: 8 Eylul'de il secimi zorunlu oldu; liste sayfaya gomulu JSON'da
    "arora": "tek",
    # Honda: Qwik sayfa durumundan (qwik/json) okunuyor
    "honda": "tek",
    # FCM: il il sekmeler, il bilgisi sekme başlığında
    "fcm": "tek",
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
    # Spormoto: KTM + Husqvarna. Bayiler gömülü JS dizisinde, servisler
    # düz HTML tabloda; ikisi de tek sayfa, il gezmiyor.
    "spormoto": "marka_bazli",
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

    if bicim == "marka_bazli":
        # Birden çok marka, HER MARKANIN KENDİ adresleri:
        #   KAYNAKLAR = {"KTM": {"satis": url, "servis": url}, ...}
        # cok_marka biçimi tek kaynağı paylaştırıyor, burada olmaz.
        for marka, roller in mod.KAYNAKLAR.items():
            for rol, url in roller.items():
                out.append((marka, rol, url, ""))
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
                iller = mod.il_sluglari(_en_iyi_coz(y, None))
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
                iller = mod.il_sluglari(_en_iyi_coz(y, None))
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
                    iller = mod.il_sluglari(_en_iyi_coz(y, None))
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
            govde = _en_iyi_coz(ilk, None)
        except Exception as e:  # noqa: BLE001
            log(f"    ✗ {mod.MARKA}/{rol}: {str(e)[:60]}")
            continue

        for deger, il_adi in mod.il_secenekleri(govde):
            denendi += 1
            try:
                y = oturum.post(url, data=mod.post_govdesi(govde, deger),
                                timeout=60, headers={"Referer": url})
                y.raise_for_status()
                govde = _en_iyi_coz(y, None)   # zincir: sonraki ViewState
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


def _uyar(metin: str) -> None:
    """GitHub Actions iş uyarısı: günlüğe erişemediğimizde tek okunur kanal."""
    print(f"::warning::[ozel_tara] {metin}", flush=True)


def marka_tara(mod_ad: str, log=print) -> dict[str, list[dict]]:
    """Modülü tarar; modül son_isle() tanımladıysa sonucu ondan geçirir.

    son_isle marka bazında, satış ve servis listelerinin İKİSİ de
    toplandıktan sonra çalışır (ör. Kuralkan'da ada göre rol birleştirme).
    """
    toplam = _marka_tara(mod_ad, log)
    mod = importlib.import_module(f"ozel.{mod_ad}")
    if hasattr(mod, "son_isle"):
        for marka in list(toplam):
            once = len(toplam[marka])
            toplam[marka] = mod.son_isle(toplam[marka])
            log(f"  {marka}: son işlem {once} -> {len(toplam[marka])} kayıt")
    return toplam


def _marka_tara(mod_ad: str, log=print) -> dict[str, list[dict]]:
    mod = importlib.import_module(f"ozel.{mod_ad}")
    if GEZINME.get(mod_ad) == "postback":
        toplam, kapsam = _postback_tara(mod_ad, mod, log)
        for marka in toplam:
            log(f"  {marka}: {len(toplam[marka])} kayıt (kapsam %{kapsam*100:.0f})")
        return toplam
    kodlama = getattr(mod, "KODLAMA", None)
    oturum = requests.Session()
    oturum.headers.update(BASLIK)
    # JSON uçları için: bazı API'ler (Next.js) Accept başlığına göre HTML
    # ya da JSON döndürüyor. Modül JSON_UC=True derse JSON istiyoruz.
    if getattr(mod, "JSON_UC", False):
        oturum.headers.update({"Accept": "application/json, text/plain, */*",
                               "X-Requested-With": "XMLHttpRequest"})
    # Modülün istediği ek başlıklar (ör. Acco'nun genel mağaza anahtarı)
    oturum.headers.update(getattr(mod, "BASLIKLAR", {}) or {})

    toplam: dict[str, list[dict]] = {}
    denendi = basarili = 0
    ilk_il_kotu = 0

    # KENDİ İSTEĞİNİ ATAN MODÜL: bazı uçlar GET değil POST + JSON gövde
    # istiyor (TVS'nin dealer-search ucu kategoriyi gövdede alıyor).
    # Modül getir(oturum) tanımladıysa çekme işi ona bırakılıyor.
    if hasattr(mod, "getir"):
        marka = getattr(mod, "MARKA", mod_ad)
        try:
            ham = mod.getir(oturum)
        except Exception as e:  # noqa: BLE001
            log(f"    ✗ {marka}: {str(e)[:80]}")
            return {}
        # FINALIZE ŞART: normalleştirme, il/ilçe çözümü, metin temizliği ve
        # telefon biçimi burada yapılıyor. Atlanırsa yazma aşaması patlıyor.
        kayitlar = []
        for r in ham:
            k = finalize(dict(r), marka, getattr(mod, "UC", ""), {})
            if k:
                kayitlar.append(k)
        log(f"    → {marka}: {len(kayitlar)} kayıt (modül kendi çekti)")
        return {marka: kayitlar} if kayitlar else {}

    for marka, rol, url, il in _hedefler(mod_ad, mod):
        denendi += 1
        try:
            y = oturum.get(url, timeout=60)
            if y.status_code >= 400:
                raise RuntimeError(f"HTTP {y.status_code}")
            govde = _en_iyi_coz(y, kodlama)
        except Exception as e:  # noqa: BLE001
            log(f"    ✗ {marka}/{rol}/{il or '-'}: {str(e)[:50]}")
            _uyar(f"{marka}/{rol}/{il or '-'} çekilemedi: {str(e)[:120]}")
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
            _uyar(f"{marka}/{il or '-'} ayrıştırma hatası: {str(e)[:120]}")
            continue

        if not ham:
            # Sayfa geldi ama kayıt çıkmadı: en sık karşılaşılan sessiz hata.
            # Gövdenin başını uyarıya koyuyoruz ki ne döndüğü görülsün.
            _uyar(f"{marka}/{rol}/{il or '-'} sayfa geldi ({len(govde)} karakter) ama "
                  f"kayıt çıkmadı. Başı: {govde[:160]!r}")
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
    # --db ile başka veritabanına yazılabilir. Gece taraması sonucu
    # canlıya değil bayiler_yeni.db'ye gidiyor; önizlemede kontrol
    # edildikten sonra canlıya alınıyor.
    db_yolu = "bayiler.db"
    if "--db" in sys.argv:
        db_yolu = sys.argv[sys.argv.index("--db") + 1]
    istenen = [a for a in sys.argv[1:]
               if not a.startswith("-") and a != db_yolu]
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
                with db(db_yolu) as con:
                    r["db"] = str(commit_tarama(con, marka, kayitlar, 1.0, basladi))[:180]
            rapor[marka] = r
            print(f"  → {marka}: {json.dumps(r, ensure_ascii=False)[:150]}")

    Path("ham").mkdir(exist_ok=True)
    Path("ham/ozel-tarama.json").write_text(
        json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n" + json.dumps(rapor, ensure_ascii=False, indent=1)[:1500])


if __name__ == "__main__":
    main()
