#!/usr/bin/env python3
"""Ayrıştırıcı gerileme testi.

Şimdiye kadar bulunan her hata kalıbı için bir vaka. Bir düzeltme başka bir
şeyi bozarsa burada yakalanır. Yayına almadan önce bu geçmeli.

    python test_ayristirici.py
"""

import sys

from bayiradar.normalize import fold
from bayiradar.otomatik import cikar, tur_coz
from bayiradar.parse import finalize

BASARILI, BASARISIZ = [], []


def kontrol(ad, html, beklenen, marka="Test"):
    """beklenen: [{alan: değer, ...}] — sadece verilen alanlar denetlenir."""
    ham = cikar(html)
    kayitlar = [finalize(r, marka, "https://test", {}) for r in ham]
    kayitlar = [k for k in kayitlar if k]

    hatalar = []
    if len(kayitlar) != len(beklenen):
        hatalar.append(f"{len(beklenen)} kayıt beklendi, {len(kayitlar)} geldi")
    for i, bek in enumerate(beklenen):
        if i >= len(kayitlar):
            break
        for alan, deger in bek.items():
            gercek = kayitlar[i].get(alan, "")
            if fold(deger) not in fold(str(gercek)):
                hatalar.append(f"#{i+1} {alan}: '{deger}' beklendi, "
                               f"'{gercek}' geldi")
    if hatalar:
        BASARISIZ.append((ad, hatalar, kayitlar))
        print(f"  ✗ {ad}")
        for h in hatalar[:4]:
            print(f"      {h}")
    else:
        BASARILI.append(ad)
        print(f"  ✓ {ad}")


def kart(*satirlar):
    return "".join(satirlar)


print("\nAYRIŞTIRICI GERİLEME TESTİ\n" + "=" * 60)

# ---------------------------------------------------------------- 1
print("\n1. Düz tablo (Mondial tipi)")
kontrol("tablo: ad/adres/ilçe/telefon",
    "<table><tbody>" + "".join(
      f'<tr><td>{a}</td><td>{ad}</td><td>{i}</td>'
      f'<td><a href="tel:{t}">{t}</a></td></tr>'
      for a, ad, i, t in [
        ("ASIL GRUP OTOMOTIV LTD", "İNÖNÜ MAH. KAR SK. NO:4", "ATAŞEHİR", "2165193636"),
        ("HAYAL MOTOSIKLET", "ÜNİVERSİTE MAH. FİRUZKÖY BULV. NO:16", "AVCILAR", "5070642092"),
        ("MICRON MOTORLU ARAÇLAR", "PINAR MAH. ÇAMLIBEL CAD. NO:7", "SARIYER", "2122761222"),
        ("EGE MOTOR SANAYİ", "AKDENİZ MAH. CUMHURİYET BLV. NO:8", "KONAK", "2324412233"),
      ]) + "</tbody></table>",
    [{"bayi_adi": "ASIL GRUP"}, {"bayi_adi": "HAYAL"},
     {"bayi_adi": "MICRON"}, {"bayi_adi": "EGE MOTOR"}])

# ---------------------------------------------------------------- 2
print("\n2. Tür etiketi (Rutec tipi) — etiket ad sanılmamalı")
kontrol("tür etiketi rol olarak okunmalı",
    "<div class='l'>" + "".join(
      f'<div class="k"><span class="tur">{tur}</span><h4>{ad}</h4>'
      f'<p>{il}</p><p>{adr}</p><a href="tel:{t}">{t}</a></div>'
      for tur, ad, il, adr, t in [
        ("Satış Noktası", "AYSAN MOTOR", "Adana", "Çınarlı Mah. Beriker Blv. No:31", "05375906519"),
        ("Yetkili Servis", "ÇETUR ÇELEBİ BURSA", "Bursa", "Panayır Mah. Yalova Cad. No:407", "08502106210"),
        ("Bölge Bayisi", "POYRAZ GLOBAL MOTOR", "Ankara", "Ostim Mah. 1201. Cad. No:12", "05448208002"),
        ("Yetkili Servis", "DENİZ MOTOSİKLET", "İzmir", "Konak Mah. Cumhuriyet Blv. No:5", "02324412233"),
      ]) + "</div>",
    [{"bayi_adi": "AYSAN", "rol": "satis", "il": "Adana"},
     {"bayi_adi": "ÇETUR", "rol": "servis", "il": "Bursa"},
     {"bayi_adi": "POYRAZ", "rol": "satis", "il": "Ankara"},
     {"bayi_adi": "DENİZ", "rol": "servis", "il": "İzmir"}])

