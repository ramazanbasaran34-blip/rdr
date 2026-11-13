"""Aynı firmayı farklı kaynaklardan tanıma.

Sorun: bir firma markanın bayi sayfasında sabit hattıyla, servis sayfasında
cep telefonuyla yazılı olabiliyor. Sadece telefona bakarsak aynı firma iki
ayrı kayıt olur ve "hem satış hem servis" bilgisi kaybolur.

Bu modül üç kademeli eşleştirme yapıyor:
  1. Telefon aynı            → kesin aynı firma
  2. Ad çekirdeği + ilçe aynı → aynı firma
  3. Ad benzer + adres benzer → aynı firma

Muhafazakâr davranıyor: şüphede birleştirmiyor. Yanlış birleştirme, ayrı
bırakmaktan daha kötü — iki farklı firmayı tek kayda indirmek veriyi bozar.
"""

import re

from .normalize import fold

# Firma adında ayırt edici olmayan kelimeler. "Yıldız Motor Ltd. Şti." ile
# "Yıldız Motorlu Araçlar San. Tic." aynı firma olabilir; çekirdek "yildiz".
DOLGU = {
    "motor", "motorlu", "motosiklet", "moto", "araclar", "arac", "vasitalari",
    "ticaret", "tic", "sanayi", "san", "ltd", "sti", "as", "a", "s",
    "limited", "anonim", "sirketi", "kollektif", "koll", "ve", "oto",
    "otomotiv", "bisiklet", "servis", "merkezi", "merkez", "grup", "group",
    "pazarlama", "paz", "dis", "ic", "ithalat", "ihracat", "yedek", "parca",
    "aksesuar", "market", "plaza", "center", "sube", "bayi", "yetkili",
    "makina", "makine", "dayanikli", "tuketim", "mallari", "insaat",
}

ADRES_DOLGU = {
    "mah", "mahalle", "mahallesi", "cad", "cadde", "caddesi", "sok", "sokak",
    "no", "blv", "bulvar", "bulvari", "apt", "kat", "d", "ic", "kapi",
    "osb", "sanayi", "sitesi", "site", "blok", "daire", "plaza",
    "apartmani", "apartman", "merkezi", "is", "cars", "carsi", "merkez",
}


def ad_cekirdegi(ad: str) -> str:
    """Firma adından ayırt edici kelimeleri süzer.

    'YILDIZ MOTOR TİCARET LTD. ŞTİ.' -> 'yildiz'
    'ÖZ ŞAHİN MOTOSİKLET'            -> 'oz sahin'
    """
    kelimeler = [k for k in fold(ad).split() if k and k not in DOLGU]
    # Tek harflik parçaları at (kısaltma artıkları)
    kelimeler = [k for k in kelimeler if len(k) > 1]
    return " ".join(kelimeler)


def adres_anahtari(adres: str) -> str:
    """Adresten sokak/numara çekirdeğini çıkarır."""
    if not adres:
        return ""
    p = fold(adres)
    # Numaraları koru, bunlar ayırt edici
    kelimeler = [k for k in p.split() if k not in ADRES_DOLGU and len(k) > 1]
    return " ".join(kelimeler[:6])


def _ortak_oran(a: str, b: str) -> float:
    """İki metnin ortak kelime oranı (Jaccard)."""
    A, B = set(a.split()), set(b.split())
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)


# Şirket eklerini eleyip ayırt edici kelimeleri bırakır.
_GENEL_EK = {
    "san", "sanayi", "tic", "ticaret", "ltd", "limited", "sti", "sirketi",
    "as", "ve", "insaat", "taahhut", "turizm", "pazarlama", "otomotiv",
    "motor", "motorlu", "araclar", "motosiklet", "bisiklet", "grup",
}


# Parantez içi AÇIKLAMA, firma adının parçası değil: "EYMEN MOTOR
# (Önder Motor)" kaydı, hangi merkeze bağlı olduğunu belirtmek için
# böyle yazılıyor. Eşleştirmede sayılırsa "Önder Motor Merkez 1" ile
# ortak kelime çıkıp iki AYRI firma birleşiyordu.
_PARANTEZ = re.compile(r"\([^)]*\)")


