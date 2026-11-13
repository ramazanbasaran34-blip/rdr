"""Türkiye il ve ilçe listesi.

Kaynak: turkiye paketi (idari sınır haritası, 973 ilçe).

Neden gerekli: ayrıştırıcı sayfadaki her kısa metni ilçe sanabiliyordu.
Antalya listesinde "Haritada Gör", "Sizi Arayalım", e-posta adresleri ve
firma adları ilçe olarak görünüyordu. Artık ilçe alanına ancak bu listede
geçen bir ad yazılabiliyor; geçmiyorsa alan boş bırakılıyor.
"""

from .normalize import fold

IL_ILCE = {
    "Adana": ["Aladağ", "Ceyhan", "Çukurova", "Feke", "İmamoğlu", "Karaisalı", "Karataş", "Kozan", "Pozantı", "Saimbeyli", "Sarıçam", "Seyhan", "Tufanbeyli", "Yumurtalık", "Yüreğir"],
    "Adıyaman": ["Adıyaman", "Besni", "Çelikhan", "Gerger", "Gölbaşı", "Kâhta", "Samsat", "Sincik", "Tut"],
    "Afyonkarahisar": ["Afyonkarahısar", "Başmakçı", "Bayat", "Bolvadin", "Çay", "Çobanlar", "Dazkırı", "Dinar", "Emirdağ", "Evciler", "Hocalar", "İhsaniye", "İscehisar", "Kızılören", "Sandıklı", "Sinanpaşa", "Şuhut", "Sultandağı"],
    "Ağrı": ["Ağrı", "Diyadin", "Doğubayazıt", "Eleşkirt", "Hamur", "Patnos", "Taşlıçay", "Tutak"],
    "Aksaray": ["Ağaçören", "Aksaray", "Eskil", "Gülağaç", "Güzelyurt", "Ortaköy", "Sarıyahşi", "Sultanhanı"],
    "Amasya": ["Amasya", "Göynücek", "Gümüşhacıköy", "Hamamözü", "Merzifon", "Suluova", "Taşova"],
    "Ankara": ["Akyurt", "Altındağ", "Ayaş", "Bala", "Beypazarı", "Çamlıdere", "Çankaya", "Çubuk", "Elmadağ", "Etimesgut", "Evren", "Gölbaşı", "Güdül", "Haymana", "Kahramankazan", "Kalecik", "Keçiören", "Kızılcahamam", "Mamak", "Nallıhan", "Polatlı", "Pursaklar", "Şereflikoçhisar", "Sincan", "Yenimahalle"],
    "Antalya": ["Akseki", "Aksu", "Alanya", "Demre", "Döşemealtı", "Elmalı", "Finike", "Gazipaşa", "Gündoğmuş", "İbradı", "Kaş", "Kemer", "Kepez", "Konyaaltı", "Korkuteli", "Kumluca", "Manavgat", "Muratpaşa", "Serik"],
    "Ardahan": ["Ardahan", "Çıldır", "Damal", "Göle", "Hanak", "Posof"],
    "Artvin": ["Ardanuç", "Arhavi", "Artvın", "Borçka", "Hopa", "Kemalpaşa", "Murgul", "Şavşat", "Yusufeli"],
    "Aydın": ["Bozdoğan", "Buharkent", "Çine", "Didim", "Efeler", "Germencik", "İncirliova", "Karacasu", "Karpuzlu", "Koçarlı", "Köşk", "Kuşadası", "Kuyucak", "Nazilli", "Söke", "Sultanhisar", "Yenipazar"],
    "Balıkesir": ["Altıeylül", "Ayvalık", "Balya", "Bandırma", "Bigadiç", "Burhaniye", "Dursunbey", "Edremit", "Erdek", "Gömeç", "Gönen", "Havran", "İvrindi", "Karesi", "Kepsut", "Manyas", "Marmara", "Savaştepe", "Sındırgı", "Susurluk"],
    "Bartın": ["Amasra", "Bartın", "Kurucaşile", "Ulus"],
    "Batman": ["Batman", "Beşiri", "Gercüş", "Hasankeyf", "Kozluk", "Sason"],
    "Bayburt": ["Aydıntepe", "Bayburt", "Demirözü"],
    "Bilecik": ["Bılecık", "Bozüyük", "Gölpazarı", "İnhisar", "Osmaneli", "Pazaryeri", "Söğüt", "Yenipazar"],
    "Bingöl": ["Adaklı", "Bıngöl", "Genç", "Karlıova", "Kiğı", "Solhan", "Yayladere", "Yedisu"],
    "Bitlis": ["Adilcevaz", "Ahlat", "Bıtlıs", "Güroymak", "Hizan", "Mutki", "Tatvan"],
    "Bolu": ["Bolu", "Dörtdivan", "Gerede", "Göynük", "Kıbrıscık", "Mengen", "Mudurnu", "Seben", "Yeniçağa"],
    "Burdur": ["Ağlasun", "Altınyayla", "Bucak", "Burdur", "Çavdır", "Çeltikçi", "Gölhisar", "Karamanlı", "Kemer", "Tefenni", "Yeşilova"],
    "Bursa": ["Büyükorhan", "Gemlik", "Gürsu", "Harmancık", "İnegöl", "İznik", "Karacabey", "Keles", "Kestel", "Mudanya", "Mustafakemalpaşa", "Nilüfer", "Orhaneli", "Orhangazi", "Osmangazi", "Yenişehir", "Yıldırım"],
    "Çanakkale": ["Ayvacık", "Bayramiç", "Biga", "Bozcaada", "Çan", "Çanakkale", "Eceabat", "Ezine", "Gelibolu", "Gökçeada", "Lâpseki", "Yenice"],
    "Çankırı": ["Atkaracalar", "Bayramören", "Çankırı", "Çerkeş", "Eldivan", "Ilgaz", "Kızılırmak", "Korgun", "Kurşunlu", "Orta", "Şabanözü", "Yapraklı"],
    "Çorum": ["Alaca", "Bayat", "Boğazkale", "Çorum", "Dodurga", "İskilip", "Kargı", "Lâçin", "Mecitözü", "Oğuzlar", "Ortaköy", "Osmancık", "Sungurlu", "Uğurludağ"],
    "Denizli": ["Acıpayam", "Babadağ", "Baklan", "Bekilli", "Beyağaç", "Bozkurt", "Buldan", "Çal", "Çameli", "Çardak", "Çivril", "Güney", "Honaz", "Kale", "Merkezefendi", "Pamukkale", "Sarayköy", "Serinhisar", "Tavas"],
    "Diyarbakır": ["Bağlar", "Bismil", "Çermik", "Çınar", "Çüngüş", "Dicle", "Eğil", "Ergani", "Hani", "Hazro", "Kayapınar", "Kocaköy", "Kulp", "Lice", "Silvan", "Sur", "Yenişehir"],
    "Düzce": ["Akçakoca", "Çilimli", "Cumayeri", "Düzce", "Gölyaka", "Gümüşova", "Kaynaşlı", "Yığılca"],
    "Edirne": ["Edırne", "Enez", "Havsa", "İpsala", "Keşan", "Lalapaşa", "Meriç", "Süloğlu", "Uzunköprü"],
    "Elazığ": ["Ağın", "Alacakaya", "Arıcak", "Baskil", "Elazığ", "Karakoçan", "Keban", "Kovancılar", "Maden", "Palu", "Sivrice"],
    "Erzincan": ["Çayırlı", "Erzıncan", "İliç", "Kemah", "Kemaliye", "Otlukbeli", "Refahiye", "Tercan", "Üzümlü"],
    "Erzurum": ["Aşkale", "Aziziye", "Çat", "Hınıs", "Horasan", "İspir", "Karaçoban", "Karayazı", "Köprüköy", "Narman", "Oltu", "Olur", "Palandöken", "Pasinler", "Pazaryolu", "Şenkaya", "Tekman", "Tortum", "Uzundere", "Yakutiye"],
    "Eskişehir": ["Alpu", "Beylikova", "Çifteler", "Günyüzü", "Han", "İnönü", "Mahmudiye", "Mihalgazi", "Mihalıççık", "Odunpazarı", "Sarıcakaya", "Seyitgazi", "Sivrihisar", "Tepebaşı"],
    "Gaziantep": ["Araban", "İslahiye", "Karkamış", "Nizip", "Nurdağı", "Oğuzeli", "Şahinbey", "Şehitkamil", "Yavuzeli"],
    "Giresun": ["Alucra", "Bulancak", "Çamoluk", "Çanakçı", "Dereli", "Doğankent", "Espiye", "Eynesil", "Gıresun", "Görele", "Güce", "Keşap", "Piraziz", "Şebinkarahisar", "Tirebolu", "Yağlıdere"],
    "Gümüşhane": ["Gümüşhane", "Kelkit", "Köse", "Kürtün", "Şiran", "Torul"],
    "Hakkâri": ["Çukurca", "Derecik", "Hakkarı", "Şemdinli", "Yüksekova"],
    "Hatay": ["Altınözü", "Antakya", "Arsuz", "Belen", "Defne", "Dörtyol", "Erzin", "Hassa", "İskenderun", "Kırıkhan", "Kumlu", "Payas", "Reyhanlı", "Samandağ", "Yayladağı"],
    "Iğdır": ["Aralık", "Iğdır", "Karakoyunlu", "Tuzluca"],
    "Isparta": ["Aksu", "Atabey", "Eğirdir", "Gelendost", "Gönen", "Isparta", "Keçiborlu", "Şarkikaraağaç", "Senirkent", "Sütçüler", "Uluborlu", "Yalvaç", "Yenişarbademli"],
    "İstanbul": ["Adalar", "Arnavutköy", "Ataşehir", "Avcılar", "Bağcılar", "Bahçelievler", "Bakırköy", "Başakşehir", "Bayrampaşa", "Beşiktaş", "Beykoz", "Beylikdüzü", "Beyoğlu", "Büyükçekmece", "Çatalca", "Çekmeköy", "Esenler", "Esenyurt", "Eyüpsultan", "Fatih", "Gazi Osmanpaşa", "Güngören", "Kadıköy", "Kağıthane", "Kartal", "Küçükçekmece", "Maltepe", "Pendik", "Sancaktepe", "Sarıyer", "Şile", "Silivri", "Şişli", "Sultanbeyli", "Sultangazi", "Tuzla", "Ümraniye", "Üsküdar", "Zeytinburnu"],
    "İzmir": ["Aliağa", "Balçova", "Bayındır", "Bayraklı", "Bergama", "Beydağ", "Bornova", "Buca", "Çeşme", "Çiğli", "Dikili", "Foça", "Gaziemir", "Güzelbahçe", "Karabağlar", "Karaburun", "Karşıyaka", "Kemalpaşa", "Kınık", "Kiraz", "Konak", "Menderes", "Menemen", "Narlıdere", "Ödemiş", "Seferihisar", "Selçuk", "Tire", "Torbalı", "Urla"],
    "Kahramanmaraş": ["Afşin", "Andırın", "Çağlayancerit", "Dulkadiroğlu", "Ekinözü", "Elbistan", "Göksun", "Nurhak", "Oniki Şubat", "Pazarcık", "Türkoğlu"],
    "Karabük": ["Eflani", "Eskipazar", "Karabük", "Ovacık", "Safranbolu", "Yenice"],
    "Karaman": ["Ayrancı", "Başyayla", "Ermenek", "Karaman", "Kazımkarabekir", "Sarıveliler"],
    "Kars": ["Akyaka", "Arpaçay", "Digor", "Kağızman", "Kars", "Sarıkamış", "Selim", "Susuz"],
    "Kastamonu": ["Abana", "Ağlı", "Araç", "Azdavay", "Bozkurt", "Çatalzeytin", "Cide", "Daday", "Devrekâni", "Doğanyurt", "Hanönü", "İhsangazi", "İnebolu", "Kastamonu", "Küre", "Pınarbaşı", "Şenpazar", "Seydiler", "Taşköprü", "Tosya"],
    "Kayseri": ["Akkışla", "Bünyan", "Develi", "Felahiye", "Hacılar", "İncesu", "Kocasinan", "Melikgazi", "Özvatan", "Pınarbaşı", "Sarıoğlan", "Sarız", "Talas", "Tomarza", "Yahyalı", "Yeşilhisar"],
    "Kilis": ["Elbeyli", "Kılıs", "Musabeyli", "Polateli"],
    "Kırıkkale": ["Bahşili", "Balışeyh", "Çelebi", "Delice", "Karakeçili", "Keskin", "Kırıkkale", "Sulakyurt", "Yahşihan"],
    "Kırklareli": ["Babaeski", "Demirköy", "Kırklarelı", "Kofçaz", "Lüleburgaz", "Pehlivanköy", "Pınarhisar", "Vize"],
    "Kırşehir": ["Akçakent", "Akpınar", "Boztepe", "Çiçekdağı", "Kaman", "Kırşehır", "Mucur"],
    "Kocaeli": ["Başiskele", "Çayırova", "Darıca", "Derince", "Dilovası", "Gebze", "Gölcük", "İzmit", "Kandıra", "Karamürsel", "Kartepe", "Körfez"],
    "Konya": ["Ahırlı", "Akören", "Akşehir", "Altınekin", "Beyşehir", "Bozkır", "Çeltik", "Cihanbeyli", "Çumra", "Derbent", "Derebucak", "Doğanhisar", "Emirgazi", "Ereğli", "Güneysınır", "Hadim", "Halkapınar", "Hüyük", "Ilgın", "Kadınhanı", "Karapınar", "Karatay", "Kulu", "Meram", "Sarayönü", "Selçuklu", "Seydişehir", "Taşkent", "Tuzlukçu", "Yalıhüyük", "Yunak"],
    "Kütahya": ["Altıntaş", "Aslanapa", "Çavdarhisar", "Domaniç", "Dumlupınar", "Emet", "Gediz", "Hisarcık", "Kütahya", "Pazarlar", "Şaphane", "Simav", "Tavşanlı"],
    "Malatya": ["Akçadağ", "Arapgir", "Arguvan", "Battalgazi", "Darende", "Doğanşehir", "Doğanyol", "Hekimhan", "Kale", "Kuluncak", "Pütürge", "Yazıhan", "Yeşilyurt"],
    "Manisa": ["Ahmetli", "Akhisar", "Alaşehir", "Demirci", "Gölmarmara", "Gördes", "Kırkağaç", "Köprübaşı", "Kula", "Salihli", "Sarıgöl", "Saruhanlı", "Şehzadeler", "Selendi", "Soma", "Turgutlu", "Yunusemre"],
    "Mardin": ["Artuklu", "Dargeçit", "Derik", "Kızıltepe", "Mazıdağı", "Midyat", "Nusaybin", "Ömerli", "Savur", "Yeşilli"],
    "Mersin": ["Akdeniz", "Anamur", "Aydıncık", "Bozyazı", "Çamlıyayla", "Erdemli", "Gülnar", "Mezitli", "Mut", "Silifke", "Tarsus", "Toroslar", "Yenişehir"],
    "Muğla": ["Bodrum", "Dalaman", "Datça", "Fethiye", "Kavaklıdere", "Köyceğiz", "Marmaris", "Menteşe", "Milas", "Ortaca", "Seydikemer", "Ula", "Yatağan"],
    "Muş": ["Bulanık", "Hasköy", "Korkut", "Malazgirt", "Muş", "Varto"],
    "Nevşehir": ["Acıgöl", "Avanos", "Derinkuyu", "Gülşehir", "Hacıbektaş", "Kozaklı", "Nevşehır", "Ürgüp"],
    "Niğde": ["Altunhisar", "Bor", "Çamardı", "Çiftlik", "Nığde", "Ulukışla"],
    "Ordu": ["Akkuş", "Altınordu", "Aybastı", "Çamaş", "Çatalpınar", "Çaybaşı", "Fatsa", "Gölköy", "Gülyalı", "Gürgentepe", "İkizce", "Kabadüz", "Kabataş", "Korgan", "Kumru", "Mesudiye", "Perşembe", "Ulubey", "Ünye"],
    "Osmaniye": ["Bahçe", "Düziçi", "Hasanbeyli", "Kadirli", "Osmanıye", "Sumbas", "Toprakkale"],
    "Rize": ["Ardeşen", "Çamlıhemşin", "Çayeli", "Derepazarı", "Fındıklı", "Güneysu", "Hemşin", "İkizdere", "İyidere", "Kalkandere", "Pazar", "Rıze"],
    "Sakarya": ["Adapazarı", "Akyazı", "Arifiye", "Erenler", "Ferizli", "Geyve", "Hendek", "Karapürçek", "Karasu", "Kaynarca", "Kocaali", "Pamukova", "Sapanca", "Serdivan", "Söğütlü", "Taraklı"],
    "Samsun": ["19 Mayıs", "Alaçam", "Asarcık", "Atakum", "Ayvacık", "Bafra", "Canik", "Çarşamba", "Havza", "İlkadım", "Kavak", "Ladik", "Salıpazarı", "Tekkeköy", "Terme", "Vezirköprü", "Yakakent"],
    "Şanlıurfa": ["Akçakale", "Birecik", "Bozova", "Ceylanpınar", "Eyyübiye", "Halfeti", "Haliliye", "Harran", "Hilvan", "Karaköprü", "Siverek", "Suruç", "Viranşehir"],
    "Siirt": ["Baykan", "Eruh", "Kurtalan", "Pervari", "Sıırt", "Şirvan", "Tillo"],
    "Sinop": ["Ayancık", "Boyabat", "Dikmen", "Durağan", "Erfelek", "Gerze", "Saraydüzü", "Sınop", "Türkeli"],
    "Şırnak": ["Beytüşşebap", "Cizre", "Güçlükonak", "İdil", "Silopi", "Şırnak", "Uludere"],
    "Sivas": ["Akıncılar", "Altınyayla", "Divriği", "Doğanşar", "Gemerek", "Gölova", "Gürün", "Hafik", "İmranlı", "Kangal", "Koyulhisar", "Sarkışla", "Sıvas", "Suşehri", "Ulaş", "Yıldızeli", "Zara"],
    "Tekirdağ": ["Çerkezköy", "Çorlu", "Ergene", "Hayrabolu", "Kapaklı", "Malkara", "Marmara Ereğlisi", "Muratlı", "Saray", "Şarköy", "Süleymanpaşa"],
    "Tokat": ["Almus", "Artova", "Başçiftlik", "Erbaa", "Niksar", "Pazar", "Reşadiye", "Sulusaray", "Tokat", "Turhal", "Yeşilyurt", "Zile"],
    "Trabzon": ["Akçaabat", "Araklı", "Arsin", "Beşikdüzü", "Çarşıbaşı", "Çaykara", "Dernekpazarı", "Düzköy", "Hayrat", "Köprübaşı", "Maçka", "Of", "Ortahisar", "Şalpazarı", "Sürmene", "Tonya", "Vakfıkebir", "Yomra"],
    "Tunceli": ["Çemişgezek", "Hozat", "Mazgirt", "Nazımiye", "Ovacık", "Pertek", "Pülümür", "Tuncelı"],
    "Uşak": ["Banaz", "Eşme", "Karahallı", "Sivaslı", "Ulubey", "Uşak"],
    "Van": ["Bahçesaray", "Başkale", "Çaldıran", "Çatak", "Edremit", "Erciş", "Gevaş", "Gürpınar", "İpekyolu", "Muradiye", "Özalp", "Saray", "Tuşba"],
    "Yalova": ["Altınova", "Armutlu", "Çiftlikköy", "Çınarcık", "Termal", "Yalova"],
    "Yozgat": ["Akdağmadeni", "Aydıncık", "Boğazlıyan", "Çandır", "Çayıralan", "Çekerek", "Kadışehri", "Saraykent", "Sarıkaya", "Şefaatli", "Sorgun", "Yenifakılı", "Yerköy", "Yozgat"],
    "Zonguldak": ["Alaplı", "Çaycuma", "Devrek", "Ereğli", "Gökçebey", "Kilimli", "Kozlu", "Zonguldak"],
}