# ---------------------------------------------------------------- 3
print("\n3. Etiketli alanlar (Voge tipi) — İlçe: / Tel: / Adres:")
kontrol("etiketli alanlar doğru okunmalı",
    "<div class='l'>" + "".join(
      f'<div class="dm-dealer-card"><div class="dm-dealer-name">{ad}</div>'
      f'<span class="dm-tip">{tur}</span><div class="dm-dealer-meta">'
      f'<div><strong>İlçe:</strong> {i}</div>'
      f'<div><strong>Tel:</strong> <a href="tel:{t}">{t}</a></div>'
      f'<div><strong>Adres:</strong> {adr}</div></div></div>'
      for ad, tur, i, t, adr in [
        ("ALAÇATI BİSİKLET", "Bayi + Servis", "ÇEŞME", "0232 716 89 70", "İSMETİNÖNÜ MAH. 2001 SK. NO: 160/A"),
        ("AK-PA TEMEL GIDA", "Bayi + Servis", "İNCİRLİOVA", "0532 273 54 84", "CUMHURİYET MAH. GÜRSEL CAD. NO: 3"),
        ("ACAR MOTORS", "Bayi", "ÜSKÜDAR", "0507 377 53 03", "ATATÜRK MAH. NUH KUYUSU CAD. NO:30"),
        ("EGE MOTO", "Servis", "KONAK", "0232 441 22 33", "AKDENİZ MAH. CUMHURİYET BLV. NO:8"),
      ]) + "</div>",
    [{"bayi_adi": "ALAÇATI", "ilce": "ÇEŞME", "rol": "satis_servis"},
     {"bayi_adi": "AK-PA", "ilce": "İNCİRLİOVA"},
     {"bayi_adi": "ACAR MOTORS", "ilce": "Üsküdar", "rol": "satis"},
     {"bayi_adi": "EGE MOTO", "ilce": "KONAK", "rol": "servis"}])

# ---------------------------------------------------------------- 4
print("\n4. İlçe başlığı (Honda/Antalya tipi) — ilçe ad sanılmamalı")
kontrol("ilçe başlığı firma adı olmamalı",
    "<div class='l'>" + "".join(
      f'<div class="k"><h4>{ilce}</h4><span>{ad}</span>'
      f'<span>{adr}</span><a href="tel:{t}">{t}</a></div>'
      for ilce, ad, adr, t in [
        ("ALANYA", "Kervan Motor Ticaret", "Cikcilli Mah. Atatürk Cad. No:5 Alanya/Antalya", "02425110022"),
        ("MANAVGAT", "Toros Motosiklet", "Aşağı Pazarcı Mah. Demokrasi Blv. No:9 Manavgat/Antalya", "02427421133"),
        ("MURATPAŞA", "Akdeniz Moto San.", "Meltem Mah. Dumlupınar Blv. No:22 Muratpaşa/Antalya", "02422410099"),
        ("SERİK", "Deniz Motor", "Merkez Mah. Cumhuriyet Cad. No:3 Serik/Antalya", "02427221144"),
      ]) + "</div>",
    [{"bayi_adi": "Kervan", "ilce": "Alanya", "il": "Antalya"},
     {"bayi_adi": "Toros", "ilce": "Manavgat"},
     {"bayi_adi": "Akdeniz", "ilce": "Muratpaşa"},
     {"bayi_adi": "Deniz Motor", "ilce": "Serik"}])

