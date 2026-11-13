"""Marka başına özel toplayıcılar.

Her sitenin altyapısı farklı; tek bir otomatik çözücü hepsini tanıyamıyor.
Bu paketteki her modül TEK bir markadan sorumlu ve şu sözleşmeye uyar:

    KAYNAKLAR : {rol: url}          — canlı adresler
    TEST      : {(marka, rol): ad}  — ham/<ad>.gz test dosyaları
    coz(rol, govde, url) -> list[dict]   — ham gövdeden kayıt listesi

Böylece bir markayı düzeltmek ötekini bozmuyor ve her biri kaydedilmiş
sayfa üzerinde ağ olmadan test edilebiliyor.
"""
