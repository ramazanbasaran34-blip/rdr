"""Konfigürasyondan sürülen ayrıştırıcı.

70 marka için 70 ayrı Python dosyası yazmıyoruz. Her marka brands.yaml'de
birkaç satırlık bir tarif. Kod hiç değişmiyor, sadece tarif ekleniyor.
"""

import json
import re

from bs4 import BeautifulSoup

from .ilceler import adresten_ilce, ilce_mi, ilceden_il
from .normalize import (clean_adres, clean_phone, clean_text, fold, il_ara, resolve_il,
                         split_il_ilce, title_tr)
from .otomatik import cikar as otomatik_cikar

ALANLAR = ["bayi_adi", "il", "ilce", "adres", "telefon", "email", "website"]


# --------------------------------------------------------------------- HTML
def _pick(node, spec):
    """Tek bir alanı çıkarır.

    spec string ise CSS seçici. Dict ise:
      sel   : CSS seçici (yoksa satırın kendisi)
      attr  : metin yerine bu attribute (href, data-lat ...)
      regex : yakalanan metne uygulanacak, 1. grup alınır
      index : birden çok eşleşmede kaçıncısı (varsayılan 0)
    """
    if spec is None:
        return ""
    if isinstance(spec, str):
        spec = {"sel": spec}

    if spec.get("sel"):
        found = node.select(spec["sel"])
        if not found:
            return ""
        el = found[spec.get("index", 0)] if len(found) > spec.get("index", 0) else found[0]
    else:
        el = node

    val = el.get(spec["attr"], "") if spec.get("attr") else el.get_text(" ")
    val = clean_text(val)

    if spec.get("regex"):
        m = re.search(spec["regex"], val, re.I | re.S)
        val = (m.group(1) if m and m.groups() else (m.group(0) if m else ""))
    return clean_text(val)


def parse_html(html: str, cfg: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select(cfg["row"])
    out = []
    for r in rows:
        rec = {a: _pick(r, cfg.get("fields", {}).get(a)) for a in ALANLAR}
        # şemada olmayan yardımcı alanlar (ör. il+ilçe birleşik hücre)
        for ad, spec in (cfg.get("ekstra_alanlar") or {}).items():
            rec[ad] = _pick(r, spec)
        out.append(rec)
    return out


# --------------------------------------------------------------------- JSON
def _jget(obj, path: str):
    """'data.items[].city' benzeri basit yol. [] listeyi açar."""
    cur = obj
    for part in path.split("."):
        if not part:
            continue
        if part.endswith("[]"):
            cur = cur.get(part[:-2], []) if isinstance(cur, dict) else cur
            return cur if isinstance(cur, list) else []
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list):
            return [(_jget(x, part) if isinstance(x, (dict, list)) else None) for x in cur]
        else:
            return None
    return cur


def parse_json(body: str, cfg: dict) -> list[dict]:
    data = json.loads(body) if isinstance(body, str) else body
    items = _jget(data, cfg["root"]) if cfg.get("root") else data
    if isinstance(items, dict):
        items = list(items.values())
    out = []
    for it in items or []:
        rec = {}
        for a in ALANLAR:
            key = cfg.get("fields", {}).get(a)
            if not key:
                rec[a] = ""
                continue
            v = _jget(it, key) if isinstance(key, str) else ""
            rec[a] = clean_text(str(v)) if v is not None else ""
        out.append(rec)
    return out


# ------------------------------------------------- sayfaya gömülü JS verisi
def _gomulu_al(blok: str, spec) -> str:
    """Gömülü bloktan tek alan çeker.

    spec string ise anahtar adı ('name' → 'name': 'DEĞER').
    dict ise {regex: ...} ile serbest kalıp verilebilir.
    """
    if not spec:
        return ""
    if isinstance(spec, dict):
        desen = spec.get("regex", "")
    else:
        desen = r"['\"]" + re.escape(str(spec)) + r"['\"]\s*:\s*['\"](.*?)['\"]"
    if not desen:
        return ""
    m = re.search(desen, blok, re.S)
    if not m:
        return ""
    return clean_text(m.group(1) if m.groups() else m.group(0))