# ---------------------------------------------------------------- 5
print("\n5. İl başlığı (Kove tipi) — il ad sanılmamalı")
kontrol("il başlığı firma adı olmamalı",
    "<div class='l'>" + "".join(
      f'<div class="k"><h3>{il}</h3><span>{ad}</span>'
      f'<span>{adr}</span><a href="tel:{t}">{t}</a></div>'
      for il, ad, adr, t in [
        ("BALIKESİR", "Nc Motor Ticaret", "Altıeylül Mah. Atatürk Cad. No:4", "05315047470"),
        ("KIRKLARELİ", "Tmd Motor Sanayi", "Merkez Mah. İstasyon Cad. No:2", "02884172520"),
        ("İSTANBUL", "Kadıköy Moto Ltd", "Caferağa Mah. Moda Cad. No:112", "02163456789"),
        ("ANKARA", "Başkent Motor San", "Ostim Mah. 1201. Cad. No:7", "03124356788"),
      ]) + "</div>",
    [{"bayi_adi": "Nc Motor", "il": "Balıkesir"},
     {"bayi_adi": "Tmd Motor", "il": "Kırklareli"},
     {"bayi_adi": "Kadıköy Moto", "il": "İstanbul"},
     {"bayi_adi": "Başkent Motor", "il": "Ankara"}])

# ---------------------------------------------------------------- 6
print("\n6. Birleşik konum (SYM tipi) — 'İZMİR-TORBALI' ayrılmalı")
kontrol("birleşik il/ilçe ayrılmalı",
    "<div class='l'>" + "".join(
      f'<div class="vc_inner"><span>{konum}</span><span>{ad}</span>'
      f'<span>{adr}</span><span>{t}</span></div>'
      for konum, ad, adr, t in [
        ("İZMİR-TORBALI", "ALİ BULUT MOTOR", "Ertuğrul Mah. İzmir Cad. No:11", "0 232 856 41 22"),
        ("MUĞLA / BODRUM", "TURCAN EĞLENCE TİC. LTD.", "Yokuşbaşı Mah. Kıbrıs Şehitleri Cad. No:2", "0 252 313 06 62"),
        ("ANKARA / YENİMAHALLE", "DURAN MOTOR TİCARET", "Ostim Mah. 1201. Cad. No:19", "0 543 144 47 45"),
        ("İSTANBUL-ATAŞEHİR", "MOTOTAL LTD. ŞTİ.", "Küçükbakkalköy Mah. Tevfik Fikret Cad. No:24", "0 216 347 61 71"),
      ]) + "</div>",
    [{"bayi_adi": "ALİ BULUT", "il": "İzmir", "ilce": "TORBALI"},
     {"bayi_adi": "TURCAN", "il": "Muğla", "ilce": "BODRUM"},
     {"bayi_adi": "DURAN MOTOR", "il": "Ankara", "ilce": "Yenimahalle"},
     {"bayi_adi": "MOTOTAL", "il": "İstanbul", "ilce": "ATAŞEHİR"}])

# ---------------------------------------------------------------- 7
print("\n7. Ayrı bloklar (Bajaj tipi) — hepsi birleşmeli")
kontrol("ayrı gruplardaki kartlar birleşmeli",
    "<div class='a'>" + "".join(
      f'<div class="cursor-pointer rounded-lg border"><h3>{ad}</h3>'
      f'<span>Satış</span><span>{adr}, {i}</span>'
      f'<a href="tel:{t}">{t}</a></div>'
      for ad, adr, i, t in [
        ("AHMET KİREMİTÇİ MOTOR", "Çavuşbaşı Cd. no:33/A", "ÇEKMEKÖY", "05413950367"),
        ("YAŞAR TİCARET LTD", "Merkez Mah. Cumhuriyet Cad. No:5", "ÜMRANİYE", "05413950368"),
      ]) + "</div><div class='b'>" + "".join(
      f'<div class="cursor-pointer rounded-lg border"><h3>{ad}</h3>'
      f'<span>Servis</span><span>{adr}, {i}</span>'
      f'<a href="tel:{t}">{t}</a></div>'
      for ad, adr, i, t in [
        ("KARDEŞLER MOTOR SAN", "Fidanlık Mah. 40. Sk. No:10", "REYHANLI", "05334113628"),
        ("ALİ KEMAL MOTOSİKLET", "Yeni Mah. İstasyon Cad. No:8", "İSKENDERUN", "05334113629"),
      ]) + "</div>",
    [{"bayi_adi": "AHMET KİREMİTÇİ", "rol": "satis"},
     {"bayi_adi": "YAŞAR TİCARET", "rol": "satis"},
     {"bayi_adi": "KARDEŞLER MOTOR", "rol": "servis"},
     {"bayi_adi": "ALİ KEMAL", "rol": "servis"}])

