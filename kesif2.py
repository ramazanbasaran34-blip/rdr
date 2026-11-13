#!/usr/bin/env python3
"""Derin keşif — sayfanın gerçekte ne yaptığını görür.

Boş kalan markalarda liste sayfa açılınca gelmiyor; kullanıcı il seçip arama
yapınca geliyor. Bu araç bir insanın yapacağını yapar ve HER ADIMDA sayfanın
arkada hangi adresleri çağırdığını kaydeder.

Amaç tarayıcıyla kazımak değil: sayfanın beslendiği adresi bulmak. O adres
bulunursa veriyi doğrudan oradan alırız — hızlı, sağlam, tarayıcısız.

Rapor: kesif/<marka>-<rol>.json
    aglar   : sayfanın çağırdığı adresler, hangisi bayi verisi taşıyor
    secimler: sayfadaki açılır listeler ve seçenekleri
    dugmeler: arama/filtre düğmeleri
    deneme  : il seçilip arama yapıldığında ne oldu

Kullanım:
    python kesif2.py                  # boş markalar
    python kesif2.py Kuba Arora       # seçili markalar
"""

import json
import re
import sys
from pathlib import Path

from bayiradar.collect import kaynaklari_coz, load_config
from bayiradar.normalize import ILLER, fold
from bayiradar.otomatik import TEL

CIKTI = Path("kesif")

# Bayi verisi taşıyan yanıtın belirtileri
VERI_IPUCU = re.compile(
    r"(bayi|dealer|servis|service|nokta|point|shop|store|magaza|"
    r"adres|address|telefon|phone|il\b|ilce|city|district)", re.I)

ARAMA_KALIP = [
    "button[type=submit]", "input[type=submit]",
    "button:has-text('Ara')", "button:has-text('ARA')",
    "button:has-text('Bul')", "button:has-text('Listele')",
    "button:has-text('Göster')", "button:has-text('Sorgula')",
    "a:has-text('Ara')", ".btn-search", "#ara", "#btnAra", ".search-btn",
]


def veri_mi(govde: str) -> tuple[bool, int]:
    """Yanıt bayi verisi taşıyor mu? (evet_mi, tahmini_kayit_sayisi)"""
    if not govde or len(govde) < 60:
        return False, 0
    tel = len(TEL.findall(govde))
    if tel >= 3 and VERI_IPUCU.search(govde):
        return True, tel
    # JSON dizisi olabilir, telefon alanı boş olsa da
    if govde.lstrip().startswith(("[", "{")) and VERI_IPUCU.search(govde):
        try:
            veri = json.loads(govde)
            if isinstance(veri, list) and len(veri) >= 3:
                return True, len(veri)
            if isinstance(veri, dict):
                for v in veri.values():
                    if isinstance(v, list) and len(v) >= 3:
                        return True, len(v)
        except Exception:                                         # noqa: BLE001
            pass
    return False, tel


