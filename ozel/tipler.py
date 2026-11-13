"""Rol belirlemede ortak kural: SADECE satış ve servis sayılır.

NEDEN BU MODÜL VAR
Markaların bayi listelerinde çoğu zaman üçüncü bir kategori daha var:
yedek parça bayileri. Bunlar motosiklet satmıyor, servis de vermiyor;
listeye girerlerse sayı gerçeğin katlarına çıkıyor. Falcon'da tam bunu
yaşadık: uç 3.737 kayıt döndürüyordu, gerçek satış+servis noktası
1.188'di. Adana/Kozan'da sitede 2 bayi görünürken listemizde 5 vardı.

ASIL TEHLİKE VARSAYILAN ROL
Falcon'daki hata "yedek parçayı satış saymak" kadar, tanımadığı kaydı
da varsayılan olarak satışa yazmaktı. Aynı desen Nanok, Kymco/Vespa/
Piaggio/Suzuki ve Meka ayrıştırıcılarında da vardı. Meka'da 550 kaydın
276'sının açıklaması boştu ve hepsi satış sayılıyordu.

KURAL
Bir kayıt ancak satış ya da servis olduğu AÇIKÇA anlaşılıyorsa
listeye girer. Emin değilsek saymayız: eksik kayıt, uydurma kayıttan
iyidir ve eksik olan bir sonraki turda kaynak düzeldiğinde gelir.

İSİMDEN ROL ÇIKARILMAZ
"Yılmaz Motosiklet ve Yedek Parça Ltd." gerçek bir satış noktası
olabilir. Firma ADINDA yedek parça geçmesi eleme sebebi DEĞİLDİR;
yalnızca kaynağın KATEGORİ alanı belirleyicidir.
"""

from __future__ import annotations

import re
import sys

# Kaynakların kategori alanında yedek parçayı işaret eden ifadeler.
# Yalnızca kategori/tip alanına uygulanır, firma adına asla.
PARCA_ISARET = (
    "yedek parca", "yedekparca", "yedek-parca", "yedek parça",
    "sparepart", "spare part", "spare-part", "spareparts",
    "parca bayi", "parts", "aksesuar",
)

# Türkçe harfler ASCII karşılığına: aksi halde "yedek parça" içindeki
# "ç" düşüp "par a" oluyor ve kalıp hiç tutmuyor.
_TR = str.maketrans({
    "ı": "i", "İ": "i", "I": "i", "i": "i",
    "ğ": "g", "Ğ": "g", "ü": "u", "Ü": "u",
    "ş": "s", "Ş": "s", "ö": "o", "Ö": "o",
    "ç": "c", "Ç": "c", "â": "a", "Â": "a", "î": "i", "û": "u",
})


def sadelestir(t) -> str:
    """Karşılaştırma için tip metnini normalleştirir."""
    s = str(t or "").translate(_TR).lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def parca_mi(tip) -> bool:
    """Kategori alanı yedek parçayı işaret ediyor mu?"""
    s = sadelestir(tip)
    return any(i in s for i in PARCA_ISARET)


def rol_belirle(satis: bool, servis: bool) -> str:
    """Bayraklardan rol. İkisi de yoksa BOŞ döner (kayıt sayılmaz)."""
    if satis and servis:
        return "satis_servis"
    if satis:
        return "satis"
    if servis:
        return "servis"
    return ""


_UYARILAN: set = set()


def tip_rol(tip, esleme: dict, marka: str = "") -> str:
    """Metin tipini role çevirir. Tanımadığını SATIŞ SAYMAZ, eler.

    esleme: tip -> rol sözlüğü. Anahtarlar da sadeleştirilerek
    karşılaştırılıyor; "yetkili-satici" ile "yetkili satici" aynı sayılsın.
    Dönen boş dize "bu kaydı listeye alma" demektir.
    """
    s = sadelestir(tip)
    if not s:
        return ""                       # tipi boş olan kayıt sayılmaz
    if parca_mi(s):
        return ""                       # yedek parça noktası
    duz = {sadelestir(k): v for k, v in esleme.items()}
    rol = duz.get(s)
    if rol:
        return rol
    for anahtar, r in duz.items():
        if anahtar and anahtar in s:
            return r
    # Tanınmayan tip: sessizce satışa yazmak yerine görünür bırak.
    # Aynı tip için tek uyarı yeter, günlüğü boğmasın.
    imza = (marka, s)
    if imza not in _UYARILAN:
        _UYARILAN.add(imza)
        print(f"::warning::[{marka or 'tip'}] tanınmayan kategori "
              f"{tip!r} — kayıtlar sayılmadı", file=sys.stderr)
    return ""