# Resmi kayıtta ayrı, sitelerde bitişik yazılan ilçeler ve eski adlar.
# "Gaziosmanpaşa" resmi listede "Gazi Osmanpaşa" olarak geçiyordu ve
# eşleşmiyordu.
TAKMA_AD = {
    "gaziosmanpasa": ("İstanbul", "Gazi Osmanpaşa"),
    "gop": ("İstanbul", "Gazi Osmanpaşa"),
    "eyup": ("İstanbul", "Eyüpsultan"),
    "sisli": ("İstanbul", "Şişli"),
    "besiktas": ("İstanbul", "Beşiktaş"),
    "kucukcekmece": ("İstanbul", "Küçükçekmece"),
    "buyukcekmece": ("İstanbul", "Büyükçekmece"),
    "seyhan": ("Adana", "Seyhan"),
    "merkezefendi": ("Denizli", "Merkezefendi"),
}

# Hızlı arama için katlanmış anahtarlar
# KAYNAK VERİDE ı/i BOZULMASI VAR.
# turkiye paketinden gelen listede merkez ilçeler "Afyonkarahısar",
# "Osmanıye", "Sıvas", "Sıırt" gibi yazılmış (büyük I küçük ı'ya
# çevrilmiş). Bu yüzden 226 kaydın ilçesi bozuk yazımla eşleşiyor,
# 115 kayıt da hiç tanınmıyordu ("Denizli" listede "Denizlı" idi).
#
# Merkez ilçe adı ilin kendi adıdır; fold ile eşleşen öğeyi ilin
# doğru yazımıyla değiştiriyoruz.
def _merkez_onar(harita: dict) -> dict:
    for il, ilceler in harita.items():
        f_il = fold(il)
        harita[il] = [il if fold(x) == f_il else x for x in ilceler]
        if f_il not in {fold(x) for x in harita[il]}:
            harita[il].append(il)          # merkez ilçe hiç yoksa ekle
    return harita