# ---------------------------------------------------------------- 8
print("\n8. Çöp sayfa — kayıt ÜRETİLMEMELİ")
cop = "".join(f'<div class="c"><span>24{c}</span><span>2{i}5</span>'
              f'<span>0212 000 00 0{i%10}</span></div>'
              for i, c in enumerate("dhkmsvy"))
r = cikar(f"<body><div class='menu'>{cop}</div></body>")
if len(r) == 0:
    BASARILI.append("çöp sayfa reddedildi"); print("  ✓ çöp sayfa reddedildi")
else:
    BASARISIZ.append(("çöp sayfa reddedilmeli", [f"{len(r)} kayıt üretti"], r))
    print(f"  ✗ çöp sayfa reddedilmeli — {len(r)} kayıt üretti")

urun = "".join(f'<div class="u"><h3>TK0{i}</h3><p>Fiyat: {70+i}.568 TL</p></div>'
               for i in range(1, 6))
r2 = cikar(f"<div>{urun}</div>")
if len(r2) == 0:
    BASARILI.append("ürün listesi reddedildi"); print("  ✓ ürün listesi reddedildi")
else:
    BASARISIZ.append(("ürün listesi reddedilmeli", [f"{len(r2)} kayıt"], r2))
    print(f"  ✗ ürün listesi reddedilmeli — {len(r2)} kayıt")

# ---------------------------------------------------------------- 9
print("\n9. Çoklu telefon ve tür etiketi tanıma")
for metin, bek in [("Satış Noktası", "satis"), ("Yetkili Servis", "servis"),
                   ("Bölge Bayisi", "satis"), ("Satış ve Servis", "satis_servis"),
                   ("Bayi + Servis", "satis_servis"), ("Teknik Servis", "servis"),
                   ("AYSAN MOTOR", ""), ("Servis Motor Ticaret A.Ş.", ""),
                   ("Kadıköy", ""), ("Balıkesir", "")]:
    g = tur_coz(metin)
    if g == bek:
        BASARILI.append(f"tür: {metin}")
    else:
        BASARISIZ.append((f"tür: {metin}", [f"'{bek}' beklendi, '{g}' geldi"], []))
        print(f"  ✗ tür '{metin}': '{bek}' beklendi, '{g}' geldi")
print(f"  ✓ tür etiketi tanıma ({sum(1 for b in BASARILI if b.startswith('tür:'))}/10)")

# ---------------------------------------------------------------- 10
print("\n10. İlçe doğrulama — mahalle/çöp ilçe alanına yazılmamalı")
kontrol("gerçek olmayan ilçe reddedilmeli",
    "<div class='l'>" + "".join(
      f'<div class="k"><h4>{sahte}</h4><span>{ad}</span>'
      f'<span>{adr}</span><a href="tel:{t}">{t}</a></div>'
      for sahte, ad, adr, t in [
        ("Haritada Gör", "Tezak Motors Ticaret", "Oba Mah. Çevre Yolu Cad. No:81 Alanya", "02425110022"),
        ("Sizi Arayalım", "Gns Motors Sanayi", "Kızıltoprak Mah. Perge Blv. No:7 Muratpaşa", "02422410099"),
        ("Halil Bike", "Halil Bike Motosiklet", "Bahçelievler Mah. Atatürk Cad. No:3 Kepez", "02423440077"),
        ("Exclusive", "Motoser Otomotiv Ltd", "Güzeloba Mah. Rauf Denktaş Cad. No:12 Muratpaşa", "02423120055"),
      ]) + "</div>",
    [{"bayi_adi": "Tezak", "ilce": "Alanya"},
     {"bayi_adi": "Gns Motors", "ilce": "Muratpaşa"},
     {"bayi_adi": "Halil Bike", "ilce": "Kepez"},
     {"bayi_adi": "Motoser", "ilce": "Muratpaşa"}])

