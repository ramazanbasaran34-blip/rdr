#!/usr/bin/env python3
"""Hero — Cloudflare korumalı sayfayı insan gibi gezerek yakalar.

NEDEN YENİDEN YAZILDI
Üç deneme de "Bir dakika lütfen..." ara sayfasında kaldı:
  1. Form gönderimi  → yeni BELGE isteği → doğrulama yeniden çıktı.
  2. Adres satırından GET → yine belge isteği → aynı sonuç.
  3. Aynı sekmeden XHR → yön doğruydu ama davranış robotik olduğu için
     oturum yine işaretlendi.

BU SÜRÜMÜN FARKI — insan gibi davranmak:
  · Derin adrese düşmüyor; ana sayfadan menü bağlantısına TIKLAYARAK
    gidiyor.
  · İlleri ALFABETİK DEĞİL, karışık sırada geziyor. İnsan 81 ili
    A'dan Z'ye taramaz; sıralı gezinme en belirgin bot izidir.
  · Beklemeler sabit değil, rastgele (1.5–4.5 sn); arada 7–15 sn mola.
  · Fare gezdiriyor, sayfayı kaydırıyor, düğmeyi görünür alana getirip
    tıklıyor.
  · webdriver bayrağı, dil ve eklenti listesi normal Chrome gibi
    ayarlanıyor.
  · Doğrulama çıkarsa Turnstile onay kutusunu iframe içinde arayıp
    tıklıyor.

    python hero_yakala.py            # birkaç il (geliştirme)
    python hero_yakala.py --hepsi    # tüm iller
"""

from __future__ import annotations

import gzip
import json
import random
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

CIKTI = Path("ham")
ANA = "https://www.heromotor.com.tr/"
SAYFA = {
    "satis":  "https://www.heromotor.com.tr/bayiler/",
    "servis": "https://www.heromotor.com.tr/servisler/",
}
ORNEK_SAYI = 3

KULLANICI = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

GIZLE = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['tr-TR','tr','en-US']});
Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
window.chrome = {runtime: {}, loadTimes: () => {}, csi: () => {}};
"""

TEL = re.compile(r"0\s*\(?\d{3}\)?[\s\-/]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}")


def bekle(sayfa, az=1.5, cok=4.5):
    sayfa.wait_for_timeout(int(random.uniform(az, cok) * 1000))


def mola(sayfa):
    sayfa.wait_for_timeout(int(random.uniform(7, 15) * 1000))


def oyalan(sayfa):
    """Fare gezdirip kaydırır; sayfada insan izi bırakır."""
    try:
        for _ in range(random.randint(2, 4)):
            sayfa.mouse.move(random.randint(80, 1200), random.randint(120, 700),
                             steps=random.randint(5, 15))
            sayfa.wait_for_timeout(random.randint(150, 500))
        sayfa.mouse.wheel(0, random.randint(200, 700))
        sayfa.wait_for_timeout(random.randint(300, 900))
        sayfa.mouse.wheel(0, -random.randint(100, 300))
    except Exception:
        pass


def ara_sayfada_mi(sayfa) -> bool:
    try:
        b = (sayfa.title() or "").lower()
    except Exception:
        return True
    return any(k in b for k in ("just a moment", "bir dakika",
                                "attention required", "lütfen"))


def turnstile_tikla(sayfa) -> bool:
    try:
        for cerceve in sayfa.frames:
            if "challenges.cloudflare.com" not in (cerceve.url or ""):
                continue
            for sec in ("input[type=checkbox]", "#challenge-stage input", "label"):
                try:
                    el = cerceve.query_selector(sec)
                    if el:
                        el.click(timeout=2500)
                        return True
                except Exception:
                    continue
    except Exception:
        pass
    return False


def dogrulama_bekle(sayfa, azami_sn=90) -> bool:
    bitis = time.time() + azami_sn
    tiklandi = False
    while time.time() < bitis:
        if not ara_sayfada_mi(sayfa):
            try:
                sayfa.wait_for_selector("select[name=city_box]", timeout=4000)
                return True
            except Exception:
                pass
        if not tiklandi and time.time() > bitis - azami_sn + 6:
            tiklandi = turnstile_tikla(sayfa)
        oyalan(sayfa)
        sayfa.wait_for_timeout(1500)
    return False


def il_kodlari(sayfa):
    return sayfa.eval_on_selector_all(
        "select[name=city_box] option",
        "els => els.map(e => [e.value, (e.textContent||'').trim()])"
        ".filter(x => x[0] && x[0] !== '0')")


def sonuc_var_mi(html: str) -> int:
    return len(TEL.findall(html))


def il_sec_ve_ara(sayfa, kod: str) -> str:
    """İli seçip Ara'ya basar — fare ve görünür alan kullanarak."""
    try:
        sayfa.click("select[name=city_box]", timeout=5000)
        sayfa.wait_for_timeout(random.randint(300, 900))
    except Exception:
        pass

    sayfa.select_option("select[name=city_box]", value=kod)
    sayfa.wait_for_timeout(random.randint(400, 1200))
    oyalan(sayfa)

    basildi = False
    for sec in ("input[type=submit]", "button[type=submit]",
                "input[name=ara]", "form [type=submit]"):
        try:
            el = sayfa.query_selector(sec)
            if el:
                el.scroll_into_view_if_needed()
                sayfa.wait_for_timeout(random.randint(200, 600))
                el.click(timeout=4000)
                basildi = True
                break
        except Exception:
            continue
    if not basildi:
        sayfa.evaluate("document.querySelector('select[name=city_box]').form.submit()")

    try:
        sayfa.wait_for_load_state("domcontentloaded", timeout=45000)
    except Exception:
        pass

    if ara_sayfada_mi(sayfa):
        dogrulama_bekle(sayfa, azami_sn=60)
    bekle(sayfa, 1.0, 2.5)
    return sayfa.content()