def _ayirt_edici(ad: str) -> set:
    cekirdek = _PARANTEZ.sub(" ", ad or "")
    k = {w for w in fold(cekirdek).split() if len(w) > 2 and w not in _GENEL_EK}
    # Parantez dışında hiçbir şey kalmadıysa parantez içini kullan
    return k or {w for w in fold(ad or "").split()
                 if len(w) > 2 and w not in _GENEL_EK}


def adres_belirtecleri(adres: str) -> set:
    """Adresin ayırt edici kelimeleri (mah/cad/sok gibi dolgular atılır)."""
    return {k for k in fold(adres or "").split()
            if k not in ADRES_DOLGU and len(k) > 1}


_KAPI = re.compile(r"\bno\s*[:.]?\s*(\d{1,4})|\b(\d{1,4})\s*/\s*[a-zA-Z]\b", re.I)
# "431A" ile "431 A" aynı sayılsın diye rakam-harf sınırına boşluk koyuyoruz
_RAKAM_HARF = re.compile(r"(\d)([a-z])|([a-z])(\d)", re.I)


# Adres alanına ikinci bir adres iliştirilebiliyor:
# "... NO: 42 AA SEVKİYAT ADRESİ: ECE MAH. ..." — karşılaştırmada asıl
# adresi kullanıyoruz, yoksa aynı firma iki ayrı yer sanılıyor.
_EK_ADRES = re.compile(
    r"\s*(sevkiyat|teslimat|fatura|kargo)\s*adres[iı]?\s*:.*$", re.I | re.S)


def asil_adres(adres: str) -> str:
    return _EK_ADRES.sub("", adres or "").strip()


def kapi_no(adres: str) -> str:
    """Adresteki kapı numarası.

    En güçlü ayırt edici: "NO: 20" ile "NO: 10" aynı sokakta ama AYRI
    işyeri. Yalnız kelime örtüşmesine bakınca bunlar aynı sanılıyordu
    (Çakmakçı, Remzi Özsoy, Ethemoğlu tek koda düşmüştü).
    """
    m = _KAPI.search(asil_adres(adres))
    return (m.group(1) or m.group(2)) if m else ""


def adres_belirtecleri(adres: str) -> set:
    """Adresin ayırt edici kelimeleri (mah/cad/sok gibi dolgular atılır)."""
    # İki kez: "4A11" tek geçişte "4 A11" oluyor, ikinci geçiş "4 A 11"
    # yapıyor; karşı taraftaki "NO: 4A BLOK DAİRE: 11" ile eşleşsin.
    d = asil_adres(adres)
    for _ in range(2):
        d = _RAKAM_HARF.sub(lambda m: " ".join(x for x in m.groups() if x), d)
    return {k for k in fold(d).split()
            if k not in ADRES_DOLGU and len(k) > 1}


def adres_benzer(a: str, b: str, esik: float = 0.5) -> bool:
    """İki adres aynı yeri mi gösteriyor?

    TEK KAYNAK: hem kayıt eşleştirme hem cari kod üretimi bu fonksiyonu
    kullanıyor. İkisi ayrı ayrı yazılıydı ve farklı sonuç veriyordu.

    Katı eşitlik işe yaramıyor: aynı yer sayfadan sayfaya farklı yazılıyor
    ("... NO:2/B ATAŞEHİR/İSTANBUL" ile "... NO:2/B ATAŞEHİR"). Eşitlik
    arayınca 45 kayıt boş yere ikiye bölünüyordu. Bu yüzden önce kapı
    numarasına, sonra kelime örtüşmesine bakıyoruz.
    """
    ka, kb = kapi_no(a), kapi_no(b)
    if ka and kb and ka != kb:
        return False
    A, B = adres_belirtecleri(a), adres_belirtecleri(b)
    if not A or not B:
        return True
    if A <= B or B <= A:
        return True
    # KAPSAMA oranı (kesişim / kısa adres), birleşim değil. Aynı adres
    # bir yerde ayrıntılı yazılıyor ("... ZEREN SANAYİ SİTESİ NO: 4A
    # BLOK DAİRE: 11"), başka yerde sade ("... No: 4A11 Urla/İzmir").
    # Birleşime bölünce fazladan kelimeler oranı düşürüp aynı yeri iki
    # ayrı adres gösteriyordu. Farklı kapı numarası zaten yukarıda elendi.
    return len(A & B) / min(len(A), len(B)) >= 0.6


