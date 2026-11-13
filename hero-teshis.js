/* ============================================================
   HERO TEŞHİS  —  tek il çekip yanıtı olduğu gibi indirir
   ============================================================
   Konsola yapıştır, Enter. 2 saniyede "hero-teshis.html" iner.
   O dosyayı gönder; hangi yapıda geldiğini görüp ayrıştırıcıyı
   ona göre yazacağım.
   ============================================================ */

(async () => {
  const kok = location.origin;
  const sayfa = location.href.split('?')[0];

  // Denenecek yollar: sayfanın kendisi + ana sayfadaki ajax kalıpları
  const denemeler = [
    { ad: 'sayfaya POST (city_box)', url: sayfa,
      govde: { city_box: '10', ara: 'Ara' } },
    { ad: 'sayfaya POST (bayi_city_box)', url: sayfa,
      govde: { bayi_city_box: '10', ara: 'Ara' } },
    { ad: 'sayfaya POST (servis_city_box)', url: sayfa,
      govde: { servis_city_box: '10', ara: 'Ara' } },
  ];

  const parcalar = [];

  for (const d of denemeler) {
    try {
      const y = await fetch(d.url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded',
                   'X-Requested-With': 'XMLHttpRequest' },
        body: new URLSearchParams(d.govde).toString(),
        credentials: 'same-origin'
      });
      const t = await y.text();
      const telSayisi = (t.match(/tel:/g) || []).length;
      const telefonlar = (t.match(/0\s*\(?\d{3}\)?[\s\-\/]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}/g) || []).length;
      console.log(`${d.ad}: durum=${y.status} boyut=${t.length} ` +
                  `tel:link=${telSayisi} telefon=${telefonlar}`);
      parcalar.push(`\n\n===== ${d.ad} | durum ${y.status} | ` +
                    `boyut ${t.length} | tel:link ${telSayisi} | ` +
                    `telefon ${telefonlar} =====\n\n` + t);
    } catch (e) {
      console.warn(`${d.ad}: HATA ${e.message}`);
      parcalar.push(`\n\n===== ${d.ad} | HATA ${e.message} =====\n`);
    }
  }

  // Sayfanın kendi durumu da faydalı: seçici adları, düğme kimliği
  const seciciler = [...document.querySelectorAll('select')]
    .map(s => `select id="${s.id}" name="${s.name}" secenek=${s.options.length}`);
  const dugmeler = [...document.querySelectorAll('input[type=button],button')]
    .map(b => `${b.tagName} id="${b.id}" value="${b.value || b.textContent.trim()}"`);
  const kutular = [...document.querySelectorAll('[id*=content],[id*=sonuc]')]
    .map(e => `id="${e.id}" ic=${e.innerHTML.length}`);

  const bas = `SAYFA: ${location.href}\n\nSELECT'LER:\n${seciciler.join('\n')}\n\n` +
              `DÜĞMELER:\n${dugmeler.join('\n')}\n\nSONUÇ KUTULARI:\n${kutular.join('\n')}\n`;

  const b = new Blob([bas + parcalar.join('')], { type: 'text/plain' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(b);
  a.download = 'hero-teshis.html';
  document.body.appendChild(a); a.click(); a.remove();
  console.log('Teşhis dosyası indi: hero-teshis.html');
})();
