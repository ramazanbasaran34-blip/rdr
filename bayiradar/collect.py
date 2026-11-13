"""Toplayıcı ve zamanlayıcı.

İki önemli davranış:

1. KAPSAM TAKİBİ. `iterate: il_kodlari` modunda 81 sayfa geziliyor. Kaçının
   başarılı olduğu sayılıyor ve depoya bildiriliyor. 81'in 60'ı geldiyse tarama
   "kısmi" sayılır ve görülmeyen bayiler pasife ÇEKİLMEZ. Bu olmadan bir ağ
   dalgalanması "Pendik'te Honda bayisi yok" sonucunu doğurur.

2. KUYRUK ZAMANLAMA. Markalar sırayla, aralarında nefes payıyla taranır.
   Sabit saat ("00:03 Yamaha") yerine kuyruk kullanılır: bir marka beklenenden
   uzun sürerse sonrakiler kaymaz, sadece geriye doğru ötelenir. Site başına
   ayrı bekleme süresi tanımlanabilir.
"""

import random
import time
import time
from datetime import datetime, timedelta, timezone

import yaml

from .fetch import Fetcher
from .koordinat import sorgu_noktalari
from .normalize import IL_KODU, ILLER, fold
from .otomatik import il_baglantilari, il_secicileri_bul, json_gomulu
from .parse import (finalize, genel_adlari_yerellestir, kayit_suzgeci,
                    parse_gomulu, parse_html, parse_json, parse_oto)
from .store import commit_tarama, db, marka_bilgi, now, tarama_hatasi


def load_config(path="brands.yaml") -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def il_slug(ad: str) -> str:
    """'İstanbul' -> 'istanbul', 'Kahramanmaraş' -> 'kahramanmaras'"""
    return fold(ad).replace(" ", "")


def _post_govdesi(cfg: dict, il_adi: str) -> dict | None:
    """Tarifteki `data` sözlüğündeki yer tutucuları il adıyla doldurur.

    MJ platformu (RKS, Kuba) ili URL'de değil POST gövdesinde istiyor:
      data: {action: states, city: "{il_adi}", state: "0", category: Bayi}
    `state: 0` = "Tüm İlçeler" — il başına tek istek yeter, 973 ilçe gezilmez.
    """
    data = cfg.get("data")
    if not isinstance(data, dict):
        return data
    return {k: (v.format(il_adi=il_adi, il_slug=il_slug(il_adi))
                if isinstance(v, str) else v)
            for k, v in data.items()}


def _urls_for(cfg: dict) -> list[tuple[str, str]]:
    """(url, o_url_hangi_ile_ait) çiftleri döner.

    İkinci değer, sayfada il bilgisi yazmıyorsa kayıtlara il atamak için
    kullanılır — 'il_url_den: true' diyen tarifler buna bakar.
    """
    url = cfg["url"]
    it = cfg.get("iterate")
    if not it:
        return [(url, "")]
    if it in ("il_kodlari",) or (isinstance(it, dict) and it.get("type") == "il_kodlari"):
        return [(url.format(il_kodu=k, il_adi=v, il_slug=il_slug(v)), v)
                for k, v in IL_KODU.items()]
    if it in ("koordinat", "harita"):
        # Harita tabanlı bulucular il adı değil enlem/boylam istiyor.
        # 81 il merkezini sırayla sorguluyoruz; yarıçaplar örtüştüğü için
        # Türkiye'de boşluk kalmıyor.
        yaricap = cfg.get("yaricap_km", 120)
        return [(url.format(lat=la, lng=lo, enlem=la, boylam=lo,
                            yaricap=yaricap, yaricap_m=yaricap * 1000,
                            il_slug=il_slug(il), il_adi=il), il)
                for il, la, lo in sorgu_noktalari(yaricap)]
    if it in ("il_post", "il_govde"):
        # URL sabit; değişen POST gövdesi. İl adları ikinci değerde taşınır.
        return [(url, v) for v in ILLER]
    if it in ("il_slug", "il_adi"):
        return [(url.format(il_slug=il_slug(v), il_adi=v,
                            il_kodu=i + 1), v) for i, v in enumerate(ILLER)]
    if isinstance(it, dict) and it.get("type") in ("sayfa", "sayi"):
        return [(url.format(sayfa=i, sayi=i, deger=i), "")
                for i in range(it.get("baslangic", 1), it["bitis"] + 1)]
    if isinstance(it, list):
        return [(url.format(deger=d), "") for d in it]
    return [(url, "")]


