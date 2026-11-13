#!/usr/bin/env python3
"""Spormoto (KTM ve Husqvarna) bayi/servis tablolarını ayrıştırır.

Neden ayrı kod: iki marka da tablepress tablosu kullanıyor ve hücre yapısı
otomatik çözücünün beklediği kalıba uymuyor. Tek hücrede üç bilgi var,
aralarındaki tek ayraç <br>:

    <td class="column-1">Adana</td>
    <td class="column-2"><strong>SÜPERMOTO</strong><br />
        Tel: 0 (322) 255 12 55 <br />
        Yüzüncüyıl Mah. ... Çukurova</td>

CSS seçicisiyle "ikinci <br>'den sonrası" alınamadığı için hücreyi <br>
sınırlarından bölüyoruz. İl ayrı sütunda hazır; ilçe adresin sonunda.

Ağ gerekmez, kaydedilmiş HTML üzerinde çalışır:

    python spormoto_tara.py --test          # ham/ altındaki dosyalarla dene
    python spormoto_tara.py                 # canlı çek + veritabanına işle
    python spormoto_tara.py --kuru          # canlı çek, yazma
"""

from __future__ import annotations

import gzip
import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

from bayiradar.parse import finalize

HAM = Path("ham")

# marka -> {rol: url}
KAYNAKLAR = {
    "KTM": {
        "satis":  "https://spormoto.com/ktm/bayiler/",
        "servis": "https://spormoto.com/ktm/ktm-servisler/",
    },
    "Husqvarna": {
        "satis":  "https://spormoto.com/husqvarna/bayiler/",
        "servis": "https://spormoto.com/husqvarna/husqvarna-servisler/",
    },
}

# Test dosyası adları: marka-rol -> ham/<ad>.html.gz
TEST_DOSYA = {
    ("KTM", "satis"): "ktm-satis",
    ("KTM", "servis"): "ktm-servis",
    ("Husqvarna", "satis"): "husqvarna-satis",
    ("Husqvarna", "servis"): "husqvarna-servis",
}

TEL_KALIP = re.compile(r"tel\s*[:.]?\s*([0-9()\s\u00a0/\-]{9,})", re.I)
# Başlık satırı: "Şehir", "Bayi", "İl" gibi tek kelimelik etiketler
BASLIK_KELIME = {"sehir", "şehir", "il", "bayi", "servis", "firma", "adres", ""}


def _hucre_parcalari(td) -> list[str]:
    """Hücreyi <br> sınırlarından bölüp boş olmayan parçaları döner."""
    ham = td.decode_contents()
    parcalar = re.split(r"<br\s*/?>", ham, flags=re.I)
    out = []
    for p in parcalar:
        metin = BeautifulSoup(p, "html.parser").get_text(" ")
        metin = metin.replace("\u00a0", " ")
        metin = re.sub(r"\s+", " ", metin).strip()
        if metin:
            out.append(metin)
    return out


def _telefon_ayikla(parcalar: list[str]) -> tuple[str, list[str]]:
    """Telefon parçasını bulur; kalan parçaları geri verir."""
    tel = ""
    kalan = []
    for p in parcalar:
        m = TEL_KALIP.search(p)
        if m and not tel:
            tel = re.sub(r"\s+", " ", m.group(1)).strip()
            # "Tel: 0 (322) 255 12 55" satırında başka bilgi yoksa parçayı atla
            artik = TEL_KALIP.sub("", p).strip(" -–—,;")
            if artik:
                kalan.append(artik)
            continue
        kalan.append(p)
    return tel, kalan


def tabloyu_coz(html: str) -> list[dict]:
    """tablepress satırlarını ham kayıt sözlüklerine çevirir."""
    soup = BeautifulSoup(html, "html.parser")
    out: list[dict] = []

    for tr in soup.select("table.tablepress tr"):
        hucre = tr.find_all("td")
        if len(hucre) < 2:
            continue

        il = re.sub(r"\s+", " ", hucre[0].get_text(" ")).strip()
        parcalar = _hucre_parcalari(hucre[1])
        if not parcalar:
            continue

        # Başlık satırını ele ("Şehir" | boş)
        if il.casefold() in BASLIK_KELIME and len(parcalar) <= 1:
            continue

        # Ad: varsa <strong>, yoksa ilk parça
        kalin = hucre[1].find(["strong", "b"])
        ad = re.sub(r"\s+", " ", kalin.get_text(" ")).strip() if kalin else parcalar[0]
        if not ad:
            continue

        tel, kalan = _telefon_ayikla(parcalar)
        adres = " ".join(p for p in kalan if p != ad).strip()

        out.append({
            "bayi_adi": ad,
            "il": il,
            "ilce": "",
            "adres": adres,
            "telefon": tel,
            "email": "",
            "website": "",
        })
    return out


def _gomulu_deger(blok: str, anahtar: str) -> str:
    """`name: "DEĞER"` biçimindeki alanı okur (tırnak tipi serbest)."""
    m = re.search(anahtar + r"\s*:\s*([\"'])(.*?)\1", blok, re.S)
    if not m:
        return ""
    return re.sub(r"\s+", " ", m.group(2)).strip()


