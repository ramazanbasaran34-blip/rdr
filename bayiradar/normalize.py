"""Türkçe metin normalizasyonu ve il/ilçe eşleştirme.

Bu modül projenin en kritik parçası. 70 farklı site il/ilçe adını 70 farklı
şekilde yazıyor: "İSTANBUL", "Istanbul", "İstanbul / Kadıköy", "IST.", "Afyon"
vs "Afyonkarahisar", "İçel" vs "Mersin". Hepsini tek bir anahtara indirgemeden
filtreleme çalışmaz.
"""

import re
import unicodedata

# Türkçe'ye özgü büyük/küçük harf dönüşümü (Python'un default lower() I -> i yapar, yanlış)
_TR_LOWER = str.maketrans("IİĞÜŞÖÇ", "ıiğüşöç")
_TR_UPPER = str.maketrans("iığüşöç", "İIĞÜŞÖÇ")

# Eşleştirme için ASCII katlama
_FOLD = str.maketrans("çğıöşüÇĞİÖŞÜâîû", "cgiosucgiosuaiu")


def tr_lower(s: str) -> str:
    """Türkçe kurallarına uygun küçük harf. 'İSTANBUL' -> 'istanbul'"""
    if not s:
        return ""
    return s.translate(_TR_LOWER).lower()


def tr_upper(s: str) -> str:
    if not s:
        return ""
    return s.translate(_TR_UPPER).upper()


def mojibake_onar(metin: str) -> str:
    """Yanlış kodlamayla okunmuş Türkçe metni onarır.

    Sunucu kodlama başlığı göndermezse tarayıcı UTF-8 baytları latin-1 gibi
    okur: "İstanbul" → "Ä°stanbul", "Şişli" → "ÅiÅli". Bu metinler il/ilçe
    eşleşmesinde tanınmıyor. Onarım başarısızsa metin olduğu gibi döner.
    """
    if not metin or not any(c in metin for c in "ÃÄÅÂ"):
        return metin
    try:
        onarilmis = metin.encode("latin-1").decode("utf-8")
        # Onarım Türkçe harf ürettiyse kabul et
        if any(c in onarilmis for c in "çğıöşüÇĞİÖŞÜ"):
            return onarilmis
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return metin


def fold(s: str) -> str:
    """Eşleştirme anahtarı üretir: küçük harf + ASCII + tek boşluk + noktalama yok.

    'İSTANBUL / Kadıköy' -> 'istanbul kadikoy'
    Yanlış kodlanmış metinler ("Ä°stanbul") önce onarılır.
    """
    if not s:
        return ""
    if any(c in s for c in "ÃÄÅÂ"):
        s = mojibake_onar(s)
    s = tr_lower(s).translate(_FOLD)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def title_tr(s: str) -> str:
    """Görüntüleme için düzgün Türkçe başlık: 'KADIKÖY' -> 'Kadıköy'"""
    if not s:
        return ""
    parts = []
    for w in tr_lower(s).split():
        parts.append(w[0].translate(_TR_UPPER).upper() + w[1:] if w else w)
    return " ".join(parts)


def clean_text(s: str) -> str:
    """HTML'den gelen metni temizler ve BOZUK TÜRKÇEYİ ONARIR.

    Kodlama başlığı göndermeyen sitelerde Türkçe harfler bozuk geliyor
    ("MUSTAFAKEMALPAÅA", "SARAÃOÄLU"). Bu onarım eskiden yalnızca il/ilçe
    eşleşmesinde yapılıyordu; firma adı ve adres bozuk hâliyle kaydediliyor,
    aramada ve tekilleştirmede eşleşmiyordu. Artık HER metin alanı buradan
    geçtiği için bütün markalarda tek noktadan onarılıyor.
    """
    if not s:
        return ""
    s = mojibake_onar(s)
    s = s.replace("\xa0", " ").replace("\u200b", "")
    # Türkçe "İ" sonrası kalan birleştirici nokta (U+0307) — casefold
    # artığı; anahtar üretiminde sessizce eşleşmeyi bozuyordu.
    s = s.replace("\u0307", "")
    return re.sub(r"\s+", " ", s).strip()


