# BAYİ RADAR — Devam Belgesi

Bu belgeyi yeni sohbetin ilk mesajına yapıştır. Sistemin ne olduğunu, nerede
kaldığını ve sıradaki işleri anlatır.

---

## 1. Sistem nedir

Türkiye'deki **62 motosiklet markasının** yetkili bayi ve servis ağını
markaların **kendi resmi sitelerinden** toplayan, sonucu tek bir web sayfasında
gösteren sistem. GitHub Actions üzerinde çalışıyor, ücretsiz.

**Depo:** https://github.com/ramazanbasaran34-blip/bayi_servisler
**Yayın:** https://ramazanbasaran34-blip.github.io/bayi_servisler/

Erişim için ince ayarlı bir GitHub anahtarı (fine-grained token) kullanılıyor;
Contents, Actions ve Pages yetkileri açık. Anahtarın süresi **26 Eylül 2026**'da
doluyor. Yeni sohbette anahtarı tekrar vermek gerekir.

---

## 2. Mevcut durum

| | |
|---|---|
| Toplam kayıt | ~6.700 |
| Veri gelen marka | 37 / 62 |
| Kapsanan il | 78 / 81 |
| Ağır sorunlu kayıt oranı | %0,3 |
| Gerileme testi | 45 vaka, hepsi geçiyor |

**Gecelik otomatik tarama ASKIYA ALINDI.** Sistem oturana kadar tarama yalnızca
elle başlatılıyor. Açmak için `.github/workflows/tarama.yml` içindeki
`schedule` satırlarının yorumunu kaldırmak yeterli.

---

## 3. Dosya düzeni

```
bayiradar/
  collect.py     tarama akışı — kademeli deneme, süre sınırları
  otomatik.py    tarif yazmadan sayfa yapısını çözen ayrıştırıcı
  parse.py       kaydı standart şemaya oturtur (il/ilçe belirleme burada)
  ilceler.py     81 il, 973 ilçe resmi listesi + doğrulama
  normalize.py   Türkçe metin, telefon, il eşleme
  eslestir.py    aynı firmayı farklı listelerde tanıma (satış/servis birleştirme)
  store.py       SQLite, veri koruma, rol birleştirme
  fetch.py       HTTP + tarayıcı; il seçerek gezme, tür süzgeci
  koordinat.py   81 il koordinatı, Türkiye sınır kontrolü

brands.yaml           62 markanın tarifi — ASIL KONFİGÜRASYON
uret_index.py         index.html üretici (arayüzün tamamı burada)
denetle.py            veri kalitesi denetimi, marka marka tablo
test_ayristirici.py   45 vakalık gerileme testi — DEĞİŞİKLİKTEN SONRA ÇALIŞTIR
birlestir.py          paralel tarama parçalarını birleştirir
gruplar.py            markaları 10 paralel gruba böler
yakala.py             sayfaları indirip depoya kaydeder (yerel geliştirme için)
kesif2.py             sayfanın arka plan isteklerini ve etkileşimini raporlar

yakalanan/     100 markanın kaydedilmiş HTML'i (.html.gz) — yerelde test için
kesif/         derin keşif raporu (hangi sayfa ne yapıyor)
logolar/       Kuralkan ve Dayanışma logoları (base64)
```

---

## 4. Çalışma yöntemi — ÖNEMLİ

