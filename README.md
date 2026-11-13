# Motosiklet Bayileri

63 motosiklet markasının resmi sitelerindeki yetkili bayi listelerini toplar,
il/ilçe bazında birleştirir ve tek sayfada yayınlar.

**Kurulum:** [KURULUM-GITHUB.md](KURULUM-GITHUB.md) — 6 adım, 10 dakika,
bilgisayarına hiçbir şey kurulmaz.

---

## Nasıl çalışır

```
Her gece 03:00
   ↓
GitHub sunucusu brands.yaml'daki markaları sırayla gezer
   ↓
Veriyi temizler (Türkçe karakter, il/ilçe ayrıştırma, tekilleştirme)
   ↓
bayiler.db'ye yazar — hiçbir kayıt silinmez
   ↓
index.html üretilir ve yayınlanır
   ↓
https://KULLANICI-ADIN.github.io/motosiklet-bayileri/
```

## Sayfa iki modda çalışır

Bir marka **taranmışsa**, satırı açılır ve o ildeki bayilerini gösterir.
**Taranmamışsa**, satır markanın kendi bayi sayfasına götürür.

Yani sistem yarım doluyken de işe yarar. Tarif ekledikçe link satırları
gerçek listeye dönüşür.

## Veri asla silinmez

Bir markanın sitesi gece açılmazsa o markanın bayileri listeden düşmez.
Sarı işaretle "son doğrulanmış veri" olarak kalır. Detay:
[bayiradar/store.py](bayiradar/store.py) başındaki açıklama.

Dört katmanlı koruma: toptan çökme, kısmi çökme (sayfaların bir kısmı
gelmemesi), anomali eşiği (kayıt sayısının çakılması), kayıp sayacı
(bir bayi 3 sağlıklı taramada görünmezse düşmüş sayılır).

## Tarif yazmak gerekmiyor

63 markanın hiçbirinde CSS seçici yazılı değil. Sistem sayfadaki tekrar eden
yapıyı kendisi buluyor: telefon ve adres içeren, kardeşleri aynı sınıfa sahip
kapları arıyor, en yüksek puanlıyı seçiyor, alanları ayıklıyor.
Ayrıntı: [bayiradar/otomatik.py](bayiradar/otomatik.py)

Tablo, kart ızgarası, article ve WordPress kalıplarında test edildi; bayi
listesi olmayan sayfalarda kayıt üretmiyor.

Bir markada tutmazsa sistem 0 kayıt görüp `hatali` işaretler ve eski veriyi
korur. Sadece o markaya elle `row` + `fields` yazılır — yazıldığı anda otomatik
mod devre dışı kalır.

Tek bir sayfayı incelemek için:

```bash
python kesfet.py "https://ornek.com/bayiler"
```

Actions sekmesindeki **Marka keşfi** iş akışı bunu bulutta çalıştırır.

## Yerelde çalıştırmak (isteğe bağlı)

```bash
pip install -r requirements.txt
python cli.py tara --marka "Mondial"
python cli.py durum
python uret_index.py site/index.html
```