def _sayfayi_coz(body, cfg, mode):
    """Bir sayfadan kayıt çıkarmayı sırayla dener.

    1. El yazması tarif (row verilmişse)
    2. Gömülü JSON — veri script etiketinde olabilir, tarayıcıya gerek kalmaz
    3. Otomatik yapı tespiti
    """
    if mode == "json":
        return parse_json(body, cfg)
    # Gömülü JS verisi tarifte açıkça verilmişse her şeyden önce gelir:
    # sayfa görünürde boş olsa bile veri kaynakta duruyor olabilir.
    if cfg.get("gomulu"):
        k = parse_gomulu(body, cfg)
        if k:
            return k
    if cfg.get("row"):
        return kayit_suzgeci(parse_html(body, cfg), cfg)
    gomulu = json_gomulu(body)
    if len(gomulu) >= 3:
        return gomulu
    return parse_oto(body, cfg)


def _rol_uygula(kayitlar, cfg):
    """Kayıtlara rol atar.

    Kaynak tek rollüyse (ayrı bir servis sayfası) o rol KESİNDİR; sayfadaki
    etiket onu ezemez. CFMoto'nun servis sayfasında bir yerde "Bayi" kelimesi
    geçtiği için 562 kaydın hepsi satış olarak yazılmıştı, servis sıfır kaldı.

    Kaynak ikisini birden veriyorsa (satis_servis) sayfanın kendi etiketi
    kullanılır — Rutec gibi her kaydın türünü yazan siteler için gerekli.
    """
    kaynak_rol = cfg.get("rol", "satis")
    for r in kayitlar:
        if kaynak_rol in ("satis", "servis"):
            r["rol"] = kaynak_rol
        else:
            r.setdefault("rol", kaynak_rol)


def kaynaklari_coz(cfg: dict) -> list[dict]:
    """Markanın taranacak kaynaklarını döner: [{rol, url, ...}, ...]

    Yeni biçim 'kaynaklar' listesi kullanıyor. Eski tek-url biçimi de
    çalışmaya devam etsin diye ona da destek var.
    """
    if cfg.get("kaynaklar"):
        out = []
        for k in cfg["kaynaklar"]:
            alt = {**{x: v for x, v in cfg.items() if x != "kaynaklar"}, **k}
            out.append(alt)
        return out
    return [{**cfg, "rol": cfg.get("rol", "satis")}]


