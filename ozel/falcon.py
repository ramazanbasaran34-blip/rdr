"""Falcon — tek JSON ucu.

Site üçlü seçim gösteriyor ama arkada tek bir uç var ve ülkenin tamamını
veriyor: /api/bayiler.php → {"tumBayiler": [...]}

Rol ayrımı `typeModel` alanında:
    mb = motosiklet bayi      → satış
    ms = motosiklet servis    → servis
    yp = yedek parça          → motosiklet noktası DEĞİL, elenir

3737 kaydın 2313'ünde hiçbir bayrak yok (yedek parça / diğer cari);
sadece mb veya ms işaretli olanlar alınıyor → ~1215 kayıt.
"""

from __future__ import annotations

import json

MARKA = "Falcon"
UC = "https://falconmotosiklet.com/api/bayiler.php"

KAYNAKLAR = {"hepsi": UC}
TEST = {("Falcon", "hepsi"): "falcon-api.json"}


def coz(rol: str, govde: str, url: str) -> list[dict]:
    d = json.loads(govde) if isinstance(govde, str) else govde
    out = []
    for x in d.get("tumBayiler") or []:
        if not x.get("isAktif", True):
            continue
        tm = x.get("typeModel") or {}
        bayi, servis = bool(tm.get("mb")), bool(tm.get("ms"))
        if not (bayi or servis):
            continue  # yalnızca yedek parça ya da alakasız cari
        rol_ = "satis_servis" if (bayi and servis) else ("satis" if bayi else "servis")

        tel = (x.get("Tel") or x.get("Gsm") or "").strip()
        out.append({
            "bayi_adi": (x.get("Unvani") or "").strip(),
            "il": (x.get("Il") or "").strip(),
            "ilce": (x.get("Ilce") or "").strip(),
            "adres": (x.get("Adres") or "").strip(),
            "telefon": tel,
            "email": "",
            "website": "",
            "rol": rol_,
        })
    return out
