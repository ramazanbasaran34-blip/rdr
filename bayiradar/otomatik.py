"""Otomatik ayrıştırma — tarif yazmadan bayi kaydı çıkarır.

63 marka için 63 el yazması tarif sürdürülebilir değil. Bu modül sayfadaki
tekrar eden yapıyı kendisi bulur: kardeşleri aynı sınıfa sahip, içinde telefon
ve adres geçen kapları arar, en yüksek puanlıyı seçer ve alanları ayıklar.

Mükemmel değil — bazı sitelerde tutmaz, o zaman el yazması tarife düşülür.
Ama çoğu Türk bayi sayfası aynı kalıbı kullanıyor: bir kap, içinde ünvan,
ilçe, adres, telefon.

Yanlış veri üretmemek için muhafazakâr davranır: telefonu ya da adresi
olmayan kaydı atar.
"""

import re
from collections import defaultdict

from bs4 import BeautifulSoup

from .normalize import IL_BY_FOLD, fold

# Türk telefon numarası.
#
# Önceki kalıp herhangi bir 10 haneli rakam dizisini telefon sayıyordu:
# koordinatlar, ürün kodları, tarihler, hatta uzun sayıların içinden
# kesitler. Zelsun'un sayfasında 21.494 "telefon" bulmuştu. Ayrıştırıcı
# doğru kabı seçerken bu sayıya baktığı için yanlış ölçüyle karar veriyordu.
#
# Kurallar: başında/sonunda başka rakam olamaz; alan kodu 2-5 ile başlar
# (Türkiye'de sabit hat 2xx-4xx, cep 5xx); toplam 10 hane.
TEL = re.compile(
    r"(?<![\d])"                          # solunda rakam yok
    r"(?:\+90[\s.\-]?)?"                  # ülke kodu
    r"0?"                                 # baştaki sıfır
    r"[\s(]*"
    r"[2-58]\d{2}"                        # alan kodu: 2-5 sabit/cep, 8 → 0850
    r"[)\s.\-]*\d{3}"
    r"[\s.\-]*\d{2}"
    r"[\s.\-]*\d{2}"
    r"(?![\d])")                          # sağında rakam yok
ADRES = re.compile(r"\b(mah|mh|mahalle|mahallesi|cad|cd|cadde|caddesi|sok|sk|"
                   r"sokak|blv|bulv|bulvar|no\s*:|osb|sanayi|apt|plaza|iş\s*mrk)\b"
                   r"[\.\s:]", re.I)
GURULTU = {"script", "style", "noscript", "svg", "head", "meta", "link",
           "iframe", "footer", "nav"}

# Kayıt türü etiketleri. Bazı siteler (Rutec gibi) her noktanın türünü
# açıkça yazıyor: "Satış Noktası", "Yetkili Servis", "Bölge Bayisi".
# Bunlar firma adı ya da ilçe DEĞİL — rol bilgisi. Ayrıştırıcı bunları
# tanımazsa "Yetkili Servis" adında bir bayi uyduruyor.
# Etiketler ASCII'ye katlanarak karşılaştırılıyor: "Satış Noktası" -> "satis noktasi".
# Doğrudan Türkçe karakterle regex yazmak kelime sınırı (\b) davranışı yüzünden
# şaşırtıyordu; katlama hem daha basit hem daha güvenilir.
TUR_ESLEME = [
    # Sıra önemli: birleşik ifadeler önce denenmeli ki "satis servis" ifadesi
    # yalnızca "servis" diye okunmasın.
    ("satis_servis", ("satis ve servis", "bayi ve servis", "satis servis",
                      "satis / servis", "bayi servis", "satis+servis",
                      "bayi ve yetkili servis", "satis noktasi ve servis")),
    ("servis", ("yetkili servis", "servis noktasi", "teknik servis",
                "servis agi", "sadece servis", "servis merkezi",
                "authorized service", "service point", "servis")),
    ("satis", ("satis noktasi", "bolge bayisi", "yetkili bayi", "yetkili satici",
               "teslimat noktasi", "showroom", "bayi", "satici", "magaza",
               "dealer", "sales point", "satis magazasi", "satis")),
]


# Bileşik kategori etiketleri: "Benzinli Araç Servisi / Elektrikli Araç
# Servisi" gibi. Volta'da bu metin firma adı olarak kaydediliyordu.
# Bileşik kategori etiketleri. Volta'da firma adı olarak
# "Benzinli Araç Servisi / Elektrikli Araç Servisi / Elektrikli Bisiklet
# Servisi" kaydediliyordu — bu bir hizmet listesi, firma adı değil.
_KATEGORI_SOZ = re.compile(
    r"\b(servisi|servis|bayisi|bayi|noktas[ıi]|sat[ıi][şs][ıi]|"
    r"mağazas[ıi]|magazasi|merkezi)\b", re.I)


