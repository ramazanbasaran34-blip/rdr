/* ============================================================
   HERO TOPLAYICI  v2  —  Chrome konsoluna yapıştır
   ============================================================
   v1 neden çalışmadı: kayıtları <a href="tel:..."> bağlantısına
   göre arıyordu. Bu sayfada telefonlar DÜZ METİN olarak geliyor
   (teşhis: tel:link=1, telefon=7). Bu sürüm telefon numarasının
   kendisini çapa olarak kullanıyor, etiket yapısına bağımlı değil.

   KULLANIM
   1) https://www.heromotor.com.tr/bayiler/ aç (view-source DEĞİL)
   2) F12 → Console
   3) Gerekirse: allow pasting  yazıp Enter
   4) Bu dosyanın tamamını yapıştır, Enter
   5) 5-8 dk sonra hero-bayiler.json iner
   6) Aynısını /servisler/ için tekrarla
   ============================================================ */

(async () => {
  const TEL = /(?:\+90|0)\s*\(?\d{3}\)?[\s\-\/\.]*\d{3}[\s\-\/\.]*\d{2}[\s\-\/\.]*\d{2}/;
  const TEL_G = new RegExp(TEL.source, 'g');

  const rol = location.pathname.includes('servis') ? 'servis' : 'satis';
  const secici = document.querySelector('select[name=city_box], select#city_box');
  if (!secici) { console.error('city_box bulunamadı — doğru sayfada mısın?'); return; }

  const iller = [...secici.options]
    .map(o => [o.value, o.textContent.trim()])
    .filter(x => x[0] && x[0] !== '0');
  console.log(`${iller.length} il bulundu, başlıyorum...`);

  const bekle = ms => new Promise(r => setTimeout(r, ms));
  const kayitlar = [];

  // Bir kaydın kutusunu bulur: telefonu İÇEREN en küçük öğeden
  // yukarı çıkıp yeterince metin taşıyan atayı seçer.
  function kartlariBul(kok) {
    const kartlar = new Set();
    kok.querySelectorAll('*').forEach(e => {
      const t = (e.textContent || '').trim();
      if (!TEL.test(t)) return;
      // Telefonu içeren EN KÜÇÜK öğe olsun (çocukları da içeriyorsa atla)
      if ([...e.children].some(c => TEL.test(c.textContent || ''))) return;
      let kart = e;
      for (let k = 0; k < 6; k++) {
        if (!kart.parentElement || kart.parentElement === kok) break;
        kart = kart.parentElement;
        const uz = (kart.innerText || kart.textContent || '').trim().length;
        if (uz > 40) break;
      }
      kartlar.add(kart);
    });
    return [...kartlar];
  }

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

      const kutu = belge.querySelector('#dealer_content, #servis_content, ' +
                   '#bayi_content, #dealer_content_container') || belge.body;

      let n = 0;
      const gorulen = new Set();

      kartlariBul(kutu).forEach(kart => {
        const metin = (kart.textContent || '').replace(/\u00a0/g, ' ');
        const satirlar = metin.split('\n').map(s => s.replace(/\s+/g, ' ').trim())
                              .filter(Boolean);
        if (!satirlar.length) return;

        const tm = metin.match(TEL_G);
        if (!tm) return;
        const tel = tm[0].replace(/\s+/g, ' ').trim();

        // Ad: telefon ve adres olmayan ilk anlamlı satır
        let ad = '';
        for (const s of satirlar) {
          if (TEL.test(s)) continue;
          if (/mah\.|cad\.|sok|no:|blv|bulv/i.test(s)) continue;
          if (s.length < 3) continue;
          ad = s; break;
        }
        if (!ad) return;

        // Adres: en uzun, ad ve telefon olmayan satır
        let adres = '';
        for (const s of satirlar) {
          if (s === ad || TEL.test(s)) continue;
          if (s.length > adres.length) adres = s;
        }

        // Adres sonu "... EDREMİT / BALIKESİR" → ilçe
        let ilce = '';
        const m = adres.match(/([^\/,]{2,60})\s*\/\s*([^\/,]{2,30})\s*$/);
        if (m) {
          const kel = m[1].trim().split(/\s+/);
          for (const n2 of [1, 2]) {
            const aday = kel.slice(-n2).join(' ').trim();
            if (aday && !/\d|no:|mah\.|cad\.|sok|blv|bulv/i.test(aday)) {
              ilce = aday; break;
            }
          }
        }

        const anahtar = ad.toLocaleLowerCase('tr') + '|' + tel;
        if (gorulen.has(anahtar)) return;
        gorulen.add(anahtar);

        kayitlar.push({ marka: 'Hero', rol, bayi_adi: ad, il: ilAdi,
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
  document.body.appendChild(a); a.click(); a.remove();
  console.log(`BİTTİ — ${kayitlar.length} kayıt, dosya indi.`);
})();
