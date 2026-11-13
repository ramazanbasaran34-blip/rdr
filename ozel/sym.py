"""SYM — tek sayfada tüm ağ, WPBakery akordeon.

NEDEN YENİDEN YAZILDI
Eski tarama 278 kaydın 126'sını Adana'ya atamıştı; adresler apaçık
başka illere aitti (Muratpaşa/Antalya, Erciyes/Kayseri...). Sebep: sayfa
illeri akordeon paneli olarak veriyor ve kayıt ile panel başlığı
arasındaki bağ kurulmadığı için ilk panelin ili (alfabetik olarak ADANA)
herkese yapıştırılmıştı. Ayrıca 225 kayıtta ilçe boştu.

YAPI
    <div class="vc_tta-panel">
      <div class="vc_tta-panel-heading">
        <span class="vc_tta-title-text">ADANA</span>      ← İL
      <div class="vc_tta-panel-body">
        <div class="wpb_wrapper">
          <p><strong>SEYHAN</strong></p>                  ← İLÇE
          <p>MOTO WEST MOTORLU ARAÇLAR</p>                ← FİRMA
          <p>Gürselpaşa Mah. ... Seyhan / Adana</p>       ← ADRES
          <p>0546 749 09 09 – 0322 502 83 11</p>          ← TELEFON

Her il paneli birden çok firma bloğu taşıyor. İl bilgisi panelden,
ilçe blok içindeki <strong>'dan geliyor.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from bayiradar.ilceler import ilce_mi

from .tr import anahtar

MARKA = "SYM"

KAYNAKLAR = {
    "satis":  "https://www.sym-tr.com/bayiler/",
    "servis": "https://www.sym-tr.com/servis/",
}
TEST = {
    ("SYM", "satis"):  "sym-bayiler.html",
    ("SYM", "servis"): "sym-servis.html",
}

TEL = re.compile(r"(?:\+90|0)[\s\(\)\-/\.]*\d{3}[\s\(\)\-/\.]*\d{3}[\s\-/\.]*\d{2}[\s\-/\.]*\d{2}")


def _m(el) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ")).strip() if el else ""


def coz(rol: str, govde: str, url: str) -> list[dict]:
    soup = BeautifulSoup(govde, "html.parser")
    out: list[dict] = []
    gorulen: set[tuple[str, str]] = set()

    for panel in soup.select(".vc_tta-panel"):
        bas = panel.select_one(".vc_tta-title-text")
        il = _m(bas)
        if not il:
            continue

        # Panel içindeki her metin bloğu bir firma
        for blok in panel.select(".wpb_text_column .wpb_wrapper"):
            satirlar = [_m(x) for x in blok.find_all("p")]
            satirlar = [x for x in satirlar if x]
            if not satirlar:
                continue

            # Blok SIRALI: kalın başlık (il/ilçe), firma, adres, telefon.
            # Sıraya güvenmek, "en uzun satır adrestir" tahmininden çok
            # daha sağlam; o tahmin firma adı uzun olunca ikisini
            # yer değiştiriyordu.
            # Başlık genelde <strong> içinde ama bazı bloklarda düz metin.
            # O zaman ilk satır "İL / MERKEZ – İLÇE" kalıbına uyuyorsa
            # başlık kabul ediyoruz; yoksa "MERKEZ – NİLÜFER" firma adı
            # sanılıyordu.
            kalin = blok.find("strong")
            bas = _m(kalin)
            if not bas and satirlar:
                ilk = satirlar[0]
                if re.search(r"(?:^|/)\s*merkez\b|[–\-]", ilk, re.I) and \
                        not TEL.search(ilk) and len(ilk) < 60:
                    bas = ilk
            ilce = ""
            if bas:
                # "BURSA / MERKEZ – OSMANGAZİ 5S" -> OSMANGAZİ
                son = re.split(r"[–\-]", bas)[-1].strip()
                son = re.sub(r"\b\d+\s*S\b", "", son, flags=re.I).strip()
                if son and anahtar(son) != anahtar(il):
                    ilce = son
                elif "/" in bas:
                    aday = bas.split("/")[-1].strip()
                    if anahtar(aday) != anahtar(il):
                        ilce = aday

            # Başlık satırını çıkar, kalanı sırayla oku
            kalan = [x for x in satirlar if x != bas]
            tel = ""
            telsiz = []
            for x in kalan:
                m = TEL.search(x)
                if m and not tel:
                    tel = m.group(0)
                elif not m:
                    telsiz.append(x)

            # Bazı bloklarda başlıktan sonra fazladan bir İLÇE LİSTESİ
            # satırı var: "ÇUKUROVA/ YÜREĞİR/ SARIÇAM/". Firma adı değil,
            # o servisin hizmet verdiği ilçeler. Eğik çizgiyle ayrılmış,
            # her parçası bilinen ilçe adı olan satırları atıyoruz.
            def _ilce_listesi(x: str) -> bool:
                """Gerçekten ilçe listesi mi, yoksa eğik çizgili firma adı mı?

                İlk denemede "eğik çizgi varsa ilçe listesidir" dedim ve
                "DURAN MOTOR / MURAT ERGISI" gibi firma adları elendi.
                Artık her parçanın O İLİN gerçek bir ilçesi olmasını
                şart koşuyoruz.
                """
                if "/" not in x:
                    return False
                parcalar = [k.strip() for k in x.split("/") if k.strip()]
                if len(parcalar) < 2:
                    return False
                return all(ilce_mi(k, il) for k in parcalar)

            telsiz = [x for x in telsiz if not _ilce_listesi(x)]

            ad = telsiz[0] if telsiz else ""
            adres = " ".join(telsiz[1:]) if len(telsiz) > 1 else ""
            if not ad:
                continue

            anahtar_kayit = (anahtar(ad), anahtar(il), anahtar(ilce))
            if anahtar_kayit in gorulen:
                continue
            gorulen.add(anahtar_kayit)

            out.append({
                "bayi_adi": ad,
                "il": il,
                "ilce": ilce,
                "adres": adres,
                "telefon": tel,
                "email": "",
                "website": "",
                "rol": rol,
            })

    return out
