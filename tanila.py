#!/usr/bin/env python3
"""Tanılama — markaların gerçek sayfalarını indirip incelenebilir hale getirir.

Neden gerekli: buradan o sitelere erişemiyorum, dolayısıyla ayrıştırıcıyı
tahminle yazıyordum. Bu araç GitHub sunucusunda çalışıp sayfaları indiriyor,
işe yarar kısımlarını süzüp depoya yazıyor. Böylece gerçek yapıyı görüp
tarifi kesin yazabiliyorum.

Ham HTML'in tamamını değil, bayi kaydı içerdiği anlaşılan bölümü kaydeder —
depoyu şişirmemek için.

Kullanım:
    python tanila.py                       # tüm markalar
    python tanila.py Honda Bajaj Rutec     # seçili markalar
"""

import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

from bayiradar.collect import kaynaklari_coz, load_config
from bayiradar.fetch import Fetcher
from bayiradar.otomatik import (TEL, il_baglantilari, il_secicileri_bul,
                                json_gomulu, kaplari_bul)

CIKTI = Path("tanilama")
AZAMI = 60000        # marka başına kaydedilecek azami karakter


def ozetle(html: str, url: str) -> dict:
    """Sayfanın yapısını çıkarır: ne var, nerede, nasıl."""
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript", "svg"]):
        if t.name == "script" and "NEXT_DATA" in (t.get("id") or ""):
            continue
        t.decompose()

    adaylar = kaplari_bul(soup)
    gomulu = json_gomulu(html)
    secici = il_secicileri_bul(html, url)
    dizin = il_baglantilari(html, url)

    return {
        "url": url,
        "boyut": len(html),
        "telefon_sayisi": len(TEL.findall(soup.get_text(" "))),
        "gomulu_json_kayit": len(gomulu),
        "gomulu_ornek": gomulu[:2],
        "il_secici": len(secici),
        "il_secici_ornek": [u for u, _ in secici[:2]],
        "il_dizini": len(dizin),
        "kap_adaylari": [
            {"secici": _yol(el[2][0]), "adet": el[1], "puan": round(el[0], 1),
             "ornek_metin": [e.get_text(" ", strip=True)[:180] for e in el[2][:2]],
             "ornek_html": str(el[2][0])[:1200]}
            for el in adaylar[:4]
        ],
    }


def _yol(el, derinlik=3):
    parca, cur = [], el
    for _ in range(derinlik):
        if cur is None or cur.name in ("html", "[document]"):
            break
        sinif = [c for c in (cur.get("class") or [])
                 if not re.match(r"^(w|col|row)-?\d", c)][:3]
        parca.append(cur.name + ("." + ".".join(sinif) if sinif else ""))
        cur = cur.parent
    return " > ".join(reversed(parca))


def main():
    conf = load_config()
    markalar = conf["markalar"]
    if len(sys.argv) > 1:
        istenen = [a for a in sys.argv[1:]]
        markalar = {k: v for k, v in markalar.items() if k in istenen}

    CIKTI.mkdir(exist_ok=True)
    f = Fetcher(delay=1.0, use_cache=False)
    rapor = {}

    try:
        for marka, cfg in markalar.items():
            rapor[marka] = []
            for kaynak in kaynaklari_coz(cfg):
                url = kaynak["url"].split("{")[0].rstrip("?&")
                rol = kaynak.get("rol", "satis")
                print(f"→ {marka} [{rol}] {url[:70]}")
                try:
                    if cfg.get("mode") == "browser":
                        html = f.render(url, max_age=0)
                    else:
                        html = f.get(url, max_age=0, encoding=cfg.get("encoding"))
                except Exception as e:                            # noqa: BLE001
                    rapor[marka].append({"rol": rol, "url": url,
                                         "hata": str(e)[:200]})
                    print(f"   ✗ {str(e)[:70]}")
                    continue
                o = ozetle(html, url)
                o["rol"] = rol
                rapor[marka].append(o)
                print(f"   telefon={o['telefon_sayisi']} json={o['gomulu_json_kayit']} "
                      f"ilSeçici={o['il_secici']} kap={len(o['kap_adaylari'])}")
                # Ham parçayı da kaydet
                if o["kap_adaylari"]:
                    ad = re.sub(r"[^a-z0-9]+", "-", f"{marka}-{rol}".lower())
                    (CIKTI / f"{ad}.html").write_text(
                        "\n\n".join(k["ornek_html"] for k in o["kap_adaylari"][:3])[:AZAMI],
                        encoding="utf-8")
    finally:
        f.close()

    (CIKTI / "rapor.json").write_text(
        json.dumps(rapor, ensure_ascii=False, indent=1)[:900000], encoding="utf-8")
    print(f"\n✓ {len(rapor)} marka incelendi → {CIKTI}/rapor.json")


if __name__ == "__main__":
    main()
