#!/usr/bin/env python3
"""Öncelikli markalar için marka bazlı toplayıcılar.

Her marka ayrı bir fonksiyon. Sebebi basit: siteler birbirine hiç benzemiyor.
Tek bir genel çözücü hepsini kaldıramıyor, zorlayınca da sessizce eksik veri
üretiyor — projede en pahalıya mal olan hata tipi bu.

Çözülen yapılar:
  Kral      · sayfaya gömülü düz JSON dizisi (ad/adres/ilçe/il/telefon hazır)
  Musatti   · GET /ajax-bayi-listesi.php?city=<plaka> → JSON
  Falcon    · GET /api/bayiler.php → JSON
  Vespa     · gömülü GeoJSON (Piaggio grubu; Kymco ile aynı kalıp)
  Aprilia   · aynı
  Piaggio   · aynı

Önce kaydedilmiş HTML üzerinde test edilir, ağ gerekmez:

    python marka_tara.py --test            # ham/ dosyalarıyla dene
    python marka_tara.py --kuru            # canlı çek, veritabanına YAZMA
    python marka_tara.py                   # canlı çek + işle
    python marka_tara.py --test Kral       # tek marka
"""

from __future__ import annotations

import gzip
import json
import re
import sys
import time
from pathlib import Path

import requests

from bayiradar.parse import finalize

HAM = Path("ham")

BASLIK = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9",
}

# Piaggio grubu + Kymco: tek tırnaklı gömülü GeoJSON
GEO_KAYIT = r"\{\s*'type':\s*'yetkili-[a-z]+',.*?'msx':\s*'.*?'\s*\}\s*\}"
GEO_ROL = {"yetkili-satici": "satis", "yetkili-servis": "servis",
           "yetkili-satici-servis": "satis_servis"}


def _t(x) -> str:
    return re.sub(r"\s+", " ", str(x or "")).strip()


# ------------------------------------------------------------------ Kral
def kral_coz(html: str) -> list[dict]:
    """Sayfaya gömülü JSON dizisi. Kayıtlar {"id":..,"name":..} biçiminde."""
    out, gorulen = [], set()
    for m in re.finditer(r'\{"id":\d+,"name":.*?"isActive":(?:true|false)[^}]*\}', html, re.S):
        try:
            d = json.loads(m.group(0))
        except Exception:  # noqa: BLE001
            continue
        if d.get("isActive") is False or d.get("id") in gorulen:
            continue
        gorulen.add(d.get("id"))
        tel = _t(d.get("phone1")) or _t(d.get("phone2"))
        if tel in {"0", "-"}:
            tel = ""
        out.append({"bayi_adi": _t(d.get("name")), "il": _t(d.get("city")),
                    "ilce": _t(d.get("district")), "adres": _t(d.get("address")),
                    "telefon": tel, "email": "", "website": ""})
    return out


# --------------------------------------------------------------- Musatti
def musatti_coz(veri: dict | list) -> list[dict]:
    kayit = veri.get("data") if isinstance(veri, dict) else veri
    if isinstance(kayit, dict):
        kayit = kayit.get("bayiler") or list(kayit.values())
    out = []
    for d in kayit or []:
        if not isinstance(d, dict):
            continue
        ad = _t(d.get("baslik") or d.get("name") or d.get("ad") or d.get("title"))
        if not ad:
            continue
        out.append({
            "bayi_adi": ad,
            "il": _t(d.get("sehir") or d.get("il") or d.get("city")),
            "ilce": _t(d.get("ilce") or d.get("district")),
            "adres": _t(d.get("adres") or d.get("address")),
            "telefon": _t(d.get("telefon") or d.get("phone") or d.get("tel")),
            "email": _t(d.get("email") or d.get("eposta")), "website": ""})
    return out