# ---------------------------------------------------------------- 11
print("\n11. E-posta firma adı olmamalı (Bajaj tipi)")
kontrol("e-posta ad alanına yazılmamalı",
    "<div class='l'>" + "".join(
      f'<div class="k"><h4>{ad}</h4><span>{eposta}</span>'
      f'<span>{adr}</span><a href="tel:{t}">{t}</a></div>'
      for ad, eposta, adr, t in [
        ("BAYMOTO OTOMOTİV TİC.LTD.ŞTİ.", "baymoto@gmail.com",
         "Caferağa Mah. Moda Cad. No:5 Kadıköy", "02163456789"),
        ("YAŞAR TİCARET MOTOSİKLET", "yasarticaret34@gmail.com",
         "Çavuşbaşı Cad. No:33 Çekmeköy", "05413950367"),
        ("PEKER MOTOR SANAYİ", "pekermotorr@gmail.com",
         "Merkez Mah. Cendere Cad. No:9 Kağıthane", "02122223344"),
        ("ERENCE MOTO GARAGE LTD", "erence@motogarage.com.tr",
         "Alibeyköy Mah. Fetih Cad. No:2 Eyüpsultan", "02125556677"),
      ]) + "</div>",
    [{"bayi_adi": "BAYMOTO", "email": "baymoto@gmail.com", "ilce": "Kadıköy"},
     {"bayi_adi": "YAŞAR TİCARET", "ilce": "Çekmeköy"},
     {"bayi_adi": "PEKER MOTOR", "ilce": "Kağıthane"},
     {"bayi_adi": "ERENCE", "ilce": "Eyüpsultan"}])

# ---------------------------------------------------------------- 12
print("\n12. Arayüz metni firma adı olmamalı (Honda tipi)")
kontrol("buton yazısı ad alanına yazılmamalı",
    "<ul>" + "".join(
      f'<li class="k"><div><p class="tt">{ad}</p><span>{ilce}</span></div>'
      f'<a href="tel:{t}"><span>Şimdi arayın</span><p>{t}</p></a>'
      f'<a href="#"><span>Yol tarifi alın</span><p>{adr}</p></a>'
      f'<div><p>Honda ile konuşun</p>'
      f'<label>Satış danışmanı ile görüşmek istiyorum</label>'
      f'<label>Test sürüşü randevusu almak istiyorum</label>'
      f'<label>Servis randevusu almak istiyorum</label></div></li>'
      for ad, ilce, adr, t in [
        ("Honda Motosiklet Alp", "Gaziosmanpaşa",
         "Merkez Mah. Eski Edirne Asfaltı No:10/A Gaziosmanpaşa / İstanbul", "02122168484"),
        ("Honda Motosiklet Anes", "Bahçelievler",
         "Basın Ekspres Yolu Cemal Ulusoy Cad. No:25 Bahçelievler / İstanbul", "02124518080"),
        ("Honda Motosiklet Esengül", "Şişli",
         "Mahmut Şevket Paşa Mah. Odesa Bulvarı No:22 Şişli / İstanbul", "02123208080"),
        ("Honda Motosiklet Marmara", "Beylikdüzü",
         "Yakuplu Mah. Sanayi Cd. No:1/B Beylikdüzü / İstanbul", "02124565859"),
      ]) + "</ul>",
    [{"bayi_adi": "Honda Motosiklet Alp", "ilce": "Gazi Osmanpaşa"},
     {"bayi_adi": "Honda Motosiklet Anes", "ilce": "Bahçelievler"},
     {"bayi_adi": "Honda Motosiklet Esengül", "ilce": "Şişli"},
     {"bayi_adi": "Honda Motosiklet Marmara", "ilce": "Beylikdüzü"}])

