"""Koordinat işleri — harita tabanlı bayi bulucular için.

Bazı markalar (Yamaha, BMW, Harley-Davidson, Indian) bayi sayfasında il listesi
sunmuyor; harita üzerinden "sana en yakın bayi" mantığıyla çalışıyor. Bunlar
il adı değil enlem/boylam istiyor.

Bu modül üç işi yapıyor:
  1. 81 il merkezinin koordinatını tutuyor — sorguları bunlarla besliyoruz
  2. Gelen sonucun Türkiye sınırlarında olup olmadığını kontrol ediyor
     (global bulucular Yunanistan, Bulgaristan, İran bayilerini de döndürüyor)
  3. Koordinattan en yakın ili buluyor — sayfada il yazmıyorsa böyle dolduruyoruz
"""

import math

# İl merkezleri (enlem, boylam). Örneklem Google ile doğrulandı, sapma < 5 km.
IL_KOORDINAT = {
    "Adana": (37.00, 35.32), "Adıyaman": (37.76, 38.28),
    "Afyonkarahisar": (38.76, 30.54), "Ağrı": (39.72, 43.05),
    "Amasya": (40.65, 35.83), "Ankara": (39.93, 32.86), "Antalya": (36.90, 30.70),
    "Artvin": (41.18, 41.82), "Aydın": (37.85, 27.84), "Balıkesir": (39.65, 27.89),
    "Bilecik": (40.15, 29.98), "Bingöl": (38.88, 40.50), "Bitlis": (38.40, 42.11),
    "Bolu": (40.74, 31.61), "Burdur": (37.72, 30.29), "Bursa": (40.19, 29.06),
    "Çanakkale": (40.15, 26.41), "Çankırı": (40.60, 33.62), "Çorum": (40.55, 34.95),
    "Denizli": (37.78, 29.09), "Diyarbakır": (37.91, 40.24), "Edirne": (41.68, 26.56),
    "Elazığ": (38.68, 39.22), "Erzincan": (39.75, 39.49), "Erzurum": (39.90, 41.27),
    "Eskişehir": (39.78, 30.52), "Gaziantep": (37.07, 37.38), "Giresun": (40.91, 38.39),
    "Gümüşhane": (40.46, 39.48), "Hakkâri": (37.58, 43.74), "Hatay": (36.20, 36.16),
    "Isparta": (37.76, 30.55), "Mersin": (36.80, 34.63), "İstanbul": (41.01, 28.98),
    "İzmir": (38.42, 27.14), "Kars": (40.60, 43.10), "Kastamonu": (41.39, 33.78),
    "Kayseri": (38.73, 35.49), "Kırklareli": (41.74, 27.22), "Kırşehir": (39.15, 34.16),
    "Kocaeli": (40.77, 29.95), "Konya": (37.87, 32.48), "Kütahya": (39.42, 29.98),
    "Malatya": (38.36, 38.31), "Manisa": (38.62, 27.43),
    "Kahramanmaraş": (37.58, 36.93), "Mardin": (37.31, 40.74), "Muğla": (37.22, 28.36),
    "Muş": (38.73, 41.49), "Nevşehir": (38.62, 34.71), "Niğde": (37.97, 34.68),
    "Ordu": (40.98, 37.88), "Rize": (41.02, 40.52), "Sakarya": (40.76, 30.38),
    "Samsun": (41.29, 36.33), "Siirt": (37.93, 41.94), "Sinop": (41.87, 35.05),
    "Sivas": (39.75, 37.02), "Tekirdağ": (40.98, 27.51), "Tokat": (40.31, 36.55),
    "Trabzon": (41.00, 39.72), "Tunceli": (39.11, 39.55), "Şanlıurfa": (37.16, 38.80),
    "Uşak": (38.68, 29.41), "Van": (38.49, 43.38), "Yozgat": (39.82, 34.81),
    "Zonguldak": (41.46, 31.79), "Aksaray": (38.37, 34.03), "Bayburt": (40.26, 40.32),
    "Karaman": (37.18, 33.22), "Kırıkkale": (39.85, 33.52), "Batman": (37.89, 41.13),
    "Şırnak": (37.52, 42.46), "Bartın": (41.64, 32.34), "Ardahan": (41.11, 42.70),
    "Iğdır": (39.89, 44.00), "Yalova": (40.65, 29.28), "Karabük": (41.20, 32.63),
    "Kilis": (36.75, 37.10), "Osmaniye": (37.07, 36.25), "Düzce": (40.84, 31.16),
}

# Kaba ön eleme kutusu — polygon testinden önce ucuz kontrol
KUTU = {"enlem_min": 35.7, "enlem_max": 42.4,
        "boylam_min": 25.5, "boylam_max": 45.0}

