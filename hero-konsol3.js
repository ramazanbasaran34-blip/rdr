/* ============================================================
   HERO TOPLAYICI  v3  —  Chrome konsoluna yapıştır
   ============================================================
   Bu sürüm tahminle değil, sitenin GERÇEK yanıtı incelenerek
   yazıldı. Yapı şu:

     <div class="corpaorateOffice">
       <h2 id="centrename">MOTO KİNG</h2>
       <div id="dealer_content">
         <table>
           <tr><td><i>Adres :</i></td><td>... ALTIEYLÜL / BALIKESİR</td></tr>
           <tr><td><i>Telefon :</i></td><td>0553 245 8284</td></tr>

   Balıkesir'de 6 kayıt çıkarması beklenir.

   KULLANIM
   1) https://www.heromotor.com.tr/bayiler/ aç (view-source DEĞİL)
   2) F12 → Console →  gerekirse "allow pasting" yazıp Enter
   3) Bu dosyanın tamamını yapıştır, Enter
   4) 5-8 dk sonra hero-bayiler.json iner
   5) Aynısını /servisler/ sayfasında tekrarla
   ============================================================ */

(async () => {
  const rol = location.pathname.includes('servis') ? 'servis' : 'satis';
  const secici = document.querySelector('select[name=city_box], select#city_box');
  if (!secici) { console.error('city_box bulunamadı — doğru sayfada mısın?'); return; }

  const iller = [...secici.options]
    .map(o => [o.value, o.textContent.trim()])
    .filter(x => x[0] && x[0] !== '0');
  console.log(`${iller.length} il bulundu, başlıyorum...`);

  const bekle = ms => new Promise(r => setTimeout(r, ms));
  const duz = s => (s || '').replace(/\s+/g, ' ').trim();
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
      const belge = new DOMParser().parseFromString(await y.text(), 'text/html');

      // Her kayıt ayrı bir .corpaorateOffice bloğu
      const bloklar = belge.querySelectorAll('.corpaorateOffice');
      let n = 0;
      const gorulen = new Set();

      bloklar.forEach(b => {
        const bas = b.querySelector('h2, h3, #centrename');
        const ad = duz(bas && bas.textContent);
        if (!ad) return;

        // Tablo satırları: "Adres :" / "Telefon :" / "E-Posta :" ...
        const alan = {};
        b.querySelectorAll('tr').forEach(tr => {
          const td = tr.querySelectorAll('td');
          if (td.length < 2) return;
          const etiket = duz(td[0].textContent).replace(/:$/, '').trim()
                         .toLocaleLowerCase('tr');
          alan[etiket] = duz(td[1].textContent);
        });

        const tel = alan['telefon'] || alan['tel'] || '';
        const adres = alan['adres'] || '';
        const eposta = alan['e-posta'] || alan['eposta'] || alan['email'] || '';

        // Adres sonu "... EDREMİT / BALIKESİR" → ilçe
        let ilce = '';
        const m = adres.match(/([^\/,]{2,60})\s*\/\s*([^\/,]{2,30})\s*$/);
        if (m) {
          const kel = m[1].trim().split(/\s+/);
          for (const n2 of [1, 2]) {
            const aday = kel.slice(-n2).join(' ').trim();
            if (aday && !/\d|no:|mah\.|cad\.|sok|sk\.|blv|bulv|apt/i.test(aday)) {
              ilce = aday; break;
            }
          }
        }

        const anahtar = ad.toLocaleLowerCase('tr') + '|' + tel + '|' + adres;
        if (gorulen.has(anahtar)) return;
        gorulen.add(anahtar);

        kayitlar.push({ marka: 'Hero', rol, bayi_adi: ad, il: ilAdi,
                        ilce, adres, telefon: tel, email: eposta, website: '' });
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
  document.body.appendChild(a); a.click(); a.remove();
  console.log(`BİTTİ — ${kayitlar.length} kayıt, dosya indi.`);
})();
