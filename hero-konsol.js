/* ============================================================
   HERO BAYİ / SERVİS TOPLAYICI  —  Chrome konsoluna yapıştır
   ============================================================

   NASIL KULLANILIR
   1) Chrome'da şu adresi aç:  https://www.heromotor.com.tr/bayiler/
      (sayfa tam açılsın, Cloudflare doğrulaması geçsin)
   2) F12'ye bas → üstteki "Console" sekmesine geç
   3) Konsol ilk kez açılıyorsa "Allow pasting" yazmanı isteyebilir;
      istersen o yazıyı yaz ve Enter'a bas
   4) Bu dosyanın TAMAMINI kopyala, konsola yapıştır, Enter
   5) Alt satırda "[12/81] Ankara: 9 kayıt" gibi satırlar akacak.
      5-8 dakika sürer. Bitince hero-bayiler.json kendiliğinden iner.
   6) Aynısını https://www.heromotor.com.tr/servisler/ sayfasında
      tekrarla → hero-servisler.json iner.
   7) İki dosyayı gönder.

   NE YAPIYOR
   Sitenin kendi arama formunu, senin kendi oturumunda, il il
   kullanıyor. Hiçbir doğrulama atlatmıyor, sahte bilgi göndermiyor.
   İstekler arası 1.5-3 saniye bekliyor ki siteye yük binmesin.
   ============================================================ */

(async () => {
  const rol = location.pathname.includes('servis') ? 'servis' : 'satis';
  const iller = [...document.querySelectorAll('select[name=city_box] option')]
    .map(o => [o.value, o.textContent.trim()])
    .filter(x => x[0] && x[0] !== '0');

  if (!iller.length) {
    console.error('İl listesi bulunamadı. Doğru sayfada mısın? ' +
                  '/bayiler/ veya /servisler/ açık olmalı.');
    return;
  }
  console.log(`${iller.length} il bulundu, başlıyorum...`);

  const bekle = ms => new Promise(r => setTimeout(r, ms));
  const TEL = /^[\d\s()+\-]+$/;
  const kayitlar = [];

  for (let i = 0; i < iller.length; i++) {
    const [kod, ilAdi] = iller[i];
    try {
      const y = await fetch(location.href.split('?')[0], {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ city_box: kod, ara: 'Ara' }).toString(),
        credentials: 'same-origin'
      });
      const d = new DOMParser().parseFromString(await y.text(), 'text/html');

      let n = 0;
      const gorulen = new Set();

      d.querySelectorAll("a[href^='tel:']").forEach(a => {
        const tel = a.getAttribute('href').slice(4).trim();
        if (!tel) return;

        // Kaydın kutusu: telefon bağlantısının yeterince metin taşıyan atası
        let kutu = a;
        for (let k = 0; k < 5; k++) {
          kutu = kutu.parentElement;
          if (!kutu) break;
          if (kutu.innerText.trim().split(/\s+/).length > 8) break;
        }
        if (!kutu) return;

        const bas = kutu.querySelector('h1,h2,h3,h4,h5,h6,strong,b');
        const isim = bas ? bas.innerText.replace(/\s+/g, ' ').trim() : '';
        if (!isim || TEL.test(isim)) return;

        let adres = '';
        kutu.querySelectorAll('p,span,td,div').forEach(e => {
          const t = e.innerText.replace(/\s+/g, ' ').trim();
          if (t && t !== isim && !TEL.test(t) && t.length > adres.length) adres = t;
        });

        // Adres sonu "... EDREMİT / BALIKESİR" → ilçe
        let ilce = '';
        const m = adres.match(/([^/,]{2,60})\s*\/\s*([^/,]{2,30})\s*$/);
        if (m) {
          const kel = m[1].trim().split(/\s+/);
          for (const n2 of [1, 2]) {
            const aday = kel.slice(-n2).join(' ').trim();
            if (aday && !/\d|no:|mah\.|cad\.|sok|blv|bulv/i.test(aday)) {
              ilce = aday; break;
            }
          }
        }

        const anahtar = isim.toLocaleLowerCase('tr') + '|' + tel;
        if (gorulen.has(anahtar)) return;
        gorulen.add(anahtar);

        kayitlar.push({ marka: 'Hero', rol, bayi_adi: isim, il: ilAdi,
                        ilce, adres, telefon: tel, email: '', website: '' });
        n++;
      });
      console.log(`[${i + 1}/${iller.length}] ${ilAdi}: ${n} kayıt`);
    } catch (e) {
      console.warn(`[${i + 1}/${iller.length}] ${ilAdi}: HATA ${e.message}`);
    }
    await bekle(1500 + Math.random() * 1500);
  }

  const veri = {
    _aciklama: 'Hero Türkiye — sitenin kendi arama formuyla, kullanıcının ' +
               'kendi tarayıcı oturumundan toplandı.',
    _kaynak: [location.href.split('?')[0]],
    _tarih: new Date().toISOString().slice(0, 10),
    _duzenlenebilir: true,
    kayitlar
  };

  const b = new Blob([JSON.stringify(veri, null, 1)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(b);
  a.download = rol === 'servis' ? 'hero-servisler.json' : 'hero-bayiler.json';
  document.body.appendChild(a);
  a.click();
  a.remove();
  console.log(`BİTTİ — ${kayitlar.length} kayıt, dosya indi.`);
})();
