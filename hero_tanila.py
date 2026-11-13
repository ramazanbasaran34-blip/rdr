#!/usr/bin/env python3
"""Hero — sayfayı insan gibi gezip ne olduğunu GÖZLEMLER.

Amaç veri toplamak değil, Cloudflare'in tam olarak neye takıldığını
görmek. Üç yaklaşımı sırayla deniyor ve her adımda ne olduğunu yazıyor:

  A) Gerçek kullanıcı gibi: fareyle oynat, kaydır, seçeneği tıklayarak
     seç, düğmeye bas. Aceleci otomasyon kalıbından kaçınır.
  B) Aynı sekmeden XHR (POST).
  C) Adres satırından GET.

Ayrıca sayfanın form yapısını ve gelen yanıtı kaydediyor ki yöntem
seçimini tahminle değil, gözlemle yapalım.
"""

from __future__ import annotations

import gzip
import json
import random
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

CIKTI = Path("ham")
URL = "https://www.heromotor.com.tr/bayiler/"

KULLANICI = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

TEL = re.compile(r"0\s*\(?\d{3}\)?[\s\-/]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}")


def bekleme(a=0.4, b=1.3) -> None:
    """İnsan gibi düzensiz bekleme."""
    time.sleep(random.uniform(a, b))


def engel_mi(sayfa) -> bool:
    b = (sayfa.title() or "").lower()
    return ("just a moment" in b or "bir dakika" in b
            or "attention required" in b or "checking your browser" in b)


def engeli_gec(sayfa, azami=70) -> bool:
    """Doğrulamayı bekler; gerekirse kutucuğa tıklar."""
    for i in range(azami):
        if not engel_mi(sayfa):
            return True
        # Turnstile kutucuğu bir iframe içinde; varsa tıkla
        try:
            for cerceve in sayfa.frames:
                if "challenges.cloudflare.com" in (cerceve.url or ""):
                    try:
                        cerceve.click("input[type=checkbox], .cb-lb, body", timeout=1500)
                    except Exception:  # noqa: BLE001
                        pass
        except Exception:  # noqa: BLE001
            pass
        if i and i % 25 == 0:
            try:
                sayfa.reload(wait_until="domcontentloaded")
            except Exception:  # noqa: BLE001
                pass
        sayfa.wait_for_timeout(1000)
    return not engel_mi(sayfa)


def insan_gibi(sayfa) -> None:
    """Fare hareketi + kaydırma. Otomasyon kalıbını yumuşatır."""
    try:
        for _ in range(3):
            sayfa.mouse.move(random.randint(80, 1200), random.randint(80, 700),
                             steps=random.randint(5, 15))
            bekleme(0.15, 0.5)
        sayfa.mouse.wheel(0, random.randint(200, 600))
        bekleme()
        sayfa.mouse.wheel(0, -random.randint(80, 250))
        bekleme()
    except Exception:  # noqa: BLE001
        pass


def form_bilgisi(sayfa) -> dict:
    return sayfa.evaluate("""() => {
      const f = document.querySelector('select[name=city_box]');
      const form = f ? f.form : null;
      const dugmeler = form ? [...form.querySelectorAll('input,button')]
        .map(e => ({etiket: e.tagName, tur: e.type, ad: e.name, deger: e.value})) : [];
      return {
        formVar: !!form,
        eylem: form ? (form.getAttribute('action') || location.pathname) : null,
        yontem: form ? (form.getAttribute('method') || 'GET').toUpperCase() : null,
        alanlar: dugmeler,
        secenekSayisi: f ? f.options.length : 0
      };
    }""")


def dene_a_insan(sayfa, kod: str) -> str:
    """Gerçek kullanıcı gibi: seç, bekle, düğmeye bas."""
    insan_gibi(sayfa)
    sayfa.click("select[name=city_box]")
    bekleme()
    sayfa.select_option("select[name=city_box]", value=kod)
    bekleme(0.6, 1.6)
    insan_gibi(sayfa)
    for sec in ("input[type=submit]", "button[type=submit]", "input[name=ara]"):
        try:
            sayfa.click(sec, timeout=2500)
            break
        except Exception:  # noqa: BLE001
            continue
    try:
        sayfa.wait_for_load_state("domcontentloaded", timeout=30000)
    except Exception:  # noqa: BLE001
        pass
    engeli_gec(sayfa, azami=40)
    bekleme(0.8, 1.6)
    return sayfa.content()


def dene_b_xhr(sayfa, kod: str) -> str:
    return sayfa.evaluate("""async (kod) => {
      const g = new URLSearchParams({city_box: kod, ara: 'Ara'});
      const y = await fetch(location.href.split('?')[0], {
        method: 'POST', credentials: 'same-origin',
        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        body: g.toString()});
      return await y.text();
    }""", kod)


def dene_c_get(sayfa, kod: str) -> str:
    sayfa.goto(f"{URL}?city_box={kod}&ara=Ara",
               wait_until="domcontentloaded", timeout=45000)
    engeli_gec(sayfa, azami=35)
    return sayfa.content()


def main() -> None:
    CIKTI.mkdir(exist_ok=True)
    rapor: dict = {}

    with sync_playwright() as pw:
        t = pw.chromium.launch(args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-features=IsolateOrigins,site-per-process",
        ])
        ctx = t.new_context(user_agent=KULLANICI, locale="tr-TR",
                            timezone_id="Europe/Istanbul",
                            viewport={"width": 1366, "height": 900})
        # navigator.webdriver izini sil
        ctx.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
        s = ctx.new_page()

        s.goto(URL, wait_until="domcontentloaded", timeout=60000)
        rapor["ilk_engel"] = engel_mi(s)
        gecti = engeli_gec(s)
        rapor["engel_gecildi"] = gecti
        rapor["baslik"] = s.title()
        if not gecti:
            print(json.dumps(rapor, ensure_ascii=False, indent=1))
            (CIKTI / "hero-tanilama.json").write_text(
                json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")
            return

        rapor["form"] = form_bilgisi(s)
        print("form:", json.dumps(rapor["form"], ensure_ascii=False)[:400])

        kod = "6"   # Ankara
        for ad, fn in (("A_insan", dene_a_insan),
                       ("B_xhr", dene_b_xhr),
                       ("C_get", dene_c_get)):
            try:
                html = fn(s, kod)
            except Exception as e:  # noqa: BLE001
                rapor[ad] = {"hata": f"{type(e).__name__}: {str(e)[:90]}"}
                print(f"  {ad}: HATA {rapor[ad]['hata']}")
                continue

            engel = ("just a moment" in html.lower()
                     or "bir dakika" in html.lower())
            rapor[ad] = {"boyut": len(html), "tel": len(TEL.findall(html)),
                         "engel": engel}
            print(f"  {ad}: {len(html)//1024}KB tel={rapor[ad]['tel']} engel={engel}")
            (CIKTI / f"hero-deneme-{ad}.html.gz").write_bytes(
                gzip.compress(html.encode("utf-8", "replace")))

            # Bir sonraki denemeye temiz başla
            try:
                s.goto(URL, wait_until="domcontentloaded", timeout=45000)
                engeli_gec(s, azami=30)
            except Exception:  # noqa: BLE001
                pass

        ctx.close(); t.close()

    (CIKTI / "hero-tanilama.json").write_text(
        json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rapor, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