# ---------------------------------------------------------------- Falcon
def falcon_coz(veri) -> list[dict]:
    kayit = veri
    if isinstance(veri, dict):
        for k in ("data", "bayiler", "items", "result", "records"):
            if isinstance(veri.get(k), list):
                kayit = veri[k]
                break
    out = []
    for d in kayit or []:
        if not isinstance(d, dict):
            continue
        ad = _t(d.get("bayi_adi") or d.get("name") or d.get("baslik")
                or d.get("unvan") or d.get("title"))
        if not ad:
            continue
        rol = _t(d.get("tur") or d.get("tip") or d.get("type")).lower()
        r = {"bayi_adi": ad,
             "il": _t(d.get("il") or d.get("sehir") or d.get("city")),
             "ilce": _t(d.get("ilce") or d.get("district")),
             "adres": _t(d.get("adres") or d.get("address")),
             "telefon": _t(d.get("telefon") or d.get("tel") or d.get("phone")),
             "email": _t(d.get("email")), "website": ""}
        if "servis" in rol and "sat" in rol:
            r["rol"] = "satis_servis"
        elif "servis" in rol:
            r["rol"] = "servis"
        elif "sat" in rol or "bayi" in rol:
            r["rol"] = "satis"
        out.append(r)
    return out


# ------------------------------------------------------- Piaggio grubu
def geo_coz(html: str, varsayilan_rol: str) -> list[dict]:
    def al(blok, anahtar):
        m = re.search(r"'" + anahtar + r"':\s*'(.*?)'", blok, re.S)
        return _t(m.group(1)) if m else ""

    out = []
    for m in re.finditer(GEO_KAYIT, html, re.S):
        blok = m.group(0)
        ad = al(blok, "name")
        if not ad:
            continue
        tip = re.search(r"'type':\s*'(yetkili-[a-z]+)'", blok)
        out.append({"bayi_adi": ad, "il": "", "ilce": "",
                    "adres": al(blok, "address"), "telefon": al(blok, "phone1"),
                    "email": al(blok, "mail1"), "website": "",
                    "konum": al(blok, "city"),
                    "rol": GEO_ROL.get(tip.group(1) if tip else "", varsayilan_rol)})
    return out


# ------------------------------------------------------------- kaynaklar
GEO_CFG = {"il_ilce_birlesik": "konum"}

MARKALAR: dict[str, dict] = {
    "Kral": {
        "kaynaklar": [{"url": "https://kralmotor.tr/SalesDealer", "rol": "satis",
                       "coz": "kral", "test": "m-kral"}],
        "cfg": {},
    },
    "Musatti": {
        "kaynaklar": [{"url": "https://musattimotor.com/ajax-bayi-listesi.php?city={plaka}",
                       "rol": "satis_servis", "coz": "musatti", "iller": True}],
        "cfg": {},
    },
    "Falcon": {
        "kaynaklar": [{"url": "https://falconmotosiklet.com/api/bayiler.php",
                       "rol": "satis_servis", "coz": "falcon"}],
        "cfg": {},
    },
    "Vespa": {
        "kaynaklar": [
            {"url": "https://www.vespa.com.tr/tr/yetkili-saticilar.html",
             "rol": "satis", "coz": "geo", "test": "m-vespa"},
            {"url": "https://www.vespa.com.tr/tr/yetkili-servisler.html",
             "rol": "servis", "coz": "geo", "test": "vespa-servis"}],
        "cfg": GEO_CFG,
    },
    "Aprilia": {
        "kaynaklar": [
            {"url": "https://www.aprilia.com.tr/tr/yetkili-saticilar.html",
             "rol": "satis", "coz": "geo", "test": "m-aprilia"},
            {"url": "https://www.aprilia.com.tr/tr/yetkili-servisler.html",
             "rol": "servis", "coz": "geo", "test": "aprilia-servis"}],
        "cfg": GEO_CFG,
    },
    "Piaggio": {
        "kaynaklar": [
            {"url": "https://www.piaggio.com.tr/tr/yetkili-saticilar.html",
             "rol": "satis", "coz": "geo", "test": "m-piaggio"},
            {"url": "https://www.piaggio.com.tr/tr/yetkili-servisler.html",
             "rol": "servis", "coz": "geo", "test": "piaggio-servis"}],
        "cfg": GEO_CFG,
    },
}


def _uygula(coz: str, govde, rol: str) -> list[dict]:
    if coz == "kral":
        return kral_coz(govde)
    if coz == "geo":
        return geo_coz(govde, rol)
    if coz == "musatti":
        return musatti_coz(govde)
    if coz == "falcon":
        return falcon_coz(govde)
    raise ValueError(coz)


