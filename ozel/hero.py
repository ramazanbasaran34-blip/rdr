"""Hero — www.heromotor.com.tr (Önder Motor)

NASIL ÇALIŞIYOR
Bayiler ve servisler iki ayrı sayfada, ikisi de aynı formu kullanıyor:

    <form action="bayiler/" method="POST">
      <select name="city_box"> 1..81 il </select>
      <input type="submit" name="ara" value="Ara">

Sonuç yalnızca POST ile geliyor (GET ?city_box=6 boş sayfa döndürüyor).
Her kayıt ayrı bir blok:

    <div class="corpaorateOffice">
      <h2 id="centrename">VİZYOL SİNCAN SHOWROOM</h2>
      <table><tr><td>Adres :</td><td>...</td></tr>
             <tr><td>Telefon :</td><td>...</td></tr></table>

NOT: sayfada tel: bağlantısı YOK. Eski konsol kodu (HERO-NASIL.txt)
tel: bağlantısı aradığı için Kasım 2026'da 0 kayıt döndürüyordu.

ŞUBE KURALI (kullanıcı kuralı)
  · Aynı ad + aynı adres, hem bayi hem servis listesinde → tek kayıt,
    rol satis_servis.
  · Aynı ad ama FARKLI adres → ayrı şube, ayrı kayıt (KOÇ MOTOR'un
    Hendek/Pamukova/Merkez şubeleri, ÖZ UYGUR'un Yunak/Akşehir'i).
  · Sitede satış tarafı "… MERKEZ SHOWROOM …", servis tarafı
    "… MERKEZ SERVİS …" diye yazılan Önder Motor merkezleri aynı
    adreste aynı işyeri; SHOWROOM/SERVİS kelimesi atılarak eşleşiyor ve
    tek satis_servis kayıt oluyor. Önder Motor'un Nazilli, Üsküdar,
    Fethiye, Ödemiş merkezleri farklı adreslerde, ayrı kalıyor.

CLOUDFLARE
Site Cloudflare arkasında. 2026 Eylül ölçümünde GitHub Actions IP'lerinden
PHP sayfaları 403 dönüyordu. Çekilemeyen il çoksa getir() hata fırlatır;
böylece eksik tarama kayıtları "görülmedi" diye işaretlemez, veri korunur.
"""

from __future__ import annotations

import re
import time

from bs4 import BeautifulSoup

from bayiradar.eslestir import _ayirt_edici, adres_benzer
from bayiradar.normalize import fold

MARKA = "Hero"
TABAN = "https://www.heromotor.com.tr"
KAYNAKLAR = {
    "satis": f"{TABAN}/bayiler/",
    "servis": f"{TABAN}/servisler/",
}
UC = KAYNAKLAR["satis"]

# İl kutusundaki ad → resmi il adı (sitede kısaltılmış olanlar)
IL_DUZELT = {"Afyon": "Afyonkarahisar"}

_BEKLE = 0.6          # siteyi yormamak için istekler arası saniye
_EN_AZ_IL = 75        # bundan az il seçeneği gelirse sayfa bozuk sayılır
_HATA_ESIGI = 0.05    # çekilemeyen istek oranı bunu aşarsa tarama geçersiz


def _metin(el) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ") if el else "").strip()


def il_secenekleri(govde: str) -> list[tuple[str, str]]:
    s = BeautifulSoup(govde, "lxml")
    out = []
    for o in s.select("select[name=city_box] option"):
        v = (o.get("value") or "").strip()
        ad = _metin(o)
        if v and v != "0" and ad:
            out.append((v, IL_DUZELT.get(ad, ad)))
    return out


def coz(rol: str, govde: str, url: str, il: str | None = None) -> list[dict]:
    """Bir il sonucunu kayıtlara çevirir."""
    s = BeautifulSoup(govde, "lxml")
    out = []
    for b in s.select(".corpaorateOffice"):
        ad = _metin(b.select_one("h2, h3, #centrename"))
        if not ad:
            continue
        adres = tel = eposta = ""
        for tr in b.select("tr"):
            td = tr.find_all("td")
            if len(td) < 2:
                continue
            k, v = fold(_metin(td[0])), _metin(td[1])
            if "adres" in k:
                adres = v
            elif "telefon" in k:
                tel = v
            elif "posta" in k:
                eposta = v
        out.append({"bayi_adi": ad, "il": il or "", "ilce": "", "adres": adres,
                    "telefon": tel, "email": eposta, "website": "", "rol": rol})
    return out


def _ad_anahtari(ad: str) -> str:
    # Parantez fold'dan ÖNCE atılmalı: fold noktalama işaretlerini
    # siliyor, "(7/24 Açık)" sonra yakalanamıyordu (Üsküdar merkezi
    # bu yüzden birleşmedi, 23 Kasım).
    a = fold(re.sub(r"\(.*?\)", " ", ad))
    # Önder Motor merkezleri: satışta SHOWROOM, serviste SERVIS yazıyor
    a = re.sub(r"\b(showroom|servis)\b", " ", a)
    return re.sub(r"[^a-z0-9]", "", a)


