#!/usr/bin/env python3
"""Hero — statik dosyalar ve olası AJAX uçları erişilebilir mi?

FİKİR
Cloudflare doğrulaması genelde HTML BELGE isteklerine uygulanır; JS, CSS,
resim gibi statik dosyalar çoğu zaman serbest geçer. Eğer öyleyse sitenin
JavaScript dosyasını okuyup bayi aramasının hangi adrese istek attığını
bulabiliriz. Bulunca o adrese doğrudan gidip 81 ili tararız ve Hero da
diğer markalar gibi otomatik güncellenir.

Bu betik hiçbir doğrulama atlatmaya çalışmıyor; sadece hangi yolların
zaten açık olduğunu ölçüyor.

    python hero_sonda.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import requests

KOK = "https://www.heromotor.com.tr"
BASLIK = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "*/*",
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Referer": KOK + "/",
}

# 1) Statik dosyalar serbest mi? (sayfada geçtiğini bildiğimiz dosyalar)
STATIK = [
    "/images/ajax-loader-small.gif",
    "/design/hero-logo-lg.png",
    "/design/dealer.png",
    "/images/search-icon.gif",
]

# 2) JS dosyası nerede? Yaygın yollar denenir.
# GERÇEK dosya adları — kullanıcının view-source ekran görüntülerinden.
# Tahminle aranınca bulunamıyordu; bunlar sayfada <script src=> ile yüklü.
JS_ADAYLARI = [
    "/js/jquery.min.js", "/js/jquery.easing.1.3.js", "/js/nav-bikes.js",
    "/js/milestones.js", "/js/social-details.js", "/js/jquery.bxslider.js",
    "/js/ddaccordion.js", "/js/organictabs.jquery.click.js",
    "/js/jquery.magnific-popup.js", "/js/scroll-top.js",
    "/js/waypoints.min.js", "/js/jquery.counterup.js",
    "/js/jquery.flexslider.js", "/js/contentslider.js", "/js/spritespin.js",
]

# 3) Olası AJAX uçları (site /inc/price.php kullanıyor, aynı klasör mantığı)
UC_ADAYLARI = [
    "/inc/dealer.php?city=10", "/inc/bayi.php?city=10",
    "/inc/dealers.php?city=10", "/inc/servis.php?city=10",
    "/inc/service.php?city=10", "/inc/bayiara.php?city=10",
    "/inc/dealer.php?city_box=10", "/inc/bayi.php?city_box=10",
    "/ajax/dealer.php?city=10", "/ajax/bayi.php?city=10",
    "/inc/price.php?id=31",
]

TEL = re.compile(r"0\s*\(?\d{3}\)?[\s\-/]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}")


def dene(o, yol: str) -> dict:
    try:
        y = o.get(KOK + yol, timeout=30, allow_redirects=False)
    except Exception as e:  # noqa: BLE001
        return {"yol": yol, "hata": f"{type(e).__name__}"}
    b = {"yol": yol, "kod": y.status_code, "boyut": len(y.content),
         "tip": y.headers.get("content-type", "")[:34]}
    if y.status_code in (301, 302):
        b["yonlendi"] = y.headers.get("location", "")[:60]
    if "text" in b["tip"] or "json" in b["tip"] or "javascript" in b["tip"]:
        b["tel"] = len(TEL.findall(y.text))
        b["ilk"] = re.sub(r"\s+", " ", y.text[:90])
    return b


def main() -> None:
    o = requests.Session()
    o.headers.update(BASLIK)
    rapor: dict = {}

    print("=== 1) STATİK DOSYALAR (Cloudflare bunları geçiriyor mu?) ===")
    rapor["statik"] = [dene(o, p) for p in STATIK]
    for b in rapor["statik"]:
        print(f"  {b.get('kod','-'):>4}  {b['boyut'] if 'boyut' in b else '':>7}  {b['yol']}")

    acik = any(b.get("kod") == 200 for b in rapor["statik"])
    print(f"\n  → statik dosyalar {'AÇIK' if acik else 'kapalı'}")

    print("\n=== 2) JS DOSYASI ARANIYOR ===")
    rapor["js"] = []
    for p in JS_ADAYLARI:
        b = dene(o, p)
        rapor["js"].append(b)
        if b.get("kod") == 200 and b.get("boyut", 0) > 200:
            print(f"  ✓ BULUNDU {b['kod']} {b['boyut']}B  {p}")
            # İçinde .php geçen adresleri çıkar
            try:
                y = o.get(KOK + p, timeout=30)
                uclar = sorted(set(re.findall(r"[\w./\-]*\.php[\w?=&]*", y.text)))
                if uclar:
                    b["php_adresleri"] = uclar[:20]
                    print(f"      php adresleri: {uclar[:12]}")
                # Bayi arama işini yapan kod bu anahtarları içerir
                for anahtar in ("bayi_quey_form", "bayi_city_box",
                                "bayi_content", "servis_quey_form",
                                "servis_city_box", "servis_content"):
                    if anahtar in y.text:
                        i = y.text.find(anahtar)
                        parca = re.sub(r"\s+", " ", y.text[max(0, i-260):i+360])
                        b.setdefault("bulgular", []).append(
                            {"anahtar": anahtar, "parca": parca})
                        print(f"      ★ {anahtar} BULUNDU")
                        print(f"        {parca[:300]}")
            except Exception:  # noqa: BLE001
                pass
        else:
            print(f"    {b.get('kod','-'):>4}  {p}")

    print("\n=== 3) OLASI AJAX UÇLARI ===")
    rapor["uclar"] = []
    for p in UC_ADAYLARI:
        b = dene(o, p)
        rapor["uclar"].append(b)
        isaret = "✓" if (b.get("kod") == 200 and b.get("tel", 0) > 0) else " "
        print(f"  {isaret} {b.get('kod','-'):>4} tel={b.get('tel','-'):>3} {p}")
        if b.get("tel"):
            print(f"      {b.get('ilk','')[:80]}")

    Path("ham").mkdir(exist_ok=True)
    Path("ham/hero-sonda.json").write_text(
        json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