def parse_gomulu(body: str, cfg: dict) -> list[dict]:
    """Veri sayfaya gömülü bir JS dizisindeyse regex ile çıkarır.

    Kymco gibi siteler bayi listesini geçerli JSON olarak değil, tek tırnaklı
    bir JS nesnesi olarak sayfaya basıyor. json.loads bunu okuyamaz, tarayıcı
    da gerekmez — kalıpla okumak yeter. Tek istek, tüm kayıtlar.

    Tarif:
      gomulu:
        kayit: "..."          # bir kaydı sınırlayan regex
        fields: {bayi_adi: name, adres: address, telefon: phone1}
        ekstra_alanlar: {konum: city}
        rol_alani: {regex: "...", esleme: {yetkili-satici: satis}}
    """
    g = cfg.get("gomulu") or {}
    desen = g.get("kayit")
    if not desen:
        return []

    out = []
    for m in re.finditer(desen, body, re.S):
        blok = m.group(0)
        rec = {a: _gomulu_al(blok, g.get("fields", {}).get(a)) for a in ALANLAR}
        for ad, spec in (g.get("ekstra_alanlar") or {}).items():
            rec[ad] = _gomulu_al(blok, spec)

        rol_cfg = g.get("rol_alani")
        if rol_cfg:
            ham_rol = _gomulu_al(blok, rol_cfg)
            esleme = rol_cfg.get("esleme", {}) if isinstance(rol_cfg, dict) else {}
            if ham_rol in esleme:
                rec["rol"] = esleme[ham_rol]
        out.append(rec)
    return out


# Türkiye dışı konum adları (il alanına düşerse kayıt elenir)
YURTDISI = {
    "kibris", "kuzey kibris", "kktc", "lefkosa", "girne", "magusa",
    "gazimagusa", "guzelyurt", "iskele", "lefke",
}


# ------------------------------------------------- kayıt bazında süzgeç
def kayit_suzgeci(kayitlar: list[dict], cfg: dict) -> list[dict]:
    """Tek listede birden çok marka geliyorsa istenmeyeni eler.

    MJ Group'un ajax ucu (RKS, Kuba, Skyjet, Benelli, Ape Ryder...) markayı
    ayırmadan tüm grubu döner; ayrım her kaydın "Yetkileri" satırında yazar.
    Tarif: kayit_suzgeci: {alan: yetkiler, icermeli: ["Kuba Motor"]}
    """
    s = cfg.get("kayit_suzgeci")
    if not s:
        return kayitlar
    alan = s.get("alan", "")
    gerekli = [fold(x) for x in (s.get("icermeli") or [])]
    if not (alan and gerekli):
        return kayitlar
    return [k for k in kayitlar
            if any(g in fold(str(k.get(alan, ""))) for g in gerekli)]