def incele(page, url, log=print):
    """Sayfayı aç, ağ trafiğini kaydet, il seçip arama yapmayı dene."""
    aglar = []

    def istek_kaydet(yanit):
        try:
            u = yanit.url
            if any(u.endswith(x) for x in
                   (".png", ".jpg", ".jpeg", ".gif", ".svg", ".css",
                    ".woff", ".woff2", ".ttf", ".ico", ".webp", ".mp4")):
                return
            tip = (yanit.headers or {}).get("content-type", "")
            if not any(t in tip for t in ("json", "html", "text", "javascript")):
                return
            govde = ""
            try:
                govde = yanit.text()[:200000]
            except Exception:                                     # noqa: BLE001
                return
            var, adet = veri_mi(govde)
            aglar.append({
                "url": u[:400],
                "method": yanit.request.method,
                "gonderilen": (yanit.request.post_data or "")[:400],
                "tip": tip[:60],
                "boyut": len(govde),
                "veri_mi": var,
                "tahmini_kayit": adet,
                "ornek": govde[:600] if var else "",
            })
        except Exception:                                         # noqa: BLE001
            pass

    page.on("response", istek_kaydet)
    page.goto(url, timeout=45000, wait_until="domcontentloaded")
    try:
        page.wait_for_load_state("networkidle", timeout=20000)
    except Exception:                                             # noqa: BLE001
        pass
    page.wait_for_timeout(2500)

    rapor = {"url": url, "acilis_telefon": len(TEL.findall(page.content()))}

    # --- Açılır listeler ---
    il_fold = {fold(i) for i in ILLER}
    secimler = []
    for i, sec in enumerate(page.query_selector_all("select")):
        secenekler = []
        for o in sec.query_selector_all("option"):
            d = (o.get_attribute("value") or "").strip()
            # inner_text() <option> üzerinde BOŞ döner: seçenekler ekranda
            # çizilmiyor. text_content() kullanmak şart — bu hata yüzünden
            # il listeleri hiç tanınmıyordu.
            m = (o.text_content() or "").strip()
            if d and d.lower() not in ("", "0", "-1"):
                secenekler.append({"deger": d, "metin": m[:40]})
        il_sayisi = sum(1 for x in secenekler if fold(x["metin"]) in il_fold)
        secimler.append({
            "sira": i,
            "name": sec.get_attribute("name") or "",
            "id": sec.get_attribute("id") or "",
            "secenek": len(secenekler),
            "il_sayisi": il_sayisi,
            "ornek": secenekler[:4],
        })
    rapor["secimler"] = secimler

    # --- Düğmeler ---
    dugmeler = []
    for d in page.query_selector_all("button, input[type=submit], a.btn, .btn"):
        try:
            metin = (d.inner_text() or d.get_attribute("value") or "").strip()
            if metin and len(metin) < 40:
                dugmeler.append({"metin": metin[:40],
                                 "id": d.get_attribute("id") or "",
                                 "class": (d.get_attribute("class") or "")[:60]})
        except Exception:                                         # noqa: BLE001
            pass
    rapor["dugmeler"] = dugmeler[:25]

    # --- Sekmeler / bağlantılar ---
    sekme = []
    for a in page.query_selector_all("a, [role=tab], .tab, .nav-link"):
        try:
            m = (a.inner_text() or "").strip()
            if m and fold(m) in il_fold:
                sekme.append(m[:30])
        except Exception:                                         # noqa: BLE001
            pass
    rapor["il_sekmesi"] = len(sekme)

    # --- DENEME: il seç + ara ---
    deneme = {"yapildi": False}
    # Eşik: en az 5 il adı VE seçeneklerin çoğu il olmalı. 20 sabit eşiği
    # yalnızca bayisi olan illeri listeleyen siteleri kaçırıyordu.
    il_secim = max((s for s in secimler
                    if s["il_sayisi"] >= 5 and s["il_sayisi"] >= s["secenek"] * 0.6),
                   key=lambda s: s["il_sayisi"], default=None)
    if il_secim:
        onceki = len(aglar)
        try:
            sec = page.query_selector_all("select")[il_secim["sira"]]
            hedef = next((o["deger"] for o in
                          [{"deger": x.get_attribute("value") or "",
                            "metin": (x.text_content() or "")}
                           for x in sec.query_selector_all("option")]
                          if fold(o["metin"]) == "istanbul"), None)
            if hedef is None:
                hedef = il_secim["ornek"][0]["deger"]
            sec.select_option(hedef)
            page.evaluate(
                """el => { el.dispatchEvent(new Event('change',{bubbles:true}));
                           el.dispatchEvent(new Event('input',{bubbles:true})); }""",
                sec)
            page.wait_for_timeout(1200)
            basilan = ""
            for kalip in ARAMA_KALIP:
                d = page.query_selector(kalip)
                if d:
                    try:
                        d.click(timeout=4000)
                        basilan = kalip
                        break
                    except Exception:                             # noqa: BLE001
                        continue
            try:
                page.wait_for_load_state("networkidle", timeout=12000)
            except Exception:                                     # noqa: BLE001
                pass
            page.wait_for_timeout(2000)
            deneme = {
                "yapildi": True,
                "secilen_il": hedef,
                "basilan_dugme": basilan,
                "sonra_telefon": len(TEL.findall(page.content())),
                "yeni_istek": len(aglar) - onceki,
                "url_degisti": page.url != url,
                "yeni_url": page.url[:300] if page.url != url else "",
            }
        except Exception as e:                                    # noqa: BLE001
            deneme = {"yapildi": False, "hata": str(e)[:160]}
    rapor["deneme"] = deneme

    # Yalnızca veri taşıyan ya da ilginç istekleri sakla
    rapor["aglar"] = [a for a in aglar if a["veri_mi"]][:12]
    rapor["ag_toplam"] = len(aglar)
    return rapor


def main():
    from playwright.sync_api import sync_playwright

    conf = load_config()["markalar"]
    if len(sys.argv) > 1:
        istenen = sys.argv[1:]
        conf = {k: v for k, v in conf.items() if k in istenen}

    CIKTI.mkdir(exist_ok=True)
    ozet = {}
    with sync_playwright() as p:
        tarayici = p.chromium.launch(headless=True)
        for marka, cfg in conf.items():
            for kaynak in kaynaklari_coz(cfg):
                rol = kaynak.get("rol", "satis")
                url = kaynak["url"].split("{")[0].rstrip("?&")
                ad = re.sub(r"[^a-z0-9]+", "-", f"{marka}-{rol}".lower()).strip("-")
                print(f"→ {marka} [{rol}]")
                sayfa = tarayici.new_page(
                    user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) "
                                "Chrome/126.0 Safari/537.36"),
                    locale="tr-TR", viewport={"width": 1440, "height": 2000})
                try:
                    r = incele(sayfa, url)
                    r["marka"], r["rol"] = marka, rol
                    (CIKTI / f"{ad}.json").write_text(
                        json.dumps(r, ensure_ascii=False, indent=1),
                        encoding="utf-8")
                    ozet[ad] = {
                        "acilis_tel": r["acilis_telefon"],
                        "veri_adresi": len(r["aglar"]),
                        "il_secici": max([s["il_sayisi"] for s in r["secimler"]],
                                         default=0),
                        "il_sekmesi": r["il_sekmesi"],
                        "deneme_sonra_tel": r["deneme"].get("sonra_telefon", 0),
                    }
                    print(f"   açılış_tel={r['acilis_telefon']} "
                          f"veri_adresi={len(r['aglar'])} "
                          f"ilSeçici={ozet[ad]['il_secici']} "
                          f"deneme_sonra={ozet[ad]['deneme_sonra_tel']}")
                except Exception as e:                            # noqa: BLE001
                    ozet[ad] = {"hata": str(e)[:160]}
                    print(f"   ✗ {str(e)[:80]}")
                finally:
                    sayfa.close()
        tarayici.close()

    (CIKTI / "ozet.json").write_text(
        json.dumps(ozet, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n✓ {len(ozet)} sayfa incelendi → {CIKTI}/")


if __name__ == "__main__":
    main()