# ---------------------------------------------------------------- 13
print("\n13. Yol adındaki il/ilçe adı konum sanılmamalı")
from bayiradar.normalize import il_ara
from bayiradar.ilceler import adresten_ilce
_t = 0
for metin, bek in [
    ("BARBAROS MAH. 11032. SOKAK (KAYSERİ YOLU, AKEDAŞ KARŞISI)", ""),
    ("50. YIL MAH. ESKİ EDİRNE ASFALTI CAD. NO: 542", ""),
    ("ERTUĞRUL MAH. İZMİR AYDIN CAD. NO: 242", ""),
    ("ÖĞRETMENEVLERİ MAH. ORDU CAD. NO:98/A", ""),
    ("ZEYBEK MAH. SANAYİ SİTESİ İZMİR BULVARI NO: 195", ""),
    ("HARMANDERE MAH ANKARA CAD NO:453/19", ""),
    ("Hasanpaşa Mah. Lavanta Sok.No:26/1 Kadıköy / İstanbul", "İstanbul"),
    ("Cikcilli Mah. Atatürk Cad. No:5 Alanya/Antalya", "Antalya"),
    ("Merkez Mah. PTT Sok. Eskil Aksaray", "Aksaray"),
]:
    g = il_ara(metin)
    if g == bek:
        BASARILI.append(f"il_ara: {metin[:24]}"); _t += 1
    else:
        BASARISIZ.append((f"il_ara: {metin[:34]}",
                          [f"'{bek}' beklendi, '{g}' geldi"], []))
        print(f"  ✗ il_ara '{metin[:40]}': '{bek}' beklendi, '{g}' geldi")
print(f"  ✓ yol adı tuzağı ({_t}/9)")

# ---------------------------------------------------------------- 14
print("\n14. Telefon tanıma — rakam yığınları telefon sayılmamalı")
from bayiradar.otomatik import TEL
_t = 0
for metin, bek in [
    ("1234567890123456789", 0), ("koordinat 41.008238 28.978359", 0),
    ("id=9876543210", 0), ("SKU 1029384756", 0), ("No:12345678901234", 0),
    ("fiyat 129900 TL", 0), ("posta kodu 34732 istanbul", 0),
    ("0216 345 67 89", 1), ("+90 212 555 44 33", 1), ("05321234567", 1),
    ("0 507 064 20 92", 1), ("(0212) 555 44 33", 1), ("0850 210 62 10", 1),
    ("Tel: 0232 441 22 33 Faks: 0232 441 22 34", 2),
]:
    g = len(TEL.findall(metin))
    if g == bek:
        BASARILI.append(f"tel: {metin[:20]}"); _t += 1
    else:
        BASARISIZ.append((f"tel: {metin[:30]}", [f"{bek} beklendi, {g} geldi"], []))
        print(f"  ✗ '{metin[:34]}': {bek} beklendi, {g} geldi")
print(f"  ✓ telefon tanıma ({_t}/14)")

# ---------------------------------------------------------------- özet
print("\n" + "=" * 60)
print(f"GEÇEN: {len(BASARILI)}   KALAN: {len(BASARISIZ)}")
if BASARISIZ:
    print("\nBAŞARISIZ VAKALAR:")
    for ad, hatalar, kayitlar in BASARISIZ:
        print(f"\n  {ad}")
        for h in hatalar:
            print(f"    · {h}")
        for k in kayitlar[:4]:
            print(f"      → ad='{k.get('bayi_adi','')[:30]}' il='{k.get('il','')}' "
                  f"ilçe='{k.get('ilce','')}' rol='{k.get('rol','')}'")
    sys.exit(1)
print("\nTümü geçti.")