def kategori_etiketi_mi(metin: str) -> bool:
    """Metin bir hizmet/kategori listesi mi?

    Ölçüt: bölü işaretiyle ayrılmış en az iki parça VAR ve parçaların
    çoğu 'servis', 'bayi', 'nokta' gibi kategori sözcüğüyle bitiyor.
    Gerçek firma adları ("Çakmak Motor / Şaban Çakmak") bu kalıba uymaz.
    """
    if not metin or "/" not in metin or len(metin) > 140:
        return False
    parcalar = [p.strip() for p in metin.split("/") if p.strip()]
    if len(parcalar) < 2:
        return False
    kategorili = sum(1 for p in parcalar if _KATEGORI_SOZ.search(p))
    return kategorili >= 2 and kategorili >= len(parcalar) * 0.7


def tur_coz(metin: str) -> str:
    """Metin bir kayıt türü etiketi mi? Öyleyse rolü döner, değilse boş.

    Rutec gibi siteler her noktanın türünü açıkça yazıyor ("Satış Noktası",
    "Yetkili Servis", "Bölge Bayisi"). Bunlar firma adı ya da ilçe DEĞİL.
    Tanınmazsa "Yetkili Servis" adında bir bayi uydurulmuş oluyor.
    """
    if not metin or len(metin) > 32:
        return ""
    f = fold(metin)
    if not f:
        return ""
    for rol, etiketler in TUR_ESLEME:
        for e in etiketler:
            # Tam eşleşme ya da etiketin metnin tamamını kaplaması
            if f == e or (e in f and len(f) <= len(e) + 10):
                return rol
    return ""


# Ticari ünvan işaretleri — bayi adını ilçe adından ayırmak için
TICARI = re.compile(
    r"\b(motor|motorlu|motosiklet|moto|bisiklet|oto|otomotiv|ticaret|tic|"
    r"ltd|şti|sti|san|sanayi|a\.?ş|as|koll|kollektif|grup|group|market|"
    r"merkez[iı]|servis|plaza|center|garage|garaj|makina|makine|traktör|"
    r"yedek|aksesuar|show\s*room|showroom|kardeşler|ve\s+o[gğ]ullar[iı]|"
    r"limited|anonim)\b", re.I)

# Arayüz metinleri: butonlar, çağrı ifadeleri, form etiketleri.
# Honda'da 59 kaydın hepsinde bayi adı yerine
# "Satış danışmanı ile görüşmek istiyorum" yazıyordu.
# Yer tutucular: veri yokken gösterilen metinler
YER_TUTUCU = re.compile(
    r"^\W*(konum yok|adres yok|bilgi yok|belirtilmemi[sş]|"
    r"bulunamad[iı]|se[cç]iniz|se[cç]im yap|t[uü]m[uü]|hepsi|di[gğ]er)\W*$", re.I)

ARAYUZ = re.compile(
    r"(istiyorum|ediyorum|alın|alin|arayın|arayin|geçin|gecin|"
    r"konuma git|yol tarifi|haritaya git|haritada g|rota|navigasyon|"
    r"ulaşın|ulasin|tıklayın|tiklayin|görüntüle|goruntule|"
    r"randevu|yol tarifi|şimdi ara|simdi ara|iletişime|iletisime|"
    r"whatsapp|konuşun|konusun|bize ulaş|bilgi al|teklif|"
    r"daha fazla|devamını|detaylı bilgi|haritada)", re.I)

# Bayi adı olamayacak metinler
COP = {"ara", "detay", "harita", "yol tarifi al", "yol tarifi", "devamı",
       "daha fazla", "iletişim", "bilgi al", "göster", "adres", "telefon",
       "tıklayınız", "detaylı bilgi", "konum", "haritada göster"}


def _sinif_anahtari(el):
    return (el.name, tuple(sorted(c for c in (el.get("class") or [])
                                  if not re.match(r"^(w|col|row)-?\d", c))))


def _puan(metin):
    p = 0
    if TEL.search(metin):
        p += 5
    if ADRES.search(metin):
        p += 4
    if 40 < len(metin) < 900:
        p += 2
    return p