def tara_marka_tek(marka: str, cfg: dict, fetcher: Fetcher, max_age=3600, log=None):
    """Tek bir kaynağı tarar. Süre bütçesi bu fonksiyonun içinde işler."""
    """Tek markayı tarar. Döner: (kayitlar, kapsam)

    Boş dönerse pes etmez, kademeli olarak şunları dener:
      · sayfa bir il dizini mi? → 81 il bağlantısını tek tek gez
      · tarayıcı gerekiyor mu?  → gerçek tarayıcıyla yeniden aç
    """
    log = log or (lambda m: None)
    mode = cfg.get("mode", "html")
    kayitlar, gorulen = [], set()
    urls = _urls_for(cfg)
    basarili_url = 0
    ilk_hata = None

    def ekle(ham, url, url_ili, zorla_il=False):
        for r in ham:
            # il_url_den: tarifte belirtilmiş
            # zorla_il  : ili bağlantı metninden kesin biliyoruz (il dizini)
            if url_ili and not r.get("il") and (zorla_il or cfg.get("il_url_den")):
                r["il"] = url_ili
            rec = finalize(r, marka, url, cfg)
            if not rec:
                continue
            # İMZADA İLÇE DEĞİL ADRES.
            #
            # İl seçmeli sitelerin çoğu filtre uygulamadan tam listeyi
            # döndürüyor. Tarama 81 il için istek attığından aynı bayi
            # tekrar tekrar geliyordu; ilçe her turda farklı atandığı
            # için (çoğu zaman il adıyla dolduruluyor) imza değişiyor ve
            # kayıt yeni sanılıyordu: Voge 138 -> 1.136, Volta 152 -> 754.
            #
            # Adres şubeden şubeye gerçekten değişir, il sorgusuna göre
            # değişmez. Bajaj'ın aynı telefonu paylaşan şubeleri farklı
            # adreste olduğu için yine ayrı kalıyor.
            imza = (fold(rec["bayi_adi"]), rec["telefon"],
                    fold(rec.get("adres", ""))[:60])
            if imza in gorulen:
                continue
            gorulen.add(imza)
            kayitlar.append(rec)

    def cek(url, tarayici=False, il_adi=""):
        if tarayici or mode == "browser":
            return fetcher.render(url, cfg.get("wait_selector"), max_age=max_age)
        return fetcher.get(url, method=cfg.get("method", "GET"),
                           data=_post_govdesi(cfg, il_adi),
                           headers=cfg.get("headers"),
                           max_age=max_age, encoding=cfg.get("encoding"))

    # --- 0a. tur: tür süzgeci varsa her tür için ayrı gez ---
    # Kaydın türü kartta yazmıyorsa (Arora) sayfanın süzgeci kullanılır:
    # önce "Bayi" işaretlenip iller gezilir, sonra "Servis", sonra "Bayi+Servis".
    suzgec = cfg.get("tur_suzgeci")
    if suzgec and len(urls) == 1:
        try:
            log("     tür süzgeciyle geziliyor")
            for rol, il_adi, sayfa in fetcher.tur_ve_il_gez(
                    urls[0][0], suzgec["secici"], suzgec["degerler"], log,
                    azami_saniye=KAYNAK_AZAMI_SANIYE * 0.9):
                ham = _sayfayi_coz(sayfa, cfg, "html")
                for r in ham:
                    r["rol"] = rol            # süzgeçten gelen rol kesindir
                # İli listeden biz seçtik, kesin biliyoruz → zorla yaz
                ekle(ham, urls[0][0], il_adi, zorla_il=True)
            if kayitlar:
                return kayitlar, 1.0
            log("     tür süzgeci sonuç vermedi")
        except Exception as e:                                    # noqa: BLE001
            log(f"     tür süzgeci hatası: {str(e)[:70]}")

    # --- 0. tur: tarif açıkça "il seçerek gez" diyorsa doğrudan onu yap ---
    # Bazı sitelerde il seçimi URL'e yansımıyor (Arora): parametre denemek
    # hep aynı sayfayı döndürüyor ve tek ilin verisi geliyordu.
    if cfg.get("etkilesim") == "il_secimi" and len(urls) == 1:
        try:
            log("     il seçerek geziliyor")
            for il_adi, sayfa in fetcher.il_secerek_gez(
                    urls[0][0], log, azami_saniye=KAYNAK_AZAMI_SANIYE * 0.8):
                ekle(_sayfayi_coz(sayfa, cfg, "html"), urls[0][0], il_adi,
                     zorla_il=False)
            if kayitlar:
                _rol_uygula(kayitlar, cfg)
                return kayitlar, 1.0
            log("     il seçimi sonuç vermedi, normal akışa dönülüyor")
        except Exception as e:                                    # noqa: BLE001
            log(f"     il seçimi hatası: {str(e)[:70]}")

    # --- 1. tur: tarifteki adres(ler) ---
    ilk_body = None
    for url, url_ili in urls:
        try:
            body = cek(url, il_adi=url_ili)
            basarili_url += 1
            if ilk_body is None:
                ilk_body = body
        except Exception as e:                                    # noqa: BLE001
            ilk_hata = ilk_hata or e
            if len(urls) == 1:
                raise RuntimeError(f"{marka}: {e}") from e
            continue
        ekle(_sayfayi_coz(body, cfg, mode), url, url_ili)

    _rol_uygula(kayitlar, cfg)

    kapsam = basarili_url / len(urls) if urls else 0.0
    if ilk_body is None:
        return kayitlar, kapsam
    # Kayıt geldiyse bile, tarifte il döngüsü yoksa seçici olup olmadığına bak:
    # tek sayfadan gelen kayıtlar listenin tamamı olmayabilir.
    if kayitlar and (cfg.get("iterate") or len(urls) > 1):
        return kayitlar, kapsam

    # --- 2. tur: sayfada il seçen açılır liste var mı? ---
    # Çoğu sayfa parametresiz açıldığında listenin sadece bir dilimini veriyor.
    # Seçiciyi bulup 81 ili tek tek geziyoruz. Bu adım kayıt VARSA da çalışır,
    # çünkü "az kayıt geldi ama hepsi temiz" en sinsi hata biçimi.
    if len(urls) == 1 and not cfg.get("iterate"):
        il_urls = il_secicileri_bul(ilk_body, urls[0][0])
        if il_urls:
            log(f"     il seçici bulundu: {len(il_urls)} il geziliyor")
            basarili = 0
            il_bas = time.monotonic()
            for il_url, il_adi in il_urls:
                if time.monotonic() - il_bas > KAYNAK_AZAMI_SANIYE * 0.6:
                    log(f"     süre doldu, {basarili}/{len(il_urls)} il tarandı")
                    break
                try:
                    ekle(_sayfayi_coz(cek(il_url), cfg, mode), il_url, il_adi,
                         zorla_il=True)
                    basarili += 1
                except Exception:                                 # noqa: BLE001
                    continue
            if kayitlar:
                return kayitlar, basarili / len(il_urls)

    # --- 3. tur: sayfa bir il dizini mi? ---
    if len(urls) == 1:
        iller = il_baglantilari(ilk_body, urls[0][0])
        if iller:
            log(f"     il dizini bulundu: {len(iller)} il geziliyor")
            basarili = 0
            dz_bas = time.monotonic()
            for il_adi, il_url in iller.items():
                if time.monotonic() - dz_bas > KAYNAK_AZAMI_SANIYE * 0.6:
                    log(f"     süre doldu, {basarili}/{len(iller)} il tarandı")
                    break
                try:
                    ekle(_sayfayi_coz(cek(il_url), cfg, mode), il_url, il_adi,
                         zorla_il=True)
                    basarili += 1
                except Exception:                                 # noqa: BLE001
                    continue
            if kayitlar:
                return kayitlar, basarili / len(iller)

    # --- 4. tur: açılır listeden il seçerek gez ---
    # Bazı siteler URL parametresini dinlemiyor; liste ancak listeden seçim
    # yapılınca geliyor. Sayfayı gerçekten kullanmak gerekiyor.
    if len(urls) == 1 and not cfg.get("iterate"):
        try:
            log("     açılır listeden il seçilerek deneniyor")
            for il_adi, sayfa in fetcher.il_secerek_gez(urls[0][0], log):
                ekle(_sayfayi_coz(sayfa, cfg, "html"), urls[0][0], il_adi,
                     zorla_il=True)
            if kayitlar:
                _rol_uygula(kayitlar, cfg)
                return kayitlar, 1.0
        except Exception as e:                                    # noqa: BLE001
            log(f"     il seçimi başarısız: {str(e)[:60]}")

    # --- 5. tur: tarayıcı gerekiyor olabilir ---
    if mode != "browser":
        try:
            log("     statik sayfada kayıt yok, tarayıcı deneniyor")
            body = cek(urls[0][0], tarayici=True)
            ekle(_sayfayi_coz(body, cfg, "html"), urls[0][0], urls[0][1])
            if kayitlar:
                return kayitlar, 1.0
            il_urls = il_secicileri_bul(body, urls[0][0])
            if il_urls:
                log(f"     tarayıcıda il seçici: {len(il_urls)} il")
                for il_url, il_adi in il_urls:
                    try:
                        ekle(_sayfayi_coz(cek(il_url, True), cfg, "html"),
                             il_url, il_adi, zorla_il=True)
                    except Exception:                             # noqa: BLE001
                        continue
                if kayitlar:
                    return kayitlar, 1.0
            iller = il_baglantilari(body, urls[0][0])
            if iller:
                log(f"     tarayıcıda il dizini: {len(iller)} il")
                for il_adi, il_url in iller.items():
                    try:
                        ekle(_sayfayi_coz(cek(il_url, True), cfg, "html"),
                             il_url, il_adi, zorla_il=True)
                    except Exception:                             # noqa: BLE001
                        continue
        except Exception as e:                                    # noqa: BLE001
            log(f"     tarayıcı denemesi başarısız: {str(e)[:60]}")

    _rol_uygula(kayitlar, cfg)
    return kayitlar, (1.0 if kayitlar else kapsam)


