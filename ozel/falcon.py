"""Falcon — tek JSON isteğiyle tüm ağ.

NEDEN ÖZEL MODÜL
Falcon tarayıcı ile ve il seçerek taranıyordu: 81 il × 2 rol = 162
sayfa yükleme. Bu 80 dakikalık sınıra takılıp her turda zaman aşımına
uğruyordu ("Falcon taranıyor has timed out after 80 minutes").

Oysa sitenin kendi JSON ucu var ve TÜM ağı tek istekte veriyor:
    https://falconmotosiklet.com/api/bayiler.php
    {"tumBayiler":[{"Unvani":..,"Il":..,"Ilce":..,"Adres":..,"Gsm":..,
                    "typeModel":{"mb":bool,"yp":bool,"ms":bool}}, ...]}

typeModel BAYRAKLARI — DİKKAT
Uç 3.737 kayıt döndürüyor ama bunların hepsi satış/servis noktası
DEĞİL. Sitenin kendi sayfasında üç ayrı sekme var: Motosiklet
Bayileri, Yedek Parça Bayileri, Yetkili Servisler. Bayraklar bunu
ayırıyor:
    mb = motosiklet bayisi   → satış
    ms = motosiklet servisi  → servis
    yp = yedek parça bayisi  → TEK BAŞINA satış/servis noktası SAYILMAZ

Bayrak dağılımı (5 Eylül 2026 yanıtı):
    hiçbiri  2.313   (düz cari kaydı, listelerde görünmüyor)
    yp       209
    mb/ms li 1.215   → tekilleştirince 1.188 kayıt:
                       466 bayi + 839 servis

Önceki kural "satis = mb veya yp" diyor, bayraksız kayıtları da
varsayılan olarak satışa yazıyordu: 3.023 kayıt, gerçeğin ~2,5 katı.
Adana/Kozan'da sitede 2 bayi görünürken listede 4-5 çıkıyordu.
Şimdi mb/ms şartı var; Kozan tam 2 bayi veriyor ve toplam, Falcon'un
kendi ilan ettiği "400'ü aşan bayi, 500'ü aşan servis" ile örtüşüyor.
"""

from __future__ import annotations

import json
import re

MARKA = "Falcon"

KAYNAKLAR = {"hepsi": "https://falconmotosiklet.com/api/bayiler.php"}
TEST = {("Falcon", "hepsi"): "falcon-api.json"}


def _bayrak(t) -> tuple[bool, bool]:
    """(motosiklet_bayisi, motosiklet_servisi). yp bilerek yok sayılıyor."""
    if not isinstance(t, dict):
        return False, False
    return bool(t.get("mb")), bool(t.get("ms"))


def coz(rol: str, govde: str, url: str) -> list[dict]:
    # Yanıtın başında/sonunda fazladan metin olabiliyor
    m = re.search(r'\{.*"tumBayiler".*\}', govde, re.S)
    ham = m.group(0) if m else govde
    try:
        d = json.loads(ham)
    except json.JSONDecodeError:
        return []

    # Aynı firma birden çok satırda gelebiliyor: Adana/Kozan'da Erdal
    # Baykul biri mb, diğeri yp+ms olarak iki kez geçiyor. İlkini alıp
    # gerisini atmak rolü yanlış sabitliyor; bayrakları birleştiriyoruz.
    birlesik: dict[tuple, dict] = {}
    for b in d.get("tumBayiler") or []:
        ad = (b.get("Unvani") or "").strip()
        if not ad:
            continue
        tel = (b.get("Gsm") or b.get("Tel") or "").strip()
        mb, ms = _bayrak(b.get("typeModel"))
        anahtar = (ad.casefold(), tel)
        k = birlesik.get(anahtar)
        if k is None:
            birlesik[anahtar] = {
                "bayi_adi": ad,
                "il": (b.get("Il") or "").strip(),
                "ilce": (b.get("Ilce") or "").strip(),
                "adres": (b.get("Adres") or "").strip(),
                "telefon": tel,
                "email": (b.get("Email") or "").strip(),
                "website": "",
                "_mb": mb, "_ms": ms,
            }
        else:
            k["_mb"] = k["_mb"] or mb
            k["_ms"] = k["_ms"] or ms
            if not k["adres"]:
                k["adres"] = (b.get("Adres") or "").strip()

    out: list[dict] = []
    for k in birlesik.values():
        mb, ms = k.pop("_mb"), k.pop("_ms")
        if not (mb or ms):
            continue          # yalnızca yedek parça ya da bayraksız cari
        k["rol"] = "satis_servis" if (mb and ms) else ("satis" if mb else "servis")
        out.append(k)
    return out
