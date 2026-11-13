#!/usr/bin/env python3
"""Sayfa yakalama — markaların gerçek sayfalarını bir kez indirip saklar.

Amaç: ayrıştırıcıyı tarama yaparak değil, kaydedilmiş sayfalar üzerinde
geliştirmek. Böylece her deneme saatler değil saniyeler sürüyor ve sitelere
tekrar tekrar gidilmiyor.

Her marka-rol için bayi listesini içeren bölgeyi kaydeder. Script, stil ve
görsel etiketleri atılır — sadece yapı ve metin kalır.

Kullanım:
    python yakala.py                    # tüm markalar
    python yakala.py Honda Bajaj        # seçili markalar
"""

import gzip
import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

from bayiradar.collect import kaynaklari_coz, load_config
from bayiradar.fetch import Fetcher
from bayiradar.otomatik import TEL, il_baglantilari, il_secicileri_bul, kaplari_bul

CIKTI = Path("yakalanan")
# Sıkıştırma öncesi azami karakter. Derin keşif Zelsun'da 21.494, Arora'da
# 3.754 telefon buldu; 400 KB sınırı bu sayfaları ortadan kesiyordu.
AZAMI = 4_000_000
COP_ETIKET = ["script", "style", "noscript", "svg", "iframe", "picture",
              "source", "video", "audio", "canvas", "template"]


def temizle(html: str) -> str:
    """Sayfayı sadeleştir: kod, stil, görsel çıkar; yapı ve metin kalsın."""
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(COP_ETIKET):
        t.decompose()
    for t in soup.find_all(True):
        # Görsel/erişilebilirlik özniteliklerini at, class ve id kalsın
        for oz in list(t.attrs):
            if oz not in ("class", "id", "href", "data-il", "data-city",
                          "value", "name", "type"):
                del t.attrs[oz]
    return str(soup)


def ilgili_bolge(html: str) -> str:
    """Bayi listesini içeren bölgeyi döner.

    Kırpma agresifti: en iyi kabın atası alınıyordu ve sayfanın kalanı
    atılıyordu. Ayrıştırıcı bu yüzden veriyi göremiyordu. Artık telefon
    sayısı korunuyor mu diye kontrol ediyor, kaybediyorsa tüm gövdeyi veriyor.
    """
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(COP_ETIKET):
        t.decompose()
    govde = temizle(str(soup.body or soup))
    tam_tel = len(TEL.findall(BeautifulSoup(govde, "html.parser").get_text(" ")))

    adaylar = kaplari_bul(soup)
    if adaylar:
        en_iyi = adaylar[0][2][0]
        kap = en_iyi.parent or en_iyi
        for _ in range(3):
            if kap.parent and len(str(kap)) < AZAMI // 2:
                kap = kap.parent
            else:
                break
        parca = temizle(str(kap))
        parca_tel = len(TEL.findall(BeautifulSoup(parca, "html.parser").get_text(" ")))
        # Kırpılmış bölge telefonların %90'ını koruyorsa onu kullan
        if tam_tel and parca_tel >= tam_tel * 0.9:
            return parca[:AZAMI]
    return govde[:AZAMI]


def main():
    conf = load_config()
    markalar = conf["markalar"]
    if len(sys.argv) > 1:
        markalar = {k: v for k, v in markalar.items() if k in sys.argv[1:]}

    CIKTI.mkdir(exist_ok=True)
    f = Fetcher(delay=1.5, use_cache=False, timeout=45)
    ozet = {}

    try:
        for marka, cfg in markalar.items():
            for kaynak in kaynaklari_coz(cfg):
                rol = kaynak.get("rol", "satis")
                ad = re.sub(r"[^a-z0-9]+", "-", f"{marka}-{rol}".lower()).strip("-")
                temel = kaynak["url"].split("{")[0].rstrip("?&")
                bilgi = {"marka": marka, "rol": rol, "url": temel}
                print(f"→ {marka} [{rol}]")

                # Her zaman gerçek tarayıcıyla: nihai DOM lazım
                try:
                    html = f.render(temel, max_age=0, wait_ms=6000)
                except Exception as e:                            # noqa: BLE001
                    bilgi["hata"] = str(e)[:200]
                    ozet[ad] = bilgi
                    print(f"   ✗ {str(e)[:70]}")
                    continue

                bilgi["boyut"] = len(html)
                bilgi["telefon"] = len(TEL.findall(BeautifulSoup(html, "html.parser").get_text(" ")))
                il_urls = il_secicileri_bul(html, temel)
                bilgi["il_secici"] = len(il_urls)
                bilgi["il_dizini"] = len(il_baglantilari(html, temel))

                # Temel sayfa boşsa il seçimi gerekiyor demektir.
                #
                # Önce URL parametresiyle dene (hızlı). Olmazsa sayfayı
                # gerçekten kullan: listeden il seç, arama düğmesine bas.
                # Ayrıştırıcıyı bu HTML'e karşı geliştireceğim için asıl
                # önemli olan bu — veri gelen halini kaydetmek.
                if bilgi["telefon"] < 5 and il_urls:
                    hedef = next((u for u, i in il_urls if i == "İstanbul"),
                                 il_urls[0][0])
                    try:
                        html2 = f.render(hedef, max_age=0, wait_ms=6000)
                        t2 = len(TEL.findall(
                            BeautifulSoup(html2, "html.parser").get_text(" ")))
                        if t2 > bilgi["telefon"]:
                            html, bilgi["telefon"] = html2, t2
                            bilgi["yontem"] = "url_parametresi"
                            bilgi["ornek_il_url"] = hedef
                    except Exception:                             # noqa: BLE001
                        pass

                if bilgi["telefon"] < 5:
                    try:
                        sayfalar = f.il_secerek_gez(temel, log=lambda m: None,
                                                    azami_saniye=180)
                        en_iyi, en_tel = None, 0
                        for il_adi, sayfa in sayfalar[:6]:
                            t3 = len(TEL.findall(
                                BeautifulSoup(sayfa, "html.parser").get_text(" ")))
                            if t3 > en_tel:
                                en_iyi, en_tel = (il_adi, sayfa), t3
                        if en_iyi and en_tel > bilgi["telefon"]:
                            html, bilgi["telefon"] = en_iyi[1], en_tel
                            bilgi["yontem"] = "il_secerek"
                            bilgi["ornek_il"] = en_iyi[0]
                    except Exception as e:                        # noqa: BLE001
                        bilgi["secim_hatasi"] = str(e)[:120]

                bolge = ilgili_bolge(html)
                (CIKTI / f"{ad}.html.gz").write_bytes(
                    gzip.compress(bolge.encode("utf-8")))
                bilgi["kaydedilen"] = len(bolge)
                ozet[ad] = bilgi
                print(f"   tel={bilgi['telefon']} ilSeçici={bilgi['il_secici']} "
                      f"kayıt={len(bolge)//1024}KB")
    finally:
        f.close()

    (CIKTI / "ozet.json").write_text(
        json.dumps(ozet, ensure_ascii=False, indent=1), encoding="utf-8")
    basarili = sum(1 for v in ozet.values() if "hata" not in v)
    print(f"\n✓ {basarili}/{len(ozet)} sayfa yakalandı → {CIKTI}/")


if __name__ == "__main__":
    main()