# Bir KAYNAK en fazla bu kadar sürebilir. Aşarsa o ana kadar toplananla
# yetinilip sonraki kaynağa geçilir.
#
# Neden kaynak başına: markanın tamamına sınır koyunca satış taraması uzun
# sürdüğünde servis hiç başlamıyordu. Bajaj'da 92 satış vardı, servis sıfırdı;
# CFMoto'da 437 satış, sıfır servis. Sayfalar çalışıyordu, sınır kesiyordu.
KAYNAK_AZAMI_SANIYE = 1800       # 30 dakika


def tara_marka(marka: str, cfg: dict, fetcher: Fetcher, max_age=3600, log=None):
    """Markanın tüm kaynaklarını (satış + servis) tarar ve birleştirir."""
    log = log or (lambda m: None)
    kaynaklar = kaynaklari_coz(cfg)
    hepsi, kapsamlar = [], []
    for k in kaynaklar:
        if len(kaynaklar) > 1:
            log(f"     [{k.get('rol','satis')}] {k['url'][:60]}")
        try:
            kay, kap = tara_marka_tek(marka, k, fetcher, max_age, log)
        except Exception as e:                                    # noqa: BLE001
            log(f"     kaynak başarısız: {str(e)[:60]}")
            kapsamlar.append(0.0)
            continue
        hepsi.extend(kay)
        kapsamlar.append(kap)
    # Tek noktada: tüm kaynaklar toplandıktan sonra, çünkü aynı ada düşen
    # kayıtları ayırmak için markanın tamamını görmek gerekiyor.
    hepsi = genel_adlari_yerellestir(hepsi, cfg)
    return hepsi, (sum(kapsamlar) / len(kapsamlar) if kapsamlar else 0.0)