Bu projede **tarama yaparak hata aramak** çok pahalıya mal oldu (her tur 2-8
saat, 30'a yakın tur). Doğru yöntem şu:

1. `yakalanan/` klasöründeki kaydedilmiş HTML'i aç, yapısını **gör**
2. O markaya özel tarif yaz, **yerelde test et** (saniyeler sürer, ağ gerekmez)
3. `python test_ayristirici.py` — 45 vakanın hepsi geçmeli
4. Ancak ondan sonra o markayı taramaya gönder

Yerel test kalıbı:

```python
import gzip
from bayiradar.otomatik import cikar
from bayiradar.parse import finalize
h = gzip.decompress(open("yakalanan/MARKA-rol.html.gz","rb").read()).decode()
r = [finalize(x, "Marka", "url", {}) for x in cikar(h)]
r = [x for x in r if x]
print(len(r), r[:3])
```

---

## 5. brands.yaml tarif seçenekleri

```yaml
"MarkaAdı":
  mode: browser              # JS ile yüklenen sayfalar
  etkilesim: il_secimi       # il seçimi URL'e yansımıyorsa: sayfayı gerçekten kullan
  encoding: windows-1254     # Türkçe karakter bozuksa
  beklenen: [alt, üst]       # saha bilgisi; denetim buna göre uyarır
  tur_suzgeci:               # bayi/servis sayfada süzgeçle ayrılıyorsa
    secici: "select[name=category]"
    degerler:
      - {deger: "Bayi",   rol: satis}
      - {deger: "Servis", rol: servis}
  kaynaklar:
    - rol: satis             # satis | servis | satis_servis
      url: "https://.../bayiler?sehir={il_slug}"
      iterate: il_slug       # ya da {type: sayi, bitis: 81}
      il_url_den: true       # ili URL'den al
  row: "div.kart"            # CSS seçici tarifi (otomatik çözüm tutmazsa)
  fields:
    bayi_adi: "h3.baslik"
    adres: "div.adres"
    telefon: {sel: "a.tel", attr: "href", regex: "tel:(.+)"}
  il_ilce_birlesik: konum    # "KADIKÖY - İstanbul" tek alandaysa
  ekstra_alanlar:
    konum: "div.sehir"
```

**Çalışan örnek — Arora** (20 kayıttan 873'e çıkardı):

```yaml
"Arora":
  mode: browser
  tur_suzgeci:
    secici: "input[name=yetkili-servis]"
    degerler:
      - {deger: "B",  rol: satis}
      - {deger: "S",  rol: servis}
      - {deger: "BS", rol: satis_servis}
  kaynaklar:
    - rol: satis_servis
      url: "https://www.arora.com.tr/hizmet-noktalari"
  row: "div.points-card-wrapper"
  fields:
    bayi_adi: "h3.points-card-title"
    adres:    "div.points-card-address"
    telefon:  {sel: "a.points-card-tel", attr: "href", regex: "tel:(.+)"}
  il_ilce_birlesik: konum
  ekstra_alanlar:
    konum: "div.points-card-city"
```

---

## 6. YAPILACAKLAR — markalar

Hepsi aynı sınıfta: sayfada **harita tıklama** ya da **çok adımlı seçim** var.
Kullanıcının verdiği adresler ve kesin sayılar:

| Marka | Adres | Yapılacak | Kesin sayı |
|---|---|---|---|
| **Yamaha** | yamaha-motor.eu/tr/tr/dealer-locator/?category=MCM | Ülke=Türkiye, kategori=Motorcycles, hizmet=tümü seç; haritadaki noktalara tıkla | 45 (satış+servis birleşik) |
| **BMW** | bmw-motorrad.com.tr/tr/ssl/yetkili-satici-ve-servisler.html | Yetkili satıcı / yetkili servis seç, sonra il, sonra "tümü" | 14 satış, 18 servis |
| **Ducati** | korlas.com.tr/bayi/ ve /servis/ | Yandaki il kutucuklarına tıklayarak liste açılıyor | 12 bayi, 31 servis (Kıbrıs hariç) |
| **Triumph** | Korlas'a bağlı, Ducati ile aynı yapı | Aynı | — |
| **Kuba** | kubamotor.com.tr/bayi-servis/kubamotor | Bayi/servis seç → il seç → ilçe seç | ~400 bayi, ~600 servis |
| **RKS** | rksmotor.com.tr/bayi-servis/rksmotor.html | Kuba ile aynı yapı | — |
| **Kymco** | — | il seçici var, çalışmıyor | ~50 bayi, ~70 servis |
| **Meka Motor** | mekamotor.com.tr/bayi-ve-servis | Önce il, sonra bayi/servis kutucuğu | Sadece bayi geldi, servis eksik |
| **Kimmi** | kimmimotor.com/servisler/ | İl seçerek ya da haritadan | Servis hiç gelmedi |
| **Leksas** | leksas.com.tr/bayi-servis/ | İl + ilçe + bayi/servis seçimi | Servis hiç gelmedi |
| **Taktas** | taktas.com.tr/servislerimiz | Haritadan il resmine tıklanıyor | Servis hiç gelmedi |
| **KTM** | spormoto.com/ktm/bayiler/ ve /ktm/ktm-servisler/ | Bayilerde tam liste; serviste şehir seçimi | 34 satış |
| **Husqvarna** | spormoto.com/husqvarna/... | KTM ile aynı | 34 satış |
| **Arnica** | arnicamotor.com/servisler?lang=tr&sehir_id=N | Liste hâlinde; adreste "İLÇE / İL" yazıyor | Servis 0 geldi |
| **CSN** | csnmotor.com.tr/servis-noktalarimiz/ | Haritadan il tıklanıyor; adres çubuğuna /il geliyor | Servis 0 geldi |
| **FCM** | fcmmotor.com/yetkili-servisler | Haritadan il tıklanıyor | İl bilinmiyor sorunu |
| **Peugeot / Horwin / Lambretta** | isotlarmotor.com/bayiler/ | Marka resmi seç → alttan yetkili servis/satıcı seç | Sadece servis geliyor, satış 0 |
| **Nanok** | — | il seçici var, çalışmıyor | — |

---

## 7. Kullanıcının kuralları

- **Sadece verdiği resmi linkler** kaynak. motorcular.com gibi üçüncü siteler
  güvenilmez (5 yıl önceki veri, kapananları silmiyor).
- Aynı firmanın **şubeleri ayrı kayıt** sayılır (farklı adres/telefon).
- **Merkez ilçe** yazılmaz; "Aksaray / Merkez" değil "Aksaray".
- Adres yanında **ilçe / il** görünmeli.
- Başlıklarda "ikisi" değil **"Satış + Servis"**.
- Honda ve Yamaha'da satış/servis ayrımı yok, hepsi **satış+servis**.
- Acele etme, önce test et, sonra tara. Her tarama saatler sürüyor.

---

## 8. Yol boyunca bulunmuş kritik hatalar (tekrarlanmasın)

1. **`inner_text()` `<option>` üzerinde boş döner** — `text_content()` kullan.
   Bu hata 28 markada il listesinin hiç okunmamasına yol açtı.
2. **Telefon kalıbı** herhangi bir 10 haneli sayıyı telefon sayıyordu
   (koordinat, ürün kodu). Ayrıştırıcı doğru kabı seçerken bu sayıya baktığı
   için bütün seçim mantığı bozuktu.
3. **Süre sınırı marka başınaydı** — satış uzun sürünce servis hiç taranmıyordu.
   Kaynak başına olmalı.
4. **Kaynak rolü sayfa etiketini ezmeli** — servis sayfasındaki "Bayi" kelimesi
   562 kaydın rolünü satışa çeviriyordu.
5. **Tarama sürerken depoya kod yükleme** — sonuç push'u reddedilir, 142
   dakikalık iş kaybolur. İş akışında artık yeniden deneme var.
6. **İş akışına marka adı gönderirken tırnak kullanma** — kabuk komutunu bozar,
   betik sessizce çöker. Virgülle ayır, dosyaya yaz, `xargs` ile aktar.
7. **Yol adları il sanılıyordu** — "KAYSERİ YOLU", "İZMİR BULVARI". İl adından
   sonra yol eki geliyorsa sayılmaz.

---

## 9. Komutlar

```bash
python cli.py tara --marka "Arora"      # tek marka
python cli.py durum                      # marka sağlık tablosu
python denetle.py                        # veri kalitesi denetimi
python denetle.py --marka Rutec          # tek markanın ayrıntısı
python test_ayristirici.py               # 45 vakalık gerileme testi
python uret_index.py site/index.html     # sayfayı üret
python yakala.py Kuba RKS                # sayfaları indir (GitHub'da çalışır)
python kesif2.py Yamaha BMW              # sayfanın ne yaptığını raporla
```

Tarama başlatma: GitHub → Actions → "Bayileri tara ve siteyi yayınla" →
Run workflow. `markalar` alanına boşlukla ayrılmış marka adları yazılabilir;
boş bırakılırsa periyodu dolanlar taranır, `hepsi` alanına "evet" yazılırsa
tümü taranır.

---

## 10. Kullanıcının istediği son özellik

Sistem tamamlanamayan markalar için **elle veri girme alanı**. Excel'den veri
girilebilecek, tarama sonrası elle girilen bozulmayacak, elle girilen doğru
kabul edilecek. Öncelik sistemin çalışması; bu son çare.