# Bazı siteler adresi etiketiyle birlikte veriyor:
#   "Adres: 50.Yıl Mah. ..."        (Motolux)
#   "Adres 100. Yıl Mah. ... Telefon"  (Regal Raptor — sonda da etiket var)
# 384 kayıtta görüldü. Etiketleri baştan ve sondan kırpıyoruz.
_ADRES_BAS = re.compile(r"^\s*(?:adres|address)\s*[:\-–]?\s*", re.I)
_ADRES_SON = re.compile(r"\s*(?:telefon|tel|gsm|e-?posta|e-?mail)\s*[:\-–]?\s*$", re.I)


def clean_adres(s: str) -> str:
    """Adres metnini temizler ve etiket kalıntılarını atar."""
    s = clean_text(s)
    onceki = None
    while s != onceki:            # "Adres : Telefon" gibi üst üste gelenler
        onceki = s
        s = _ADRES_BAS.sub("", s)
        s = _ADRES_SON.sub("", s)
    return s.strip(" ·-–,")


def clean_phone(s: str) -> str:
    """Telefonu +90XXXXXXXXXX formatına indirger. Tekilleştirme için kritik."""
    if not s:
        return ""
    d = re.sub(r"\D", "", s)
    if len(d) == 10:
        d = "90" + d
    elif len(d) == 11 and d.startswith("0"):
        d = "90" + d[1:]
    elif len(d) == 12 and d.startswith("90"):
        pass
    else:
        return clean_text(s)
    return "+" + d


# --- İl adı takma adları ------------------------------------------------------
# Sitelerin kullandığı eski / kısaltılmış adlar -> resmi ad
IL_ALIAS = {
    "afyon": "Afyonkarahisar",
    "icel": "Mersin",
    "k maras": "Kahramanmaraş",
    "kmaras": "Kahramanmaraş",
    "maras": "Kahramanmaraş",
    "urfa": "Şanlıurfa",
    "s urfa": "Şanlıurfa",
    "antep": "Gaziantep",
    "g antep": "Gaziantep",
    "ist": "İstanbul",
    "ank": "Ankara",
    "izm": "İzmir",
    "hakkari": "Hakkâri",
}

ILLER = [
    "Adana", "Adıyaman", "Afyonkarahisar", "Ağrı", "Amasya", "Ankara", "Antalya",
    "Artvin", "Aydın", "Balıkesir", "Bilecik", "Bingöl", "Bitlis", "Bolu",
    "Burdur", "Bursa", "Çanakkale", "Çankırı", "Çorum", "Denizli", "Diyarbakır",
    "Edirne", "Elazığ", "Erzincan", "Erzurum", "Eskişehir", "Gaziantep",
    "Giresun", "Gümüşhane", "Hakkâri", "Hatay", "Isparta", "Mersin", "İstanbul",
    "İzmir", "Kars", "Kastamonu", "Kayseri", "Kırklareli", "Kırşehir", "Kocaeli",
    "Konya", "Kütahya", "Malatya", "Manisa", "Kahramanmaraş", "Mardin", "Muğla",
    "Muş", "Nevşehir", "Niğde", "Ordu", "Rize", "Sakarya", "Samsun", "Siirt",
    "Sinop", "Sivas", "Tekirdağ", "Tokat", "Trabzon", "Tunceli", "Şanlıurfa",
    "Uşak", "Van", "Yozgat", "Zonguldak", "Aksaray", "Bayburt", "Karaman",
    "Kırıkkale", "Batman", "Şırnak", "Bartın", "Ardahan", "Iğdır", "Yalova",
    "Karabük", "Kilis", "Osmaniye", "Düzce",
]

# plaka kodu -> il  (bazı siteler ?il=34 şeklinde sorgu alıyor)
IL_KODU = {i + 1: ad for i, ad in enumerate(ILLER)}
IL_BY_FOLD = {fold(ad): ad for ad in ILLER}