def kaplari_bul(soup, en_az=2):
    """Bayi kaydına benzeyen, tekrar eden eleman gruplarını puanlayarak döner."""
    # Kartları önce ebeveyne göre grupla...
    gruplar = defaultdict(list)
    for el in soup.find_all(True):
        if el.name in GURULTU or el.parent is None:
            continue
        gruplar[(id(el.parent),) + _sinif_anahtari(el)].append(el)

    # ...sonra AYNI sınıfa sahip olanları sayfa genelinde birleştir.
    #
    # Neden: siteler bayileri il/harf başlıkları altında ayrı bloklara bölüyor.
    # Bajaj'da kartlar 21 ve 9 diye iki grupta duruyordu; sadece birini alınca
    # 98 nokta yerine 18 kayıt çıkıyordu. Voge'de 24+16, SYM'de 9+4 aynı durum.
    birlesik = defaultdict(list)
    for anahtar, elemanlar in gruplar.items():
        sinif = anahtar[1:]          # (etiket, sınıflar) — ebeveyni at
        if sinif[1]:                 # sınıfı olanları birleştir
            birlesik[sinif].extend(elemanlar)
    for sinif, elemanlar in birlesik.items():
        # Aynı eleman birden çok gruptan gelebilir; kimliğe göre tekilleştir
        tekil, gorulen = [], set()
        for e in elemanlar:
            if id(e) not in gorulen:
                gorulen.add(id(e))
                tekil.append(e)
        # İç içe geçmiş aynı sınıflı kutularda dıştakini at, yoksa her kayıt
        # iki kez çıkıyor (SYM'de böyleydi).
        kumeler = {id(e) for e in tekil}
        yaprak = [e for e in tekil
                  if not any(id(alt) in kumeler for alt in e.find_all(True))]
        if len(yaprak) > 3:
            gruplar[("birlesik",) + sinif] = yaprak

    adaylar = []
    for elemanlar in gruplar.values():
        if len(elemanlar) < en_az:   # az sayıda sonuç veren ilçe sayfaları için 2
            continue
        metinler = [e.get_text(" ", strip=True) for e in elemanlar]
        telli = sum(1 for m in metinler if TEL.search(m))
        if telli < max(2, len(elemanlar) * 0.4):
            continue
        # Sıralama ölçütü: kaç elemanda telefon var.
        #
        # Ortalama puan kullanmak yanıltıyordu: ızgara düzenli sayfalarda boş
        # hücreler ortalamayı düşürüp doğru grubu (FCM'de 285 kartlık) alt
        # sıralara itiyordu. "Telefon taşıyan eleman sayısı" bayi listesini
        # doğrudan işaret ediyor.
        ort = sum(_puan(m) for m in metinler) / len(elemanlar)
        adaylar.append((telli, ort, len(elemanlar), elemanlar))
    adaylar.sort(key=lambda a: (-a[0], -a[1]))
    return [(a[1], a[2], a[3]) for a in adaylar]


def _yapraklar(kap):
    """İçinde metinli başka eleman olmayan elemanlar."""
    out = []
    for c in kap.find_all(True):
        if c.name in GURULTU:
            continue
        if any(x.get_text(strip=True) for x in c.find_all(True)):
            continue
        m = c.get_text(" ", strip=True)
        if not m or len(m) >= 400:
            continue
        # "İlçe:", "Tel:", "Adres:" gibi salt etiketler alan değeri değil
        if m.rstrip().endswith((":", "：")) and len(m) < 24:
            continue
        if any(k.match(m) and not m[k.match(m).end():].strip(" :：-–")
               for k in ETIKET.values()):
            continue
        out.append((c, m))
    return out