IL_ILCE = _merkez_onar(IL_ILCE)

ILCE_FOLD = {}
for _il, _liste in IL_ILCE.items():
    for _i in _liste:
        ILCE_FOLD.setdefault(fold(_i), []).append((_il, _i))
        # Boşluksuz hali de eşleşsin ("Gazi Osmanpaşa" → "gaziosmanpasa")
        _bitisik = fold(_i).replace(" ", "")
        if _bitisik != fold(_i):
            ILCE_FOLD.setdefault(_bitisik, []).append((_il, _i))
for _a, (_il, _i) in TAKMA_AD.items():
    ILCE_FOLD.setdefault(_a, [])
    if (_il, _i) not in ILCE_FOLD[_a]:
        ILCE_FOLD[_a].append((_il, _i))


def ilce_mi(metin: str, il: str = "") -> str:
    """Metin gerçek bir ilçe adı mı? Doğru yazımını döner, değilse boş.

    il verilirse yalnızca o ilin ilçeleri kabul edilir — "Merkez" gibi
    çok sayıda ilde bulunan adlarda yanlış eşleşmeyi önler.
    """
    if not metin:
        return ""
    f = fold(metin)
    adaylar = ILCE_FOLD.get(f)
    if not adaylar:
        return ""
    if il:
        for _il, _i in adaylar:
            if fold(_il) == fold(il):
                return _i
        return ""
    return adaylar[0][1]