def resolve_il(raw: str) -> str:
    """Serbest metinden resmi il adını bulur. Bulamazsa temizlenmiş halini döner."""
    f = fold(raw)
    if not f:
        return ""
    if f in IL_BY_FOLD:
        return IL_BY_FOLD[f]
    if f in IL_ALIAS:
        return IL_ALIAS[f]
    # "istanbul avrupa", "istanbul (anadolu)" gibi ekleri kırp
    for key, ad in IL_BY_FOLD.items():
        if f.startswith(key + " ") or f == key:
            return ad
    return title_tr(raw)


def split_il_ilce(raw: str) -> tuple[str, str]:
    """'İstanbul / Kadıköy' veya 'KADIKÖY - İSTANBUL' -> ('İstanbul', 'Kadıköy')

    Çoğu sitede il ve ilçe tek hücrede birleşik geliyor. Hangi tarafın il
    olduğunu il listesine bakarak anlıyoruz, sıraya güvenmiyoruz.
    """
    if not raw:
        return "", ""
    parts = [p for p in re.split(r"[/\-–,|]", raw) if p.strip()]
    if len(parts) == 1:
        tek = resolve_il(parts[0])
        return (tek, "") if fold(tek) in IL_BY_FOLD else ("", title_tr(parts[0]))
    il, ilce = "", ""
    for p in parts:
        cand = resolve_il(p)
        if fold(cand) in IL_BY_FOLD and not il:
            il = cand
        else:
            ilce = title_tr(p)
    if not il:
        il = resolve_il(parts[0])
        ilce = title_tr(parts[-1])
    return il, ilce


def matches(value: str, query: str) -> bool:
    """Filtre eşleşmesi. Boş sorgu her şeyi geçirir."""
    if not query:
        return True
    return fold(query) in fold(value)


def phone_display(s: str) -> str:
    """Depoda +905321234567, ekranda 0532 123 45 67."""
    if not s or not s.startswith("+90") or len(s) != 13:
        return s
    d = s[3:]
    return f"0{d[:3]} {d[3:6]} {d[6:8]} {d[8:]}"


# İl adından sonra gelen yol/yer eki. "KAYSERİ YOLU", "İZMİR BULVARI",
# "ESKİ EDİRNE ASFALTI", "ORDU CAD." — bunlar sokak adı, o ilde olduğu
# anlamına gelmez. Adana'daki bir bayinin adresinde "KAYSERİ YOLU" geçiyor
# diye il Kayseri yazılamaz.
_YOL_EKI = re.compile(
    r"^\s*(yolu|yol|caddesi|cad|cd|bulvari|bulvar|blv|asfalti|asfalt|"
    r"mahallesi|mah|mh|sokak|sok|sk|sitesi|apartmani|apt|"
    r"kavsagi|kavsak|otoyolu|karayolu|istikameti|yonu|cikisi)\b")


def il_ara(metin: str) -> str:
    """Serbest metinde geçen il adını bulur. Bulamazsa boş döner.

    Yalnızca 81 ilden biri gerçekten geçiyorsa kabul eder. Ayrıca il adının
    ardından yol/cadde eki geliyorsa o eşleşme sayılmaz — sokak adları
    yüzünden yanlış il atanıyordu.
    """
    if not metin:
        return ""
    f = " " + fold(metin) + " "
    bulunan = ""
    for anahtar, ad in IL_BY_FOLD.items():
        for m in re.finditer(r"(?<= )" + re.escape(anahtar) + r"(?= )", f):
            # Yol eki hemen sonra ya da bir kelime sonra gelebilir:
            # "kayseri yolu" ve "izmir aydin caddesi" ikisi de sokak adı.
            kalan = f[m.end():].lstrip()
            if _YOL_EKI.match(kalan):
                continue
            parcalar = kalan.split(None, 2)
            if len(parcalar) >= 2 and _YOL_EKI.match(parcalar[1]):
                continue
            if len(anahtar) > len(fold(bulunan)):
                bulunan = ad
            break
    if not bulunan:
        for takma, ad in IL_ALIAS.items():
            if f" {takma} " in f:
                bulunan = ad
                break
    return bulunan