EPOSTA_ADRES = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$|^(https?://|www\.)", re.I)


def COP_JETON(m: str) -> bool:
    """Metin gerçek bir isim mi? CSS artığı / rakam yığını değil mi?

    Honda'nın sayfasında ayrıştırıcı '243', '24d', '24h' gibi jetonları
    firma adı sanmıştı; bunlar sınıf adlarıydı.
    """
    t = m.strip()
    if len(t) < 4:
        return False
    # E-posta ya da web adresi firma adı değildir.
    # Bajaj'da 24 kayıtta "taskinmotor@gmail.com" bayi adı olarak yazılmıştı.
    if EPOSTA_ADRES.match(t):
        return False
    harf = sum(1 for c in t if c.isalpha())
    if harf < 3:
        return False
    # Harf/rakam karışık kısa jetonlar ("24d", "a1b2")
    if len(t) <= 8 and re.fullmatch(r"[a-z0-9]+", t, re.I) and any(c.isdigit() for c in t):
        return False
    return True


def _ilk_telefon(m: str) -> str:
    """Birleşik yazılmış telefonlardan ilkini alır.

    Voge'de '0232 716 89 70 – 0532 396 63 73' tek alan olarak geliyordu.
    """
    e = TEL.search(m)
    return e.group(0) if e else ""


ETIKET = {
    "ilce": re.compile(r"^\s*(il[çc]e|semt|b[öo]lge)\s*[:：]", re.I),
    "il": re.compile(r"^\s*(il|[şs]ehir|province)\s*[:：]", re.I),
    "telefon": re.compile(r"^\s*(tel|telefon|gsm|cep|phone)\s*[:：]", re.I),
    "adres": re.compile(r"^\s*(adres|address)\s*[:：]", re.I),
    "email": re.compile(r"^\s*(e-?posta|e-?mail|mail)\s*[:：]", re.I),
}


def _etiketli_alanlar(kap, rec):
    """'İlçe: ÇEŞME' gibi etiketli satırları okur.

    Voge ve benzeri siteler alanları açıkça etiketliyor. Bunu okumak, metin
    uzunluğuna bakıp tahmin etmekten çok daha güvenilir.
    """
    bulundu = set()
    # Kısa metinden uzuna: en içteki eleman kazansın. Dıştaki kutu
    # "İlçe: ÇEŞME Tel: ... Adres: ..." diye hepsini kapsıyor ve önce
    # eşleşirse ilçeye telefon da yapışıyordu.
    adaylar = [(d, d.get_text(" ", strip=True))
               for d in kap.find_all(["div", "p", "li", "span", "td"])]
    for d, m in sorted(adaylar, key=lambda x: len(x[1])):
        if not m or len(m) > 300:
            continue
        for alan, kalip in ETIKET.items():
            if alan in bulundu:
                continue
            e = kalip.match(m)
            if e:
                deger = m[e.end():].strip(" :：-–")
                if deger:
                    rec[alan] = (_ilk_telefon(deger) if alan == "telefon"
                                 else deger)
                    bulundu.add(alan)
                break
    return bulundu


def _kaydi_cikar(kap):
    """Tek bir kaptan bayi kaydı çıkarır. Çıkaramazsa None."""
    rec = {"bayi_adi": "", "il": "", "ilce": "", "adres": "",
           "telefon": "", "email": "", "website": ""}
    kullanildi = set()
    yap = _yapraklar(kap)

    # Önce etiketli alanları oku — en güvenilir kaynak
    etiketli = _etiketli_alanlar(kap, rec)
    if etiketli:
        # Etiketli değerleri aday havuzundan çıkar ki ad seçimini bozmasın
        degerler = {fold(rec[a]) for a in etiketli if rec.get(a)}
        yap = [(c, m) for c, m in yap if fold(m) not in degerler
               and not any(fold(m).startswith(fold(v)) for v in degerler if v)]

    # Telefon — tel: bağlantısı varsa en güvenilir
    tel = kap.select_one("a[href^='tel:']")
    if tel:
        # href de çoklu olabiliyor: tel:"0232 716 89 70 – 0532 396 63 73"
        rec["telefon"] = _ilk_telefon(tel.get("href", "")[4:]) or tel.get("href", "")[4:]
    else:
        for c, m in yap:
            if TEL.search(m):
                rec["telefon"] = _ilk_telefon(m)
                kullanildi.add(id(c))
                break

    # E-posta: bağlantıdan ya da düz metinden
    mail = kap.select_one("a[href^='mailto:']")
    if mail:
        rec["email"] = mail.get("href", "")[7:]
    else:
        for c, m in yap:
            if EPOSTA_ADRES.match(m.strip()) and "@" in m:
                rec["email"] = m.strip()
                kullanildi.add(id(c))
                break

    # Adres
    for c, m in yap:
        if id(c) in kullanildi:
            continue
        if ADRES.search(m) and len(m) > 15:
            rec["adres"] = re.sub(r"^\s*adres\s*[:\-]\s*", "", m, flags=re.I)
            kullanildi.add(id(c))
            break

    # Kalan adaylar: telefon/adres olmayan anlamlı metinler
    kalan, il_adaylari = [], []
    for c, m in yap:
        if id(c) in kullanildi or TEL.search(m) or ADRES.search(m):
            continue
        if len(m) < 3 or m.strip().lower().rstrip(":") in COP:
            continue
        if ARAYUZ.search(m) or YER_TUTUCU.match(m) or kategori_etiketi_mi(m):
            continue
        temiz = re.sub(r"\s+", " ", m).strip()
        # Tür etiketi mi? Öyleyse rol olarak al, ad/ilçe adayı sayma.
        # Tür etiketi hiçbir zaman ad/ilçe adayı olamaz. Rol zaten
        # atanmışsa da atlanmalı — Rutec ve Bajaj'da etiket iki kez geçtiği
        # için ikincisi firma adı olarak kaydediliyordu.
        rol = tur_coz(temiz)
        if rol:
            rec.setdefault("rol", rol)
            continue
        # İl adı mı? Firma adı olamaz — il alanına yazılır.
        # (Kove'de "BALIKESİR" firma adı sanılıyordu, gerçek ad ilçeye düşüyordu.)
        if fold(temiz) in IL_BY_FOLD:
            il_adaylari.append(temiz)
            continue
        # Anlamsız jeton mu? ("243", "24d" gibi CSS artıkları)
        if not COP_JETON(temiz):
            continue
        kalan.append((c, temiz))

    # Bayi adı ile ilçeyi ayır.
    #
    # Uzunluk tek başına yetmiyor: "EYÜP SULTAN" (ilçe) ile "Ctn Motor" (bayi)
    # örneğinde uzun olan ilçeydi. Daha güvenilir ayraç: bayi adları neredeyse
    # her zaman bir ticari kelime içerir, ilçe adları hiç içermez.
    if not kalan:
        return None

    # Konum adı mı, firma adı mı?
    #
    # İl adlarını yukarıda eledik ama ilçe adları da bayi adı sanılabiliyor
    # (Antalya'da "ALANYA", "MANAVGAT" firma adı olarak kaydediliyordu).
    # Türkiye'de ~970 ilçe var ve listesini taşımak yerine şu ipucunu
    # kullanıyoruz: ilçe adı neredeyse her zaman kaydın ADRESİNDE de geçiyor,
    # firma adı ise geçmiyor. Adreste geçen tek kelimelik adaylar konum sayılır.
    from .ilceler import ilce_mi
    from .normalize import il_ara
    adres_f = fold(rec.get("adres", ""))
    konum_gibi, gercek = [], []
    for c, m in kalan:
        f = fold(m)
        if TICARI.search(m):
            gercek.append((c, m))
            continue
        # a) Başlık etiketindeki konum adı ("<strong>SEYHAN</strong>")
        if c.name in ("strong", "b", "h1", "h2", "h3", "h4", "h5", "h6"):
            if ilce_mi(m) or il_ara(m) or len(f.split()) <= 3:
                konum_gibi.append((c, m))
                continue
        # b) Gerçek bir ilçe adıysa firma adı olamaz.
        #    FCM'de "SEYHAN", "KOZAN", "YÜREĞİR" satırları bayi adı
        #    oluyordu; kişi adlı bayilerde ticari kelime bulunmadığı için
        #    ilk sıradaki ilçe seçiliyordu.
        if len(f.split()) <= 3 and ilce_mi(m):
            konum_gibi.append((c, m))
            continue
        # c) Adresin içinde geçen kısa ifade → ilçe adı
        if adres_f and f and len(f.split()) <= 2 and f in adres_f:
            konum_gibi.append((c, m))
            continue
        # d) İçinde gerçek bir il adı geçiyor → konum başlığı
        #    ("İZMİR-TORBALI", "MUĞLA / BODRUM" firma adı sanılıyordu)
        if len(f.split()) <= 3 and il_ara(m):
            konum_gibi.append((c, m))
            continue
        gercek.append((c, m))
    # Konum ayıklaması sonrası hiç aday kalmadıysa geri al — yoksa kayıt
    # tamamen kaybolur. Yanlış ad, kayıp kayıttan iyidir.
    if gercek:
        kalan = gercek
        if konum_gibi:
            for _, km in konum_gibi:
                bulunan = il_ara(km)
                if bulunan and not rec.get("il"):
                    rec["il"] = bulunan
                    kalan_parca = re.split(r"[_/\-–]", km)[-1].strip()
                    if kalan_parca and fold(kalan_parca) != fold(bulunan) \
                            and not rec.get("ilce"):
                        rec["ilce"] = kalan_parca
                elif not rec.get("ilce"):
                    rec["ilce"] = km

    # Bayi adı seçimi.
    #
    # "En uzun metni ad say" kuralı Honda'da çuvalladı: buton yazısı
    # ("Satış danışmanı ile görüşmek istiyorum", 37 karakter) gerçek addan
    # ("Honda Motosiklet Alp", 20 karakter) uzundu. Firma adı neredeyse her
    # zaman kartın BAŞINDA olduğu için belge sırası daha güvenilir.
    ticari = [(c, m) for c, m in kalan if TICARI.search(m)]
    if ticari:
        rec["bayi_adi"] = ticari[0][1]                 # ilk ticari ifade
        secilen = ticari[0][0]
        digerleri = [m for c, m in kalan if c is not secilen]
    else:
        rec["bayi_adi"] = kalan[0][1]                  # ilk aday
        digerleri = [m for _, m in kalan[1:]]

    # İlçe: kalanlar içinde kısa ve ticari kelime içermeyen
    for m in digerleri:
        if len(m) <= 30 and not TICARI.search(m):
            rec["ilce"] = m
            break

    if il_adaylari and not rec.get("il"):
        rec["il"] = il_adaylari[0]

    # İlçe alanı "İL / BÖLGE _ İLÇE" gibi birleşik gelmiş olabilir
    if rec.get("ilce") and not rec.get("il"):
        from .normalize import il_ara
        bulunan = il_ara(rec["ilce"])
        if bulunan:
            rec["il"] = bulunan
            son = re.split(r"[_/\-–]", rec["ilce"])[-1].strip()
            rec["ilce"] = son if son and fold(son) != fold(bulunan) else ""

    if not rec["telefon"] and not rec["adres"]:
        return None
    return rec


def il_basliklari(soup):
    """Belgedeki il başlıklarını sırasıyla döner: [(sıra_no, il_adı), ...]

    Siteler bayileri il başlıkları altında grupluyor (SYM'de 44 sekme başlığı
    var). Kartın içinde sadece ilçe yazıyor, il yukarıdaki başlıkta. Bu
    eşlemeyi kurmadan 35 SYM kaydında il boş kalıyordu.
    """
    out = []
    for sira, el in enumerate(soup.find_all(True)):
        if el.find(True):                      # yalnızca yaprak
            continue
        m = el.get_text(" ", strip=True)
        if not m or len(m) > 40:
            continue
        il = IL_BY_FOLD.get(fold(m))
        if il:
            out.append((sira, il))
    return out


def _il_devral(soup, elemanlar, kayitlar):
    """Kaydın üstündeki en yakın il başlığını AYRI bir alana yazar.

    Doğrudan 'il' alanına yazmıyoruz. Başlık devralma yanılabiliyor: sayfa
    yapısı beklenenden farklıysa Kadıköy'deki bir bayiye Zonguldak atanıyordu.
    Yanlış il, eksik ilden çok daha kötü. Bu yüzden başlık yalnızca ADAY
    olarak saklanıyor; kaydın kendi adresi hiçbir ipucu vermiyorsa kullanılıyor.
    """
    basliklar = il_basliklari(soup)
    if len(basliklar) < 3:
        return
    sira = {id(el): i for i, el in enumerate(soup.find_all(True))}
    for el, rec in zip(elemanlar, kayitlar):
        if rec is None:
            continue
        yer = sira.get(id(el), -1)
        onceki = [il for s, il in basliklar if s < yer]
        if onceki:
            rec["il_baslik"] = onceki[-1]


def cikar(html: str) -> list[dict]:
    """Sayfadan bayi kayıtlarını otomatik çıkarır."""
    soup = BeautifulSoup(html, "html.parser")
    for g in soup(list(GURULTU)):
        g.decompose()

    # Tüm adayları dene, EN ÇOK sağlam kayıt vereni seç.
    #
    # Önceden ilk yeterli adayda duruluyordu ve "elemanların yarısından kayıt
    # çıkmalı" kuralı vardı. Izgara düzenli sitelerde (FCM) hücrelerin bir
    # kısmı boş olduğu için 285 kartlık doğru grup eleniyor, 16 kartlık küçük
    # grup seçiliyordu. Oran yerine mutlak sayı ve kalite bakıyoruz.
    en_iyi, en_iyi_skor = [], 0.0
    for _, _, elemanlar in kaplari_bul(soup)[:12]:
        ham = [_kaydi_cikar(e) for e in elemanlar]
        _il_devral(soup, elemanlar, ham)          # il başlıklarını miras al
        kayitlar = [r for r in ham if r]
        if len(kayitlar) < 2:
            continue
        puan = _kalite(kayitlar)
        if puan < 0.45:
            continue
        # Kalite eşiği geçildiyse kayıt sayısı belirleyici olsun
        skor = len(kayitlar) * (1 + puan)
        if skor > en_iyi_skor:
            en_iyi, en_iyi_skor = kayitlar, skor
    return en_iyi


def _kalite(kayitlar) -> float:
    """Çıkan kayıtlar ne kadar inandırıcı? 0-1 arası.

    Kaplardan hangisinin doğru olduğunu ayırt etmek için. Sadece "kaç kayıt
    çıktı" bakmak yetmiyor; çöp de kayıt gibi görünebiliyor.
    """
    if not kayitlar:
        return 0.0
    n = len(kayitlar)
    p = 0.0
    # Adı inandırıcı olanların oranı
    p += 0.45 * sum(1 for k in kayitlar if len(k["bayi_adi"]) >= 6
                    and " " in k["bayi_adi"].strip()) / n
    # Telefonu olanlar
    p += 0.25 * sum(1 for k in kayitlar if k["telefon"]) / n
    # Adresi olanlar
    p += 0.20 * sum(1 for k in kayitlar if len(k["adres"]) > 12) / n
    # Adlar birbirinden farklı mı (aynı etiket çoğaltılmamış)
    p += 0.10 * (len({k["bayi_adi"] for k in kayitlar}) / n)
    return p


# ============================================================================
#  İL DİZİNİ TESPİTİ
# ============================================================================
def il_baglantilari(html: str, temel_url: str) -> dict:
    """Sayfa bir il dizini mi? Öyleyse {il: url} döner.

    Arora (/bayiler/Ankara), Kral (/kategori/bayiler/adana) gibi siteler ana
    bayi sayfasında bayi göstermiyor; 81 ile giden bağlantı listesi sunuyor.
    Bu sayfada bayi aramak boş sonuç verir — bağlantıları izlemek gerekir.
    """
    from urllib.parse import urljoin, urlparse

    from .normalize import ILLER, fold

    soup = BeautifulSoup(html, "html.parser")
    il_fold = {fold(i): i for i in ILLER}
    il_fold["afyon"] = "Afyonkarahisar"
    il_fold["icel"] = "Mersin"
    il_fold["urfa"] = "Şanlıurfa"

    bulunan = {}
    ana_alan = urlparse(temel_url).netloc
    for a in soup.find_all("a", href=True):
        metin = fold(a.get_text(" ", strip=True))
        href = a["href"]
        # Bağlantı metni ya da adresin son parçası bir il adı mı?
        aday = il_fold.get(metin)
        if not aday:
            son = fold(href.rstrip("/").split("/")[-1].split("?")[0])
            aday = il_fold.get(son)
        if not aday:
            continue
        tam = urljoin(temel_url, href)
        if urlparse(tam).netloc != ana_alan:
            continue
        bulunan.setdefault(aday, tam)

    # En az 20 il varsa bu gerçekten bir dizin sayfasıdır
    return bulunan if len(bulunan) >= 20 else {}


# ============================================================================
#  GÖMÜLÜ JSON
# ============================================================================
def json_gomulu(html: str) -> list[dict]:
    """HTML içine gömülü JSON'dan bayi listesi çıkarır.

    Modern siteler (Next.js, Nuxt, Vue) veriyi __NEXT_DATA__ gibi bir script
    etiketinde gönderiyor. Sayfa görsel olarak JS ile çiziliyor ama veri
    aslında HTML'in içinde — tarayıcı açmaya gerek yok.
    """
    import json as _json

    from .koordinat import en_yakin_il, turkiyede_mi

    ADAY_ANAHTAR = ("phone", "telefon", "tel", "gsm", "phonenumber", "telephone")
    ADRES_ANAHTAR = ("address", "adres", "adres1", "street", "addressline1")
    LAT_ANAHTAR = ("lat", "latitude", "enlem", "y")
    LNG_ANAHTAR = ("lng", "lon", "long", "longitude", "boylam", "x")

    def _bul(d, adaylar):
        for a in adaylar:
            for k, v in d.items():
                if k.lower() == a and v not in (None, ""):
                    return v
        return None

    def kayit_mi(d):
        """Bayi kaydına benziyor mu?

        İki kalıp var:
          klasik → telefon + adres
          harita → ad + koordinat  (Yamaha, BMW gibi harita tabanlı bulucular
                   telefon vermeyebiliyor ama koordinat hep var)
        """
        if not isinstance(d, dict):
            return False
        k = {x.lower() for x in d}
        if any(a in k for a in ADAY_ANAHTAR) and any(a in k for a in ADRES_ANAHTAR):
            return True
        adli = any(a in k for a in ("name", "title", "unvan", "dealername", "firma"))
        return adli and any(a in k for a in LAT_ANAHTAR) and any(a in k for a in LNG_ANAHTAR)

    def gez(o, bulunan):
        if isinstance(o, list):
            uygun = [x for x in o if kayit_mi(x)]
            if len(uygun) >= 3:
                bulunan.append(uygun)
            for x in o:
                gez(x, bulunan)
        elif isinstance(o, dict):
            for v in o.values():
                gez(v, bulunan)

    soup = BeautifulSoup(html, "html.parser")
    kumeler = []
    for sc in soup.find_all("script"):
        ham = sc.string or sc.get_text() or ""
        if not ham or len(ham) < 60:
            continue
        for parca in re.findall(r"(\{.*\}|\[.*\])", ham, re.S)[:3]:
            try:
                gez(_json.loads(parca), kumeler)
            except Exception:
                continue

    if not kumeler:
        return []
    en_buyuk = max(kumeler, key=len)

    def al(d, adaylar):
        for a in adaylar:
            for k, v in d.items():
                if k.lower() == a and v:
                    return str(v)
        return ""

    out = []
    yurtdisi = 0
    cop = 0
    for d in en_buyuk:
        ad = al(d, ("name", "title", "unvan", "bayi", "dealername", "firma"))
        if not ad:
            continue

        lat, lng = _bul(d, LAT_ANAHTAR), _bul(d, LNG_ANAHTAR)
        il = al(d, ("city", "il", "sehir", "province", "town"))

        # Global bulucular komşu ülke bayilerini de döndürüyor. Koordinat
        # varsa Türkiye dışındakileri burada eliyoruz.
        if lat is not None and lng is not None:
            if not turkiyede_mi(lat, lng):
                yurtdisi += 1
                continue
            if not il:
                il = en_yakin_il(lat, lng)

        # Kayıt türü alanı: rolü doğrudan kaynağından al
        rol = ""
        tur = al(d, ("type", "tur", "tür", "tip", "kategori", "category",
                     "nokta_turu", "dealertype", "pointtype"))
        if tur:
            rol = tur_coz(tur)

        # Ülke alanı varsa ona da bak
        ulke = al(d, ("country", "countrycode", "ulke", "iso"))
        if ulke and ulke.strip().lower() not in (
                "tr", "tur", "turkey", "türkiye", "turkiye", "türkei"):
            yurtdisi += 1
            continue

        kayit = {
            "bayi_adi": ad,
            "il": il or "",
            "ilce": al(d, ("district", "ilce", "county", "region")),
            "adres": al(d, ADRES_ANAHTAR),
            "telefon": al(d, ADAY_ANAHTAR),
            "email": al(d, ("email", "eposta", "mail")),
            "website": al(d, ("website", "web", "url", "site")),
        }
        # Bazı siteler (Honda) JSON'da gerçek değer yerine iç referans kodu
        # taşıyor: {"name":"1uj","city":"1ut"}. Bunlar veri değil, işaretçi.
        # Ad 4 karakterden kısaysa ya da harf/rakam karışık kısa jetonsa at.
        if not COP_JETON(ad) or (kayit["adres"] and not COP_JETON(kayit["adres"])):
            cop += 1
            continue
        if rol:
            kayit["rol"] = rol
        out.append(kayit)

    # Kayıtların çoğu çöpse bu JSON bayi listesi değildir
    if cop > len(en_buyuk) * 0.5:
        return []
    return out


# ============================================================================
#  İL SEÇİCİ KEŞFİ
# ============================================================================
def il_secicileri_bul(html: str, temel_url: str) -> list[tuple[str, str]]:
    """Sayfada il seçen bir açılır liste var mı? Varsa (url, il) çiftleri üretir.

    Neden gerekli: çoğu bayi sayfası parametresiz açıldığında listenin sadece
    bir dilimini gösteriyor. Mondial'de 390 kayıt gelirken 600 servisin hiçbiri
    gelmemişti; sebep servis sayfasına il parametresi verilmemesiydi.

    Elle her markaya parametre yazmak yerine sayfadaki <select> içinde il
    adlarını arıyoruz. Bulursak seçeneğin değerini ve alanın adını kullanarak
    81 il için adres üretiyoruz.
    """
    from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

    from .normalize import ILLER, fold

    soup = BeautifulSoup(html, "html.parser")
    il_fold = {fold(i): i for i in ILLER}
    il_fold.update({"afyon": "Afyonkarahisar", "icel": "Mersin",
                    "mersin icel": "Mersin", "urfa": "Şanlıurfa",
                    "k maras": "Kahramanmaraş"})

    en_iyi = None
    for sec in soup.find_all("select"):
        secenekler = []
        for o in sec.find_all("option"):
            metin = fold(o.get_text(" ", strip=True))
            deger = (o.get("value") or "").strip()
            if not deger or deger.lower() in ("", "0", "-1", "sec", "seciniz"):
                continue
            il = il_fold.get(metin)
            if il:
                secenekler.append((deger, il))
        # En az 20 il tanınıyorsa bu gerçekten il seçicisidir
        if len(secenekler) >= 20:
            ad = (sec.get("name") or sec.get("id") or "").strip()
            if ad and (en_iyi is None or len(secenekler) > len(en_iyi[1])):
                en_iyi = (ad, secenekler)

    if not en_iyi:
        return []

    alan, secenekler = en_iyi
    parca = urlparse(temel_url)
    out = []
    for deger, il in secenekler:
        q = dict(parse_qsl(parca.query))
        q[alan] = deger
        out.append((urlunparse(parca._replace(query=urlencode(q))), il))
    return out