def gomulu_coz(html: str) -> list[dict]:
    """Satış sayfasındaki `const dealers = [...]` dizisini ayrıştırır.

    Satış sayfası tablo değil; kartlar JS'ten çiziliyor. Dizinin kendisi
    kaynakta düz metin olarak duruyor, tarayıcı gerekmiyor. `type` alanı
    bayi tipini veriyor (distributor / exclusive / dealer ...).
    """
    out: list[dict] = []
    for m in re.finditer(r"\{\s*type\s*:.*?\}", html, re.S):
        blok = m.group(0)
        ad = _gomulu_deger(blok, "name")
        if not ad:
            continue
        out.append({
            "bayi_adi": ad,
            "il": _gomulu_deger(blok, "city"),
            "ilce": "",
            "adres": _gomulu_deger(blok, "address"),
            "telefon": _gomulu_deger(blok, "phone"),
            "email": "",
            "website": "",
        })
    return out


def marka_coz(marka: str, rol: str, html: str, url: str) -> list[dict]:
    cfg: dict = {}
    ham = tabloyu_coz(html)
    if len(ham) < 5:
        # Servis sayfası tablo, satış sayfası gömülü JS dizisi kullanıyor.
        ham = gomulu_coz(html)
    kayitlar = []
    for r in ham:
        r["rol"] = rol
        k = finalize(r, marka, url, cfg)
        if k:
            kayitlar.append(k)
    return kayitlar


# ------------------------------------------------------------------- test
def test() -> int:
    """Kaydedilmiş HTML üzerinde çalışır — ağ yok, saniyeler sürer.

    Eşik marka TOPLAMI üzerinden: satış ve servis ayrı ayrı az olabilir
    (Husqvarna'da site gerçekten 19 satış noktası listeliyor), önemli olan
    markanın toplam kapsamı.
    """
    hata = 0
    toplam: dict[str, list[dict]] = {}

    for (marka, rol), dosya in TEST_DOSYA.items():
        yol = HAM / f"{dosya}.html.gz"
        if not yol.exists():
            print(f"  · {marka}/{rol}: {yol} yok, atlandı")
            continue
        html = gzip.decompress(yol.read_bytes()).decode("utf-8", "replace")
        k = marka_coz(marka, rol, html, KAYNAKLAR[marka][rol])
        toplam.setdefault(marka, []).extend(k)

        ilsiz = sum(1 for x in k if not x.get("il"))
        telsiz = sum(1 for x in k if not x.get("telefon"))
        adressiz = sum(1 for x in k if not x.get("adres"))
        print(f"  {marka:10} {rol:7} → {len(k):3} kayıt "
              f"(ilsiz {ilsiz}, telefonsuz {telsiz}, adressiz {adressiz})")
        for x in k[:2]:
            print(f"        {x['bayi_adi'][:26]:26} | {x.get('il')} / "
                  f"{x.get('ilce')} | {x.get('telefon')}")
        if not k:
            print("        ✗ hiç kayıt çıkmadı")
            hata += 1
        if ilsiz:
            print("        ✗ ilsiz kayıt var")
            hata += 1

    print()
    for marka, k in toplam.items():
        adlar = {(x.get("bayi_adi", ""), x.get("il", "")) for x in k}
        print(f"  {marka:10} TOPLAM {len(k):3} kayıt, {len(adlar)} tekil firma, "
              f"{len({x.get('il') for x in k if x.get('il')})} il")
        if len(k) < 37:
            print("        ✗ marka toplamı 37'nin altında")
            hata += 1
    return hata


# ------------------------------------------------------------------- canlı
def canli(kuru: bool) -> None:
    import requests

    from bayiradar.store import commit_tarama, db, now

    basladi = now()
    basliklar = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) "
                                "Chrome/124.0 Safari/537.36")}
    rapor: dict = {}
    for marka, roller in KAYNAKLAR.items():
        hepsi: list[dict] = []
        for rol, url in roller.items():
            y = requests.get(url, headers=basliklar, timeout=45)
            y.raise_for_status()
            k = marka_coz(marka, rol, y.text, url)
            print(f"  {marka}/{rol}: {len(k)}")
            hepsi.extend(k)
        rapor[marka] = {"kayit": len(hepsi),
                        "il": len({x.get("il") for x in hepsi if x.get("il")}),
                        "ilsiz": sum(1 for x in hepsi if not x.get("il"))}
        if not kuru:
            with db() as con:
                rapor[marka]["db"] = str(commit_tarama(con, marka, hepsi, 1.0,
                                                       basladi))[:200]
    print(json.dumps(rapor, ensure_ascii=False, indent=1))
    HAM.mkdir(exist_ok=True)
    (HAM / "spormoto-tarama.json").write_text(
        json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")


def main() -> None:
    if "--test" in sys.argv:
        h = test()
        print("\n✓ test geçti" if not h else f"\n✗ {h} sorun")
        sys.exit(1 if h else 0)
    canli("--kuru" in sys.argv)


if __name__ == "__main__":
    main()