def ayni_firma_mi(a: dict, b: dict) -> tuple[bool, str]:
    """İki kayıt aynı firma mı? (evet_mi, gerekçe)"""
    # 1. Telefon — güçlü kanıt AMA tek başına yetmiyor.
    #
    # Zincir bayiler şubelerinde aynı merkezi numarayı kullanıyor.
    # Yalnızca telefona bakınca Bajaj'da 7 gerçek satış noktası tek
    # kayda iniyordu (Hatay/Kenan Uslu, Mersin/Çetinkaya Moto,
    # İstanbul/Mustafa Oktay, Denizli/Yiğitler...). Bu yüzden telefon
    # tutsa bile ADRESLER açıkça farklıysa ayrı nokta sayılıyor.
    if a.get("telefon") and a.get("telefon") == b.get("telefon"):
        # AYNI İLÇEDE aynı numara → aynı işyeri. Adres yazımı sayfadan
        # sayfaya değişebiliyor ("Mimar Sinan Mah. 6045 Sok." vs
        # "MİMAR SİNAN MAH.6045 SOK."), bu yüzden adres farkına bakmıyoruz.
        #
        # SYM'de bunu yapmayınca 29 firma iki kez sayılıyordu: bayi
        # sayfasında "MANAVGAT MOTOR / YASİN AĞGEDİK", servis sayfasında
        # "YASİN AĞGEDİK" yazdığı için biri "sadece bayi", öteki "sadece
        # servis" görünüyordu. Oysa tek işyeri ve satış+servis.
        ia = fold(a.get("ilce", "") or "")
        ib = fold(b.get("ilce", "") or "")
        if ia and ib and ia == ib:
            # Aynı numarayı FARKLI firmalar da kullanabiliyor. Niğde'de
            # "HAFIZLAR OTOMOTİV" ile "MERTAS PAZARLAMA" aynı numarada
            # ve tek firmaya iniyorlardı. Adlar hiç ortak kelime
            # taşımıyorsa ayrı işyeri sayıyoruz.
            ka = _ayirt_edici(a.get("bayi_adi", ""))
            kb = _ayirt_edici(b.get("bayi_adi", ""))
            if ka and kb and not (ka & kb):
                return False, "aynı telefon, farklı firma adı"
            # ADRES BELİRLEYİCİ: aynı ilçede, aynı numarayla çalışan iki
            # AYRI şube olabiliyor. CFMoto/Edremit'te Özdemir Mağazaları
            # hem Altınkum hem Camivasat şubesiyle listede; Bayhas Motors
            # da böyle. Bunlar ayrı bayi sayılmalı.
            # Yazım farkı bölmesin diye eşitlik değil benzerlik arıyoruz.
            if not adres_benzer(a.get("adres", ""), b.get("adres", "")):
                return False, "aynı telefon, farklı adres"
            return True, "telefon + aynı ilçe + aynı adres"

        # FARKLI ilçede aynı numara → zincir bayinin ayrı şubesi.
        # Bajaj'da 7 gerçek nokta bu yüzden tek kayda iniyordu.
        if ia and ib and ia != ib:
            return False, "aynı telefon, farklı ilçe"

        # İlçe bilinmiyorsa eski davranış: adres farkı ayırt edici.
        aa = adres_anahtari(a.get("adres", ""))
        ab = adres_anahtari(b.get("adres", ""))
        if aa and ab and aa != ab:
            return False, "aynı telefon, farklı adres"
        return True, "telefon"

    ca, cb = ad_cekirdegi(a.get("bayi_adi", "")), ad_cekirdegi(b.get("bayi_adi", ""))
    if not ca or not cb:
        return False, ""
    # Çekirdek çok kısaysa ayırt edici değil ("mondial" gibi tek kelime marka
    # adı kalıyorsa aynı ilçedeki bütün bayiler tek kayda iniyordu)
    if len(ca) < 4 or len(cb) < 4:
        return False, ""

    # İKİSİNİN DE telefonu var ve FARKLI → güçlü ayrım kanıtı.
    #
    # Bu normal bir durum: bayi hattı ayrı, servis hattı ayrı olabiliyor.
    # Mondial'de "OMER ARAS - MONDI MOTOR" iki kez çıkıyordu, biri satış biri
    # servis, farklı numaralarla. Ama adres de yoksa eskiden birleşemiyordu.
    #
    # Ölçüt: adres varsa adres tutmalı; adres YOKSA ad çekirdeği birebir aynı
    # ve aynı ilçe olmalı. İkisi de yoksa ayrı bırakılır.
    tel_a, tel_b = a.get("telefon", ""), b.get("telefon", "")
    if tel_a and tel_b and tel_a != tel_b:
        aa = adres_anahtari(a.get("adres", ""))
        ab = adres_anahtari(b.get("adres", ""))
        if aa and ab:
            if _ortak_oran(aa, ab) < 0.7:
                return False, ""
        else:
            # Adres bilinmiyor: ad ve ilçe birebir tutmalı
            ia0, ib0 = fold(a.get("ilce", "")), fold(b.get("ilce", ""))
            if not (ca == cb and ia0 and ia0 == ib0):
                return False, ""

    ia, ib = fold(a.get("ilce", "")), fold(b.get("ilce", ""))
    ila, ilb = fold(a.get("il", "")), fold(b.get("il", ""))

    # Farklı ildeyse aynı firma olamaz
    if ila and ilb and ila != ilb:
        return False, ""
    # Farklı ilçedeyse de birleştirme. Zincir bayiler aynı adı taşıyor
    # ("Öz Şahin Motosiklet" Kadıköy'de de var Pendik'te de) ve bunlar
    # ayrı şubeler — tek kayda indirmek yanlış olur.
    if ia and ib and ia != ib:
        return False, ""

    # 2. Ad çekirdeği birebir + aynı ilçe + ADRES ÇELİŞMİYOR
    #    Adres şartı olmadan aynı ilçedeki ŞUBELER birleşiyordu: KOÇ
    #    MOTOR'un Hendek/Pamukova şubeleri, Bayhas Motors gibi. Aynı ad
    #    aynı ilçede iki ayrı kapı numarası varsa iki ayrı bayidir.
    if ca == cb and ia and ia == ib:
        if adres_benzer(a.get("adres", ""), b.get("adres", "")):
            return True, "ad+ilçe"
        return False, "aynı ad ve ilçe, farklı adres"

    # 3. Ad çok benzer + adres benzer
    ad_oran = _ortak_oran(ca, cb)
    if ad_oran >= 0.6:
        aa = adres_anahtari(a.get("adres", ""))
        ab = adres_anahtari(b.get("adres", ""))
        if aa and ab and _ortak_oran(aa, ab) >= 0.5:
            return True, "ad+adres"
        # Adres yoksa: ad birebir aynı, aynı il, ve en az birinde ilçe yok
        if ca == cb and ila and ila == ilb and not (ia and ib):
            return True, "ad+il"

    return False, ""


