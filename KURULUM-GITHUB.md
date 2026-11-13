# GitHub Kurulumu

Bu kurulumdan sonra bilgisayarına hiçbir şey kurmayacaksın. GitHub'ın sunucusu
her gece markaları tarayacak, sonucu bir web adresine koyacak. Sen o adresi
tarayıcına yer imi ekleyip açacaksın.

**Ücretsiz.** Herkese açık depolarda GitHub Actions dakika sınırı yok.

---

## 1 · Hesap aç

[github.com/signup](https://github.com/signup) — e-posta, şifre, kullanıcı adı.
Ücretsiz plan yeterli.

## 2 · Depo oluştur

Sağ üstteki **+** → **New repository**

| Alan | Değer |
|---|---|
| Repository name | `motosiklet-bayileri` |
| Görünürlük | **Public** |

> **Neden Public?** İki sebep: Actions dakikaları herkese açık depolarda
> sınırsız, ve GitHub Pages ücretsiz planda sadece public depolardan yayın
> yapabiliyor. Buradaki veri zaten markaların kendi sitelerinde herkese açık
> olan bayi bilgisi.
>
> Depoyu gizli tutmak istersen: Pages çalışmaz, ama tarama çalışır ve sonucu
> Actions sekmesinden dosya olarak indirirsin. Bu durumda ayda 2000 dakika
> ücretsiz hakkın var — gecelik 1 saatlik tarama için yeterli.

**Create repository**'ye bas.

## 3 · Dosyaları yükle

Açılan sayfada **uploading an existing file** bağlantısına tıkla.

`bayi-radar-sistem` klasörünün **içindeki** her şeyi sürükle bırak:

```
bayiradar/          markalar.json       requirements.txt
.github/            brands.yaml         uret_index.py
cli.py              fixtures/
```

> `.github` klasörü gizli olduğu için Finder/Dosya Gezgini'nde görünmeyebilir.
> Windows: Görünüm → Gizli öğeler. Mac: `Cmd + Shift + .`
> Bu klasör olmazsa otomatik tarama çalışmaz.

Altta **Commit changes** butonuna bas.

## 4 · Actions'a yazma izni ver

**Settings** → sol menüden **Actions** → **General** → en alta in:

- **Workflow permissions** başlığında **Read and write permissions** seç
- **Save**

> Bu izin, taranan verinin depoya geri yazılabilmesi için gerekli. Olmazsa her
> gece sıfırdan başlar ve "eski veriyi koru" mantığı çalışmaz.

## 5 · Pages'i aç

**Settings** → sol menüden **Pages**

- **Source** kutusunda **GitHub Actions** seç

## 6 · İlk taramayı başlat

**Actions** sekmesi → soldan **Bayileri tara ve siteyi yayınla** → sağdaki
**Run workflow** → yeşil **Run workflow** butonu.

İlk tarama uzun sürer. Sayfayı yenileyip ilerlemeyi izleyebilirsin.

Bitince adresin hazır:

```
https://KULLANICI-ADIN.github.io/motosiklet-bayileri/
```

Bu adresi tarayıcına yer imi ekle. İşin bitti.

---

## Bundan sonrası

Her gece Türkiye saatiyle 03:00'te kendiliğinden tarar ve sayfayı günceller.
Sen sadece adresi açarsın.

**Elle tazelemek:** Actions → Run workflow.

**Tek markayı tazelemek:** Run workflow'a basınca çıkan kutuya marka adını yaz
(örnek: `Mondial`).

**Ne olduğunu görmek:** Actions sekmesinde her taramanın kaydı durur. Bir marka
hata verdiyse orada görürsün — ama sayfadaki verisi silinmez, sarı işaretle
"son doğrulanmış veri" olarak kalır.

---

## Marka tarifi eklemek

Şu an sadece Mondial taranıyor. Yeni marka eklemek için GitHub'da
`brands.yaml` dosyasını aç, kalem simgesine bas, o markanın bloğunu doldur ve
`pasif: true` satırını sil. Commit ettiğinde bir sonraki taramada devreye girer.

Tarifi nasıl yazacağını bilmiyorsan bana o markanın bayi sayfasından ne
gördüğünü söyle, ben yazayım.

---

## Takıldığın yer olursa

Actions sekmesinde kırmızı ✗ görürsen üzerine tıkla, hangi adımda durduğunu
gösterir. O ekranın metnini bana gönder.