def _adres_anahtari(adres: str) -> str:
    return re.sub(r"[^a-z0-9]", "", fold(adres))


def _ortak_ad(ad: str) -> str:
    """Birleşen merkez kaydında SHOWROOM/SERVİS kelimesini at."""
    a = re.sub(r"\s*\b(SHOWROOM|SERVİS|SERVIS)\b\s*/?\s*", " ", ad, flags=re.I)
    return re.sub(r"\s+", " ", a).strip(" /-")


_GENEL = {"hero", "merkez", "showroom", "servis", "sube", "subesi"}


def _ayni_isyeri(a: dict, b: dict) -> bool:
    """İki liste satırı aynı işyeri mi?

    Adres belirleyici: adres benzer değilse aynı ad bile olsa AYRI ŞUBE.
    Adres benzerse adlar da örtüşmeli (aynı adreste iki ayrı firma
    olabiliyor). Yazım farkları (EMİROĞLU/EMIROGLU, "SOK. NO : 4"/"SK.
    NO:4", "BALKANOGLU MAD."/"BALKANOĞLU MADENCİLİK") eşleşir.

    Bunu modülde yapmak ŞART: ayrı bırakılırsa veritabanı ikisini aynı
    eski kayda yazıyor, ikincisi birincinin rolünü eziyor ve firma
    "sadece servis" görünüyordu (Elazığ, Bodrum, Şarkışla, Çanakkale,
    Tarsus — 23 Kasım ilk tarama).
    """
    if a["il"] != b["il"]:
        return False
    if not adres_benzer(a["adres"], b["adres"]):
        return False
    if _ad_anahtari(a["bayi_adi"]) == _ad_anahtari(b["bayi_adi"]):
        return True
    ka = _ayirt_edici(a["bayi_adi"]) - _GENEL
    kb = _ayirt_edici(b["bayi_adi"]) - _GENEL
    return bool(ka & kb)


def birlestir(kayitlar: list[dict]) -> list[dict]:
    """Şube kuralı: aynı işyeri (ad + adres) → tek kayıt; adres farklıysa ayrı."""
    sonuc: list[dict] = []
    for k in kayitlar:
        var = next((v for v in sonuc if _ayni_isyeri(v, k)), None)
        if var is None:
            sonuc.append(dict(k))
            continue
        if var["rol"] != k["rol"]:
            var["rol"] = "satis_servis"
            if var["bayi_adi"] != k["bayi_adi"]:
                # Satış adı esas; SHOWROOM/SERVİS farkı varsa ortak ada indir
                satis = var if var.get("_ilk_rol") != "servis" else k
                var["bayi_adi"] = _ortak_ad(satis["bayi_adi"])
            # Bayi sayfasındaki numara esas, yoksa servisinki.
            if not var["telefon"]:
                var["telefon"] = k["telefon"]
    return sonuc


def getir(oturum) -> list[dict]:
    hepsi: list[dict] = []
    denendi = hata = 0
    for rol, url in KAYNAKLAR.items():
        y = oturum.get(url, timeout=60)
        if y.status_code >= 400:
            raise RuntimeError(f"{rol} sayfası HTTP {y.status_code} "
                               "(Cloudflare engeli olabilir)")
        iller = il_secenekleri(y.text)
        if len(iller) < _EN_AZ_IL:
            raise RuntimeError(f"{rol} sayfasında il listesi okunamadı "
                               f"({len(iller)} il) — sayfa değişmiş olabilir")
        n_rol = 0
        for deger, il in iller:
            denendi += 1
            try:
                r = oturum.post(url, data={"city_box": deger, "ara": "Ara"},
                                headers={"Referer": url, "Origin": TABAN},
                                timeout=60)
                r.raise_for_status()
                ks = coz(rol, r.text, url, il=il)
            except Exception as e:  # noqa: BLE001
                hata += 1
                print(f"    ✗ Hero/{rol}/{il}: {str(e)[:60]}", flush=True)
                continue
            for k in ks:
                k["_ilk_rol"] = rol
            hepsi.extend(ks)
            n_rol += len(ks)
            time.sleep(_BEKLE)
        print(f"    Hero/{rol}: {len(iller)} il, {n_rol} kayıt", flush=True)

    if denendi and hata / denendi > _HATA_ESIGI:
        raise RuntimeError(f"{hata}/{denendi} istek başarısız — eksik tarama, "
                           "veri korunuyor")
    sonuc = birlestir(hepsi)
    for k in sonuc:
        k.pop("_ilk_rol", None)
    return sonuc