# Türkiye sınırının basitleştirilmiş hali (boylam, enlem).
#
# Neden kutu yetmiyor: dikdörtgen kutu Halep'i, Selanik'i, Tebriz yakınını
# içine alıyor. Global bayi bulucular komşu ülke bayilerini de döndürdüğü için
# bu kayıtlar "Türkiye'de" sayılıp yanlış ile atanıyordu.
SINIR_COKGEN = [
    # Trakya ve Marmara
    (26.35, 41.71), (27.50, 42.00), (28.00, 41.98), (29.10, 41.22),
    # Karadeniz kıyısı, batıdan doğuya
    (31.40, 41.30), (33.80, 42.02), (35.15, 42.03), (36.30, 41.30),
    (38.40, 41.10), (40.50, 41.05), (41.55, 41.52),
    # Doğu sınırı: Gürcistan, Ermenistan, Nahçıvan, İran
    (43.45, 41.15), (43.60, 40.20), (44.80, 39.75), (44.40, 39.35),
    (44.05, 38.35), (44.35, 37.90), (44.80, 37.35),
    # Güney sınırı: Irak ve Suriye
    (42.80, 37.32), (42.35, 37.10), (41.20, 37.10), (40.20, 36.90),
    (38.60, 36.83), (37.80, 36.75), (37.50, 36.66), (36.95, 36.72),
    (36.65, 36.60), (36.62, 36.20), (35.95, 36.05),
    # Akdeniz kıyısı, doğudan batıya
    (34.90, 36.30), (33.70, 36.10), (32.80, 36.05), (31.20, 36.30),
    (30.55, 36.20), (29.10, 36.20), (28.10, 36.65), (27.25, 36.70),
    # Ege kıyısı
    (27.35, 37.30), (26.75, 37.65), (27.05, 38.40), (26.30, 38.60),
    (26.70, 39.55), (26.10, 39.50), (26.20, 40.05),
    # Çanakkale ve Trakya kıyısı
    (26.75, 40.45), (26.30, 40.85), (26.05, 41.30),
]


def _cokgende_mi(lng, lat, cokgen) -> bool:
    """Işın atma yöntemi: nokta çokgenin içinde mi?"""
    ic = False
    n = len(cokgen)
    j = n - 1
    for i in range(n):
        xi, yi = cokgen[i]
        xj, yj = cokgen[j]
        if (yi > lat) != (yj > lat) and \
           lng < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi:
            ic = not ic
        j = i
    return ic


def turkiyede_mi(lat, lng) -> bool:
    """Koordinat Türkiye sınırları içinde mi?"""
    try:
        lat, lng = float(lat), float(lng)
    except (TypeError, ValueError):
        return False
    if not (KUTU["enlem_min"] <= lat <= KUTU["enlem_max"]
            and KUTU["boylam_min"] <= lng <= KUTU["boylam_max"]):
        return False
    return _cokgende_mi(lng, lat, SINIR_COKGEN)


def mesafe_km(a, b) -> float:
    """İki koordinat arası kuşuçuşu mesafe (haversine)."""
    R = 6371.0
    la1, lo1 = math.radians(a[0]), math.radians(a[1])
    la2, lo2 = math.radians(b[0]), math.radians(b[1])
    h = (math.sin((la2 - la1) / 2) ** 2
         + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(h))


def en_yakin_il(lat, lng, azami_km=180) -> str:
    """Koordinata en yakın il merkezini bulur.

    azami_km: bundan uzaksa il atanmaz. Türkiye'nin en büyük ili Konya bile
    merkeze 180 km'den uzak noktalar içermiyor denemez; ama yanlış il yazmaktansa
    boş bırakmak daha iyi olduğu için sınır koyuyoruz.
    """
    if not turkiyede_mi(lat, lng):
        return ""
    nokta = (float(lat), float(lng))
    en_iyi, en_kisa = "", 1e9
    for il, k in IL_KOORDINAT.items():
        d = mesafe_km(nokta, k)
        if d < en_kisa:
            en_iyi, en_kisa = il, d
    return en_iyi if en_kisa <= azami_km else ""


def sorgu_noktalari(yaricap_km=120):
    """Harita tabanlı bulucuları beslemek için (il, lat, lng) listesi.

    81 il merkezi, ortalama 120 km yarıçapla Türkiye'yi fazlasıyla kaplıyor;
    kenar illerde bile boşluk kalmıyor çünkü komşu il merkezleri örtüşüyor.
    """
    return [(il, k[0], k[1]) for il, k in IL_KOORDINAT.items()]