# ============================================================================
#  ZAMANLAMA
# ============================================================================
_GUN_HARITASI: dict[str, int] = {}


def gun_haritasi(config_path="brands.yaml") -> dict:
    """Markaları haftanın günlerine EŞİT dağıtır (0=Pazartesi ... 6=Pazar).

    Marka adının harflerinden hesaplamak dengesiz sonuç veriyordu (bir güne
    14, diğerine 3 marka). Bunun yerine alfabetik sıraya göre sırayla
    dağıtıyoruz: 63 marka → her güne 9.

    Haftada bir tazelik korunur ama tek gecede 63 siteye gidilmez; hem karşı
    tarafa yük binmez hem de aynı IP'den yoğun trafik görünmez.
    """
    global _GUN_HARITASI
    if not _GUN_HARITASI:
        markalar = sorted(load_config(config_path).get("markalar", {}))
        _GUN_HARITASI = {m: i % 7 for i, m in enumerate(markalar)}
    return _GUN_HARITASI


def _gun_yuvasi(marka: str) -> int:
    return gun_haritasi().get(marka, 0)


# Tarama tutarsız çıkarsa (hata / kısmi kapsam / karantina) bu kadar saat
# sonra SADECE o marka yeniden taranır. Haftalık periyot beklenmez.
TUTARSIZLIK_BEKLEME = 3