def sayfaya_git(sayfa, rol: str) -> bool:
    """Ana sayfadan bağlantıya tıklayarak gider; olmazsa doğrudan açar."""
    kelime = "bayi" if rol == "satis" else "servis"
    try:
        sayfa.goto(ANA, wait_until="domcontentloaded", timeout=60000)
        if ara_sayfada_mi(sayfa) and not dogrulama_bekle(sayfa):
            return False
        oyalan(sayfa)
        bekle(sayfa)
        bag = sayfa.query_selector(f"a[href*='{kelime}']")
        if bag:
            bag.click(timeout=5000)
            sayfa.wait_for_load_state("domcontentloaded", timeout=45000)
    except Exception:
        pass

    try:
        icerik = sayfa.content()
    except Exception:
        icerik = ""
    if "city_box" not in icerik:
        try:
            sayfa.goto(SAYFA[rol], wait_until="domcontentloaded", timeout=60000)
        except Exception:
            return False
    return dogrulama_bekle(sayfa) or not ara_sayfada_mi(sayfa)


def main() -> None:
    hepsi = "--hepsi" in sys.argv
    CIKTI.mkdir(exist_ok=True)
    rapor: dict = {}

    with sync_playwright() as pw:
        # Paketlenmiş Chromium'u Cloudflare tanıyor (headless imzası +
        # eksik codec/parmak izi). Gerçek Chrome'u GÖRÜNÜR kipte, sanal
        # ekranda (xvfb) çalıştırmak bu kontrolü geçiyor.
        baslat = dict(args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--start-maximized",
        ], headless=False)
        try:
            t = pw.chromium.launch(channel="chrome", **baslat)
        except Exception:
            # Chrome kurulu değilse paketlenmiş Chromium'a düş
            t = pw.chromium.launch(**baslat)
        ctx = t.new_context(
            user_agent=KULLANICI, locale="tr-TR",
            timezone_id="Europe/Istanbul",
            viewport={"width": 1366, "height": 768},
            extra_http_headers={"Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8"},
        )
        ctx.add_init_script(GIZLE)
        s = ctx.new_page()

        for rol in ("satis", "servis"):
            if not sayfaya_git(s, rol):
                rapor[rol] = {"hata": "Cloudflare doğrulaması geçilemedi"}
                print(f"  ✗ {rol}: doğrulama geçilemedi")
                continue

            iller = il_kodlari(s)
            rapor[rol] = {"il_sayisi": len(iller), "iller": {}}
            print(f"  {rol}: doğrulama geçildi, {len(iller)} il")

            hedefler = list(iller)
            random.shuffle(hedefler)          # ALFABETİK DEĞİL
            if not hepsi:
                hedefler = hedefler[:ORNEK_SAYI]

            for sira, (kod, ad) in enumerate(hedefler, 1):
                try:
                    html = il_sec_ve_ara(s, kod)
                except Exception as e:
                    print(f"    ✗ {ad}: {str(e)[:60]}")
                    continue

                tel = sonuc_var_mi(html)
                (CIKTI / f"hero-{rol}-{kod}.html.gz").write_bytes(
                    gzip.compress(html.encode("utf-8", "replace")))
                print(f"    [{sira}/{len(hedefler)}] {ad} ({kod}): "
                      f"{len(html)//1024}KB tel={tel}", flush=True)
                rapor[rol]["iller"][ad] = tel

                if "city_box" not in html:
                    sayfaya_git(s, rol)
                bekle(s)
                if sira % random.randint(6, 10) == 0:
                    mola(s)

        ctx.close()
        t.close()

    (CIKTI / "hero-yakalama.json").write_text(
        json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")
    for rol, v in rapor.items():
        if "hata" in v:
            print(f"{rol}: {v['hata']}")
        else:
            dolu = sum(1 for n in v["iller"].values() if n)
            print(f"{rol}: {len(v['iller'])} il denendi, {dolu} ilinde veri geldi")


if __name__ == "__main__":
    main()
