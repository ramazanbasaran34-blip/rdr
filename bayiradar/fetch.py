"""Sayfa çekme katmanı.

Üç strateji:
  http     – requests ile düz GET/POST (en hızlı, tercih edilen)
  browser  – Playwright ile gerçek tarayıcı (JS ile çizilen harita/liste için)

Nazik davranıyoruz: istekler arası bekleme, retry, gerçek User-Agent.
70 siteyi peş peşe dövmek IP ban demektir.
"""

import hashlib
import random
import time
from pathlib import Path

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

CACHE_DIR = Path(".cache")


class Fetcher:
    def __init__(self, delay=1.2, timeout=20, retries=3, use_cache=True):
        self.delay = delay
        self.timeout = timeout
        self.retries = retries
        self.use_cache = use_cache
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": UA,
            "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
        })
        self._browser = None
        CACHE_DIR.mkdir(exist_ok=True)

    # ---------------------------------------------------------------- cache
    def _cache_path(self, key: str) -> Path:
        return CACHE_DIR / (hashlib.sha1(key.encode()).hexdigest() + ".txt")

    def _cached(self, key: str, max_age=3600):
        if not self.use_cache:
            return None
        p = self._cache_path(key)
        if p.exists() and time.time() - p.stat().st_mtime < max_age:
            return p.read_text(encoding="utf-8")
        return None

    def _store(self, key: str, body: str):
        if self.use_cache:
            self._cache_path(key).write_text(body, encoding="utf-8")

    # ----------------------------------------------------------------- http
    def get(self, url, method="GET", data=None, headers=None, max_age=3600,
            encoding=None):
        # Yerel dosya: seçicileri internete çıkmadan test etmek için
        if not url.startswith(("http://", "https://")):
            return Path(url).read_text(encoding="utf-8")

        key = f"{method}:{url}:{data}"
        hit = self._cached(key, max_age)
        if hit is not None:
            return hit

        last = None
        for attempt in range(self.retries):
            try:
                time.sleep(self.delay + random.random() * 0.4)
                r = self.session.request(
                    method, url, data=data, headers=headers,
                    timeout=self.timeout,
                )
                r.raise_for_status()
                # Türk siteleri sık sık windows-1254 kullanır ve bunu doğru
                # bildirmez; yanlış kodlama "İstanbul" yerine "�stanbul" verir.
                r.encoding = encoding or r.apparent_encoding or r.encoding
                self._store(key, r.text)
                return r.text
            except Exception as e:          # noqa: BLE001
                last = e
                time.sleep(2 ** attempt)
        raise RuntimeError(f"{url} çekilemedi: {last}")

    # -------------------------------------------------------------- browser
    def render(self, url, wait_selector=None, wait_ms=3000, max_age=3600):
        """JS ile dolan sayfalar için. Playwright kurulu değilse anlaşılır hata verir."""
        key = f"RENDER:{url}"
        hit = self._cached(key, max_age)
        if hit is not None:
            return hit
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise RuntimeError(
                "Bu marka için tarayıcı gerekiyor. Kurulum:\n"
                "  pip install playwright && playwright install chromium"
            ) from e

        if self._browser is None:
            self._pw = sync_playwright().start()
            try:
                self._browser = self._pw.chromium.launch(headless=True)
            except Exception:
                # Chromium indirilmemişse bir kez kendisi kursun. İş akışındaki
                # kurulum adımı atlanmış olabilir; buna bağlı kalmıyoruz.
                import subprocess
                import sys as _sys
                subprocess.run([_sys.executable, "-m", "playwright",
                                "install", "--with-deps", "chromium"],
                               check=False, timeout=600)
                self._browser = self._pw.chromium.launch(headless=True)
        page = self._browser.new_page(user_agent=UA, locale="tr-TR",
                                      viewport={"width": 1440, "height": 2200})
        try:
            page.goto(url, timeout=self.timeout * 1000, wait_until="domcontentloaded")
            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=self.timeout * 1000)
                except Exception:                                 # noqa: BLE001
                    pass
            # Arka plan istekleri bitene kadar bekle — liste çoğu sitede
            # sayfa açıldıktan sonra AJAX ile geliyor.
            try:
                page.wait_for_load_state("networkidle", timeout=12000)
            except Exception:                                     # noqa: BLE001
                pass
            # Tembel yüklenen listeler için sayfayı sonuna kadar kaydır
            try:
                onceki = 0
                for _ in range(6):
                    page.mouse.wheel(0, 5000)
                    page.wait_for_timeout(400)
                    yukseklik = page.evaluate("document.body.scrollHeight")
                    if yukseklik == onceki:
                        break
                    onceki = yukseklik
            except Exception:                                     # noqa: BLE001
                pass
            page.wait_for_timeout(wait_ms)
            html = page.content()
            self._store(key, html)
            return html
        finally:
            page.close()

    def il_secerek_gez(self, url, log=None, azami_saniye=900):
        """Sayfadaki il açılır listesini kullanarak 81 ili tek tek gezer.

        Bazı siteler URL parametresini dinlemiyor; liste ancak listeden il
        seçilip arama yapılınca geliyor. Bu durumda sayfayı gerçekten
        kullanmak gerekiyor: seç, tetikle, bekle, oku.

        Döner: [(il_adi, html), ...]
        """
        from .normalize import ILLER, fold
        log = log or (lambda m: None)
        try:
            from playwright.sync_api import sync_playwright     # noqa: F401
        except ImportError:
            return []

        if self._browser is None:
            self.render(url, max_age=0)          # tarayıcıyı başlat

        il_fold = {fold(i): i for i in ILLER}
        il_fold.update({"afyon": "Afyonkarahisar", "icel": "Mersin",
                        "mersin icel": "Mersin", "urfa": "Şanlıurfa",
                        "k maras": "Kahramanmaraş"})
        page = self._browser.new_page(user_agent=UA, locale="tr-TR",
                                      viewport={"width": 1440, "height": 2000})
        cikti = []
        try:
            page.goto(url, timeout=self.timeout * 1000, wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:                                     # noqa: BLE001
                pass

            # İl listesini bul: seçeneklerinde en çok il adı geçen <select>
            hedef, secenekler = None, []
            for i, sec in enumerate(page.query_selector_all("select")):
                cift = []
                for o in sec.query_selector_all("option"):
                    d = (o.get_attribute("value") or "").strip()
                    # inner_text() <option> üzerinde boş döner (seçenekler
                    # ekranda çizilmiyor). text_content() kullanılmalı.
                    m = fold(o.text_content() or "")
                    if d and d.lower() not in ("", "0", "-1") and m in il_fold:
                        cift.append((d, il_fold[m]))
                if len(cift) > len(secenekler):
                    hedef, secenekler = i, cift
            if hedef is None or len(secenekler) < 5:
                return []

            log(f"     açılır listede {len(secenekler)} il, tek tek seçiliyor")
            import time as _t
            bas = _t.monotonic()
            for deger, il in secenekler:
                # Cevap vermeyen site bütün taramayı kilitlemesin
                if _t.monotonic() - bas > azami_saniye:
                    log(f"     süre doldu, {len(cikti)}/{len(secenekler)} il alındı")
                    break
                try:
                    sec = page.query_selector_all("select")[hedef]
                    sec.select_option(deger)
                    page.evaluate(
                        """el => { el.dispatchEvent(new Event('change',{bubbles:true}));
                                   el.dispatchEvent(new Event('input',{bubbles:true})); }""",
                        sec)
                    # Arama butonu varsa bas
                    for kalip in ["button[type=submit]", "input[type=submit]",
                                  "button:has-text('Ara')", "button:has-text('ARA')",
                                  "a:has-text('Ara')", ".btn-search", "#ara"]:
                        d = page.query_selector(kalip)
                        if d:
                            try:
                                d.click(timeout=3000)
                            except Exception:                     # noqa: BLE001
                                pass
                            break
                    try:
                        page.wait_for_load_state("networkidle", timeout=5000)
                    except Exception:                             # noqa: BLE001
                        pass
                    page.wait_for_timeout(350)
                    cikti.append((il, page.content()))
                except Exception as e:                            # noqa: BLE001
                    log(f"     {il}: {str(e)[:50]}")
                    continue
        finally:
            page.close()
        return cikti

    def tur_ve_il_gez(self, url, suzgec_secici, degerler, log=None,
                      azami_saniye=1500):
        """Tür süzgecini işaretleyip her tür için 81 ili gezer.

        Bazı sitelerde kaydın türü (bayi / servis / ikisi) kartta yazmıyor;
        sayfanın üstündeki onay kutusuyla süzülüyor. Arora böyle: kart hangi
        türe ait belli değil, ama "B", "S", "BS" kutuları var.

        Tür bilgisini doğru almak için her kutuyu tek tek işaretleyip listeyi
        ayrı ayrı toplamak gerekiyor.

        degerler: [{"deger": "B", "rol": "satis"}, ...]
        Döner: [(rol, il_adi, html), ...]
        """
        import time as _t

        from .normalize import ILLER, fold
        log = log or (lambda m: None)
        try:
            from playwright.sync_api import sync_playwright   # noqa: F401
        except ImportError:
            return []
        if self._browser is None:
            self.render(url, max_age=0)

        il_fold = {fold(i): i for i in ILLER}
        il_fold.update({"afyon": "Afyonkarahisar", "icel": "Mersin",
                        "urfa": "Şanlıurfa", "k maras": "Kahramanmaraş"})
        cikti = []
        bas = _t.monotonic()

        for tur in degerler:
            if _t.monotonic() - bas > azami_saniye:
                log(f"     süre doldu, {len(cikti)} sayfa alındı")
                break
            page = self._browser.new_page(user_agent=UA, locale="tr-TR",
                                          viewport={"width": 1440, "height": 2000})
            try:
                page.goto(url, timeout=self.timeout * 1000,
                          wait_until="domcontentloaded")
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:                                 # noqa: BLE001
                    pass

                # Süzgeç ya açılır liste ya onay kutusu — ikisini de destekle.
                #
                # Önceki sürüm her zaman check() çağırıyordu; açılır listelerde
                # (Kuba, RKS, Kymco, Nanok, Leksas, Abush, Axion, Rutec)
                # hiç çalışmıyor ve o markalar sıfır kayıt veriyordu.
                eleman = page.query_selector(suzgec_secici)
                if eleman and eleman.evaluate("e => e.tagName.toLowerCase()") == "select":
                    eleman.select_option(tur["deger"])
                    page.evaluate(
                        """el => { el.dispatchEvent(new Event('change',{bubbles:true}));
                                   el.dispatchEvent(new Event('input',{bubbles:true})); }""",
                        eleman)
                else:
                    for d in degerler:
                        kutu = page.query_selector(
                            f"{suzgec_secici}[value='{d['deger']}']")
                        if not kutu:
                            continue
                        secili = kutu.is_checked()
                        if d["deger"] == tur["deger"] and not secili:
                            kutu.check(timeout=4000)
                        elif d["deger"] != tur["deger"] and secili:
                            kutu.uncheck(timeout=4000)
                page.wait_for_timeout(900)
                log(f"     [{tur['rol']}] süzgeç işaretlendi")

                # İl listesini bul
                hedef, secenekler = None, []
                for i, sec in enumerate(page.query_selector_all("select")):
                    cift = []
                    for o in sec.query_selector_all("option"):
                        dv = (o.get_attribute("value") or "").strip()
                        m = fold(o.text_content() or "")
                        if dv and dv.lower() not in ("", "0", "-1") and m in il_fold:
                            cift.append((dv, il_fold[m]))
                    if len(cift) > len(secenekler):
                        hedef, secenekler = i, cift

                if hedef is None or len(secenekler) < 5:
                    cikti.append((tur["rol"], "", page.content()))
                    continue

                for dv, il in secenekler:
                    if _t.monotonic() - bas > azami_saniye:
                        break
                    try:
                        sec = page.query_selector_all("select")[hedef]
                        sec.select_option(dv)
                        page.evaluate(
                            """el => { el.dispatchEvent(new Event('change',{bubbles:true}));
                                       el.dispatchEvent(new Event('input',{bubbles:true})); }""",
                            sec)
                        try:
                            page.wait_for_load_state("networkidle", timeout=5000)
                        except Exception:                         # noqa: BLE001
                            pass
                        page.wait_for_timeout(500)

                        # İl seçilince dolan bir İLÇE listesi var mı?
                        # Kuba ve RKS'de zincir üç adımlı: tür → il → ilçe.
                        # İlçe seçilmeden sonuç görünmüyordu.
                        ilce_sec = None
                        for s2 in page.query_selector_all("select"):
                            ad2 = ((s2.get_attribute("name") or "") + " "
                                   + (s2.get_attribute("id") or "")).lower()
                            if any(k in ad2 for k in ("district", "ilce", "ilçe", "town")):
                                ilce_sec = s2
                                break
                        ilce_degerleri = []
                        if ilce_sec:
                            for o in ilce_sec.query_selector_all("option"):
                                dv2 = (o.get_attribute("value") or "").strip()
                                if dv2 and dv2.lower() not in ("", "0", "-1"):
                                    ilce_degerleri.append(dv2)

                        if not ilce_degerleri:
                            cikti.append((tur["rol"], il, page.content()))
                            continue

                        for dv2 in ilce_degerleri:
                            if _t.monotonic() - bas > azami_saniye:
                                break
                            try:
                                ilce_sec.select_option(dv2)
                                page.evaluate(
                                    """el => { el.dispatchEvent(new Event('change',{bubbles:true}));
                                               el.dispatchEvent(new Event('input',{bubbles:true})); }""",
                                    ilce_sec)
                                try:
                                    page.wait_for_load_state("networkidle", timeout=4000)
                                except Exception:                 # noqa: BLE001
                                    pass
                                page.wait_for_timeout(300)
                                cikti.append((tur["rol"], il, page.content()))
                            except Exception:                     # noqa: BLE001
                                continue
                    except Exception:                             # noqa: BLE001
                        continue
            except Exception as e:                                # noqa: BLE001
                log(f"     [{tur['rol']}] hata: {str(e)[:60]}")
            finally:
                page.close()
        return cikti

    def close(self):
        if self._browser:
            self._browser.close()
            self._pw.stop()
            self._browser = None