def kayitlara_cevir(marka: str, ham: list[dict], rol: str, url: str,
                    cfg: dict) -> list[dict]:
    out = []
    for r in ham:
        r.setdefault("rol", rol)
        k = finalize(r, marka, url, cfg)
        if k:
            out.append(k)
    return out


# ------------------------------------------------------------------ test
def test(secili: list[str]) -> int:
    hata = 0
    for marka, ayar in MARKALAR.items():
        if secili and marka not in secili:
            continue
        toplam: list[dict] = []
        for k in ayar["kaynaklar"]:
            if not k.get("test"):
                print(f"  · {marka}/{k['rol']}: canlı uç, testte atlanır")
                continue
            yol = HAM / f"{k['test']}.html.gz"
            if not yol.exists():
                print(f"  · {marka}/{k['rol']}: {yol} yok")
                continue
            govde = gzip.decompress(yol.read_bytes()).decode("utf-8", "replace")
            ham = _uygula(k["coz"], govde, k["rol"])
            kk = kayitlara_cevir(marka, ham, k["rol"], k["url"], ayar["cfg"])
            toplam.extend(kk)
            ilsiz = sum(1 for x in kk if not x.get("il"))
            print(f"  {marka:9} {k['rol']:12} → {len(kk):4} kayıt (ilsiz {ilsiz})")
            for x in kk[:2]:
                print(f"        {x['bayi_adi'][:30]:30} | {x.get('il')} / "
                      f"{x.get('ilce')} | {x.get('telefon')}")
            if not kk:
                print("        ✗ hiç kayıt yok")
                hata += 1
            if ilsiz:
                print(f"        ✗ {ilsiz} kayıtta il yok")
                hata += 1
        if toplam:
            print(f"  {marka:9} TOPLAM {len(toplam)} kayıt, "
                  f"{len({x['il'] for x in toplam if x.get('il')})} il\n")
    return hata


# ----------------------------------------------------------------- canlı
def il_plakalari() -> list[str]:
    return [f"{i:02d}" for i in range(1, 82)]


def canli(secili: list[str], kuru: bool) -> None:
    from bayiradar.store import commit_tarama, db, now

    basladi = now()
    oturum = requests.Session()
    oturum.headers.update(BASLIK)
    rapor: dict = {}

    for marka, ayar in MARKALAR.items():
        if secili and marka not in secili:
            continue
        hepsi: list[dict] = []
        for k in ayar["kaynaklar"]:
            adresler = ([k["url"].format(plaka=p) for p in il_plakalari()]
                        if k.get("iller") else [k["url"]])
            for u in adresler:
                try:
                    y = oturum.get(u, timeout=45)
                    y.raise_for_status()
                    govde = y.json() if k["coz"] in ("musatti", "falcon") else y.text
                except Exception as e:  # noqa: BLE001
                    if not k.get("iller"):
                        print(f"    ✗ {marka} {u[:50]}: {str(e)[:60]}")
                    continue
                ham = _uygula(k["coz"], govde, k["rol"])
                hepsi.extend(kayitlara_cevir(marka, ham, k["rol"], u, ayar["cfg"]))
                if k.get("iller"):
                    time.sleep(0.25)
            print(f"  {marka}/{k['rol']}: {len(hepsi)}")

        rapor[marka] = {"kayit": len(hepsi),
                        "il": len({x.get("il") for x in hepsi if x.get("il")}),
                        "ilsiz": sum(1 for x in hepsi if not x.get("il"))}
        if hepsi and not kuru:
            with db() as con:
                rapor[marka]["db"] = str(commit_tarama(con, marka, hepsi, 1.0,
                                                       basladi))[:200]
    print(json.dumps(rapor, ensure_ascii=False, indent=1))
    HAM.mkdir(exist_ok=True)
    (HAM / "marka-tarama.json").write_text(
        json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")


def main() -> None:
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--test" in sys.argv:
        h = test(argv)
        print("\n✓ test geçti" if not h else f"\n✗ {h} sorun")
        sys.exit(1 if h else 0)
    canli(argv, "--kuru" in sys.argv)


if __name__ == "__main__":
    main()