def ilceden_il(metin: str) -> str:
    """İlçe adından ilini bulur. Birden çok ilde varsa boş döner."""
    adaylar = ILCE_FOLD.get(fold(metin))
    if adaylar and len({a[0] for a in adaylar}) == 1:
        return adaylar[0][0]
    return ""

# Adres içinde ilçe aramak için: uzun adlar önce denenmeli ki
# "Kadıköy" ararken "Köy" ile karışmasın.
_SIRALI = sorted(ILCE_FOLD.items(), key=lambda x: -len(x[0]))


import re as _re

# "Bahçelievler Mah." bir mahalle; ama Bahçelievler İstanbul'da ilçe de.
# Arkasından mahalle/cadde eki gelen eşleşmeler ilçe sayılmaz.
_MAHALLE_EKI = _re.compile(r"^\s*(mah|mh|mahalle|mahallesi|cad|cd|cadde|"
                           r"caddesi|sok|sk|sokak|bulv|blv|apt|sit|sitesi)\b")


def adresten_ilce(adres: str, il: str = "") -> str:
    """Adres metninde geçen ilçe adını bulur.

    Sayfada ilçe alanı yoksa ya da doğrulanamadıysa son çare. Adres
    neredeyse her zaman ilçeyi içeriyor: "... No:81 Alanya/Antalya".

    İki incelik:
      · Arkasından "Mah."/"Cad." gelen ad mahalledir, ilçe değil.
      · İlçe genelde adresin SONUNDA olur; en sağdaki eşleşme kazanır.
    """
    if not adres:
        return ""
    f = " " + fold(adres) + " "
    il_f = fold(il) if il else ""
    en_iyi, en_sag = "", -1
    # İl adının kendisi son çare: "... Alanya/Antalya" adresinde en sağdaki
    # eşleşme "Antalya" oluyor ve gerçek ilçe "Alanya" atlanıyordu. Bazı
    # illerde merkez ilçe il adını taşıdığı için tamamen elemiyoruz,
    # sadece geriye atıyoruz.
    yedek, yedek_sag = "", -1
    for anahtar, adaylar in _SIRALI:
        if len(anahtar) < 4:
            continue
        for m in _re.finditer(r"(?<= )" + _re.escape(anahtar) + r"(?= )", f):
            if _MAHALLE_EKI.match(f[m.end():]):
                continue
            secim = ""
            if il_f:
                for _il, _i in adaylar:
                    if fold(_il) == il_f:
                        secim = _i
                        break
            elif len({a[0] for a in adaylar}) == 1:
                secim = adaylar[0][1]
            if not secim:
                continue
            if il_f and fold(secim) == il_f:
                if m.start() > yedek_sag:
                    yedek, yedek_sag = secim, m.start()
                continue
            if m.start() > en_sag:
                en_iyi, en_sag = secim, m.start()
    return en_iyi or yedek