# ------------------------------------------------------------- son rötuşlar
def finalize(rec: dict, marka: str, kaynak_url: str, cfg: dict) -> dict | None:
    """Ham kaydı standart şemaya oturtur. Adı olmayan kaydı çöpe atar."""
    ad = clean_text(rec.get("bayi_adi", ""))
    if not ad:
        return None

    # İl ve ilçe tek alanda geldiyse ayır (tarifte belirtilmişse)
    birlesik = cfg.get("il_ilce_birlesik")
    if birlesik and rec.get(birlesik):
        il, ilce = split_il_ilce(rec[birlesik])
        rec["il"] = il or rec.get("il", "")
        rec["ilce"] = ilce or rec.get("ilce", "")

    # ================== İL VE İLÇE BELİRLEME ==================
    #
    # Sıralama pahalıya mal oldu; iki ters hata yaşandı:
    #   · Başlık devralma en üstteyken Kadıköy'deki bayiye Zonguldak atandı.
    #   · Adresten ilçe çıkarma üstteyken "BİR ARALIK OKULU YANI" adresi
    #     Iğdır'ın Aralık ilçesine eşleşip il Iğdır oldu; başlık Adıyaman'dı.
    #
    # Doğru sıra: kaydın açık il alanı → adreste yazan il → sayfadaki il
    # başlığı → en son ilçeden çıkarım. İlçe araması bilinen ille SINIRLI,
    # yoksa rastgele kelime eşleşmeleri ili bozuyor.

    il_ad = resolve_il(rec.get("il", ""))                  # 1
    if not il_ad:
        il_ad = il_ara(rec.get("adres", ""))               # 2
    if not il_ad:
        il_ad = resolve_il(rec.get("il_baslik", ""))       # 3

    # İlçe: kaydın kendi alanı, ile göre doğrulanarak
    ham_ilce = clean_text(rec.get("ilce", ""))
    ilce_ad = ""
    if ham_ilce and fold(ham_ilce) in ("merkez", "merkez ilce", "il merkezi",
                                       "sehir merkezi", "merkezi"):
        ham_ilce = ""          # aşağıda il adıyla doldurulacak
    if ham_ilce:
        ilce_ad = ilce_mi(ham_ilce, il_ad)
        if not ilce_ad and not il_ad:
            ilce_ad = ilce_mi(ham_ilce)
        if not ilce_ad:
            for parca in re.split(r"[/,\-–_|]", ham_ilce):
                p2 = parca.strip()
                ilce_ad = ilce_mi(p2, il_ad) or (ilce_mi(p2) if not il_ad else "")
                if ilce_ad:
                    break
        # "İlçe" alanında aslında il adı varsa (Rutec) ili oradan al
        if not ilce_ad and not il_ad:
            il_ad = il_ara(ham_ilce)

    if not ilce_ad:
        ilce_ad = adresten_ilce(rec.get("adres", ""), il_ad)

    if ilce_ad and not il_ad:                              # 4
        il_ad = ilceden_il(ilce_ad)

    # İlçe hâlâ boşsa ve kaynak "Merkez" demişse il adını yaz
    if not ilce_ad and il_ad and fold(clean_text(rec.get("ilce", ""))) in (
            "merkez", "merkez ilce", "il merkezi", "sehir merkezi", "merkezi"):
        ilce_ad = il_ad

    # "Merkez" ilçe adı değil, il merkezini anlatan bir sözcük. Kullanıcı
    # listede "Aksaray / Merkez" değil doğrudan "Aksaray" görmek istiyor.
    if ilce_ad and fold(ilce_ad) in ("merkez", "merkez ilce", "il merkezi",
                                     "sehir merkezi", "merkezi") and il_ad:
        ilce_ad = il_ad

    # SON KONTROL: il alanı gerçek bir il mi?
    #
    # Bazı siteler il alanına İLÇE yazıyor (Yuki'de "Antakya", "İzmit").
    # Böyle kayıtlar veritabanında sahte il yaratıyordu; 81 il beklenirken
    # 83 görünüyordu. İl tanınmıyorsa ilçe kabul edip gerçek ilini buluyoruz;
    # bulunamazsa il alanını boşaltıyoruz — uydurmuyoruz.
    if il_ad and not il_ara(il_ad):
        aday = ilceden_il(il_ad)
        if aday:
            if not ilce_ad:
                ilce_ad = il_ad
            il_ad = aday
        else:
            il_ad = ""

    # Türkiye dışı konumlar kapsam dışı. Yamaha'nın listesinde KKTC
    # bayisi vardı ve il doğrulanmadığı için "Kıbrıs" diye bir il
    # oluşmuştu. Bu kayıtlar tamamen eleniyor.
    if fold(il_ad) in YURTDISI:
        return None

    # Tutarlılık: ilçe bu ile ait değilse ilçeyi yazma.
    # İl adının kendisi ilçe olarak yazılmışsa (Aksaray/Aksaray) buna izin ver;
    # küçük illerde merkez ilçe il adını taşıyor.
    if ilce_ad and il_ad and fold(ilce_ad) != fold(il_ad) \
            and not ilce_mi(ilce_ad, il_ad):
        ilce_ad = ""

    out = {
        "marka": marka,
        "bayi_adi": ad,
        "il": il_ad,
        "ilce": ilce_ad,
        "adres": clean_adres(rec.get("adres", "")),
        "telefon": clean_phone(rec.get("telefon", "")),
        "email": clean_text(rec.get("email", "")).lower(),
        "website": clean_text(rec.get("website", "")),
        "kaynak_url": kaynak_url,
    }
    if rec.get("rol"):
        out["rol"] = rec["rol"]
    return out


# --------------------------------------------------------------- OTOMATİK
def parse_oto(html: str, cfg: dict) -> list[dict]:
    """Tarif yok — yapıyı sayfadan çıkar. Ayrıntı: bayiradar/otomatik.py"""
    return otomatik_cikar(html)