def tarama_gerekiyor_mu(bilgi: dict, cfg: dict, marka: str = "") -> tuple[bool, str]:
    """Bu marka şimdi taranmalı mı? (evet_mi, gerekçe)"""
    periyot = cfg.get("periyot_saat", 168)      # varsayılan: haftalık
    son = bilgi.get("son_basarili")
    if not son:
        return True, "hiç başarılı tarama yok"

    simdi = datetime.now(timezone.utc)
    yas = simdi - datetime.fromisoformat(son)

    # TUTARSIZLIK SONRASI: haftalık periyodu bekleme, 3 saat sonra
    # SADECE BU MARKAYI yeniden tara.
    #
    # Neden 3 saat: hata, kısmi kapsam ya da karantina genelde geçici bir
    # arızadan geliyor (site yavaş, bir il sayfası düşmüş, sunucu bakımda).
    # Bir hafta beklemek veriyi bayatlatıyor; hemen tekrar denemek de
    # karşı tarafı zorluyor. 3 saat ikisinin arası.
    #
    # Ardışık hata artarsa aralık büyüyor (3, 6, 12, en fazla 24 saat) ki
    # site gerçekten kapalıysa üst üste gidilmesin.
    if bilgi.get("son_deneme_durum") in ("hatali", "kismi", "karantina"):
        son_deneme = bilgi.get("son_deneme")
        if son_deneme:
            hata = max(bilgi.get("ardisik_hata", 1), 1)
            bekleme_saat = min(TUTARSIZLIK_BEKLEME * (2 ** (hata - 1)), 24)
            gecen = simdi - datetime.fromisoformat(son_deneme)
            if gecen < timedelta(hours=bekleme_saat):
                kalan = bekleme_saat - gecen.total_seconds() / 3600
                return False, (f"tutarsızlık sonrası tekrar denemeye "
                               f"{kalan:.1f} saat var")
        return True, "önceki tarama tutarsızdı, yeniden deneniyor"

    if yas < timedelta(hours=periyot):
        gun = int(yas.total_seconds() // 86400)
        return False, f"{gun} gün önce tarandı, periyot {int(periyot/24)} gün"

    # Periyot dolmuş. Haftalık markalarda ayrıca gün yuvası tutmalı ki
    # 63 marka aynı geceye yığılmasın.
    if marka and periyot >= 168 and not cfg.get("oncelik") == 1:
        if simdi.weekday() != _gun_yuvasi(marka):
            gunler = ["Pazartesi","Salı","Çarşamba","Perşembe","Cuma",
                      "Cumartesi","Pazar"]
            return False, f"sırası {gunler[_gun_yuvasi(marka)]} günü"

    return True, f"{yas.days} gündür taranmadı"


def plan_olustur(config_path="brands.yaml", db_path="bayiler.db",
                 zamanlanmis=False) -> list[dict]:
    """Tarama sırasını ve tahmini başlangıç saatlerini hesaplar.

    Sabit saat atamıyoruz. Bir marka 81 sayfa geziyorsa 20 dakika sürebilir;
    sabit saatli plan çakışır. Bunun yerine kuyruk: her marka öncekinin
    bitişinden + nefes payı kadar sonra başlar.
    """
    conf = load_config(config_path)
    ayarlar = conf.get("ayarlar", {})
    marka_arasi = ayarlar.get("marka_arasi_saniye", 180)
    varsayilan_bekleme = ayarlar.get("bekleme", 1.2)

    plan, t = [], datetime.now()
    with db(db_path) as con:
        for marka, cfg in conf.get("markalar", {}).items():
            if cfg.get("pasif"):
                continue
            bilgi = marka_bilgi(con, marka)
            gerek, sebep = tarama_gerekiyor_mu(bilgi, cfg, marka)
            if zamanlanmis and not gerek:
                continue

            sayfa = len(_urls_for(cfg))
            bekleme = cfg.get("bekleme", varsayilan_bekleme)
            # kaba tahmin: sayfa başına bekleme + ~2 sn yanıt süresi
            tahmini_sn = sayfa * (bekleme + 2.0)
            plan.append({
                "marka": marka,
                "baslangic": t,
                "sayfa": sayfa,
                "bekleme": bekleme,
                "tahmini_dk": round(tahmini_sn / 60, 1),
                "sebep": sebep,
                "oncelik": cfg.get("oncelik", 5),
            })
            t += timedelta(seconds=tahmini_sn + marka_arasi)

    # Öncelikli markalar önce (büyük markalar gece erken saatte bitsin)
    plan.sort(key=lambda p: p["oncelik"])
    t = datetime.now()
    for p in plan:
        p["baslangic"] = t
        t += timedelta(seconds=p["tahmini_dk"] * 60 + marka_arasi)
    return plan


# ============================================================================
#  ÇALIŞTIRMA
# ============================================================================
def tara_hepsi(config_path="brands.yaml", sadece=None, db_path="bayiler.db",
               max_age=3600, zamanlanmis=False, log=print) -> dict:
    """Markaları kuyrukta, aralarında nefes payıyla tarar."""
    conf = load_config(config_path)
    ayarlar = conf.get("ayarlar", {})
    marka_arasi = ayarlar.get("marka_arasi_saniye", 180)
    varsayilan_bekleme = ayarlar.get("bekleme", 1.2)

    markalar = {k: v for k, v in conf.get("markalar", {}).items()
                if not v.get("pasif")}
    if sadece:
        markalar = {k: v for k, v in markalar.items() if k in sadece}

    ozet = {"basarili": [], "kismi": [], "karantina": [], "hatali": [],
            "atlanan": [], "toplam_kayit": 0}

    with db(db_path) as con:
        sirali = sorted(markalar.items(), key=lambda kv: kv[1].get("oncelik", 5))
        for i, (marka, cfg) in enumerate(sirali):
            # elle: true → verisi elle/<marka>.json'dan geliyor, taranmaz.
            # (Cloudflare korumalı siteler; bkz. elle_tara.py)
            if cfg.get("elle"):
                ozet["atlanan"].append((marka, "elle girilen veri"))
                log(f"⏭  {marka} atlandı — elle girilen veri")
                continue

            if zamanlanmis:
                gerek, sebep = tarama_gerekiyor_mu(marka_bilgi(con, marka), cfg, marka)
                if not gerek:
                    ozet["atlanan"].append((marka, sebep))
                    log(f"⏭  {marka} atlandı — {sebep}")
                    continue

            # Markalar arası nefes payı: karşı tarafa da, bize de iyi gelir
            if i > 0 and marka_arasi:
                bekle = marka_arasi + random.randint(0, 60)
                log(f"   ⏸  {bekle} sn bekleniyor...")
                time.sleep(bekle)

            fetcher = Fetcher(delay=cfg.get("bekleme", varsayilan_bekleme))
            bas = now()
            log(f"→ {marka} taranıyor...")
            try:
                kayitlar, kapsam = tara_marka(marka, cfg, fetcher, max_age, log)
                sonuc = commit_tarama(con, marka, kayitlar, kapsam, bas)
            except Exception as e:                                # noqa: BLE001
                sonuc = tarama_hatasi(con, marka, bas, str(e))
            finally:
                fetcher.close()
            con.commit()

            d = sonuc["durum"]
            if d == "basarili":
                ozet["basarili"].append((marka, sonuc["adet"]))
                ozet["toplam_kayit"] += sonuc["adet"]
                ek = f", {sonuc['supheli']} doğrulanamadı" if sonuc["supheli"] else ""
                log(f"  ✓ {sonuc['adet']} bayi ({sonuc['yeni']} yeni{ek})")
            elif d in ("kismi", "karantina"):
                ozet[d].append((marka, sonuc["mesaj"]))
                log(f"  ⚠ {sonuc['mesaj']} — eski veri korundu")
            else:
                ozet["hatali"].append((marka, sonuc["mesaj"]))
                log(f"  ✗ {sonuc['mesaj'][:80]} — eski veri korundu")

    return ozet