def eslesme_anahtarlari(rec: dict) -> list[str]:
    """Bir kaydın hızlı arama için üreteceği anahtarlar.

    Veritabanında her kaydı her kayıtla karşılaştırmak pahalı; bu anahtarlarla
    önce aday havuzu daraltılır, sonra ayni_firma_mi ile kesinleştirilir.
    """
    an = []
    if rec.get("telefon"):
        an.append("t:" + rec["telefon"])
    c = ad_cekirdegi(rec.get("bayi_adi", ""))
    if c:
        an.append("a:" + c + "|" + fold(rec.get("il", "")))
        ilk = c.split()[0] if c.split() else ""
        if ilk and len(ilk) > 3:
            an.append("k:" + ilk + "|" + fold(rec.get("ilce", "")))
    return an


# ---------------------------------------------------------------- roller
ROL_ADI = {
    "satis": "Satış",
    "servis": "Servis",
    "satis_servis": "Satış + Servis",
}


def rolleri_birlestir(mevcut: str, yeni: str) -> str:
    """İki rolü birleştirir. Satış + Servis = ikisi birden."""
    if not mevcut:
        return yeni
    if mevcut == yeni:
        return mevcut
    kume = set()
    for r in (mevcut, yeni):
        kume.update(r.split("_") if r == "satis_servis" else [r])
    if "satis" in kume and "servis" in kume:
        return "satis_servis"
    return mevcut or yeni
