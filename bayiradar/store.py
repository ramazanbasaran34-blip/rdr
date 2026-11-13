"""SQLite deposu — veri koruma odaklı sürüm.

Temel ilke: BİR TARAMA ASLA VERİ SİLEMEZ.
Silme yetkisi yoktur; sadece "bu kaydı şu tarihten beri göremiyorum" diyebilir.

Üç katmanlı koruma:
  1. Kısmi tarama tespiti — 81 il sayfasının 60'ı geldiyse eksik kabul edilir,
     görülmeyen kayıtlara dokunulmaz.
  2. Anomali eşiği — kayıt sayısı bir önceki başarılı taramanın %60'ının altına
     düşerse marka karantinaya alınır, eski veri korunur, insan bakar.
  3. Kayıp sayacı — bir bayi tek taramada görünmedi diye düşmüş sayılmaz;
     üst üste 3 SAĞLIKLI taramada görünmezse "kaldırıldı" olur.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from .eslestir import ayni_firma_mi, eslesme_anahtarlari, rolleri_birlestir
from .normalize import fold

DB_PATH = "bayiler.db"

# Bir bayi kaç ardışık sağlıklı taramada görünmezse gerçekten düşmüş sayılır
KAYIP_ESIGI = 3
# Yeni sayı, son başarılı sayının bu oranının altındaysa karantina
ANOMALI_ORANI = 0.60
# Taranan URL'lerin en az bu oranı başarılı olmalı ki tarama "tam kapsamlı" sayılsın
KAPSAM_ORANI = 0.95

SCHEMA = """
CREATE TABLE IF NOT EXISTS bayiler (
    id           INTEGER PRIMARY KEY,
    marka        TEXT NOT NULL,
    bayi_adi     TEXT NOT NULL,
    il           TEXT,
    ilce         TEXT,
    adres        TEXT,
    telefon      TEXT,
    email        TEXT,
    website      TEXT,
    kaynak_url   TEXT,
    il_key       TEXT,
    ilce_key     TEXT,
    tekil_key    TEXT UNIQUE,
    ilk_gorulme  TEXT,
    son_gorulme  TEXT,
    durum        TEXT DEFAULT 'aktif',
    kayip_sayaci INTEGER DEFAULT 0,
    rol          TEXT DEFAULT 'satis',   -- satis | servis | satis_servis
    kaynak_satis  TEXT,                  -- satış listesinde göründüğü adres
    kaynak_servis TEXT                   -- servis listesinde göründüğü adres
);
CREATE INDEX IF NOT EXISTS ix_il    ON bayiler(il_key);
CREATE INDEX IF NOT EXISTS ix_ilce  ON bayiler(ilce_key);
CREATE INDEX IF NOT EXISTS ix_mrk   ON bayiler(marka);
CREATE INDEX IF NOT EXISTS ix_durum ON bayiler(durum);

CREATE TABLE IF NOT EXISTS marka_durum (
    marka             TEXT PRIMARY KEY,
    son_basarili      TEXT,
    son_basarili_adet INTEGER,
    son_deneme        TEXT,
    son_deneme_durum  TEXT,
    son_hata          TEXT,
    ardisik_hata      INTEGER DEFAULT 0,
    karantina         INTEGER DEFAULT 0,
    periyot_saat      REAL DEFAULT 24,
    bekleme           REAL
);

CREATE TABLE IF NOT EXISTS degisim_log (
    id       INTEGER PRIMARY KEY,
    tarih    TEXT,
    marka    TEXT,
    tip      TEXT,
    bayi_adi TEXT,
    il       TEXT,
    ilce     TEXT,
    detay    TEXT
);
CREATE INDEX IF NOT EXISTS ix_deg ON degisim_log(marka, tarih);

CREATE TABLE IF NOT EXISTS tarama_log (
    id         INTEGER PRIMARY KEY,
    marka      TEXT,
    baslangic  TEXT,
    bitis      TEXT,
    durum      TEXT,
    adet       INTEGER,
    beklenen   INTEGER,
    kapsam     REAL,
    mesaj      TEXT
);
"""


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# Şemaya sonradan eklenen sütunlar. CREATE TABLE IF NOT EXISTS mevcut tabloyu
# değiştirmediği için, yeni sütunlar burada tek tek eklenir. Eski veritabanı
# silinmeden yeni sürüme geçebilsin diye.
EK_SUTUNLAR = [
    ("rol", "TEXT DEFAULT 'satis'"),
    ("kaynak_satis", "TEXT"),
    ("kaynak_servis", "TEXT"),
]


def _goc(con):
    """Eksik sütunları ekler ve indeksleri kurar."""
    var = {r[1] for r in con.execute("PRAGMA table_info(bayiler)")}
    if not var:
        return          # tablo henüz yok, SCHEMA zaten kuracak
    for ad, tanim in EK_SUTUNLAR:
        if ad not in var:
            con.execute(f"ALTER TABLE bayiler ADD COLUMN {ad} {tanim}")
    con.execute("CREATE INDEX IF NOT EXISTS ix_rol ON bayiler(rol)")


@contextmanager
def db(path=DB_PATH):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    try:
        con.executescript(SCHEMA)
        _goc(con)
        con.commit()
        yield con
        con.commit()
    finally:
        con.close()


def tekil_key(rec: dict) -> str:
    """Kaydın benzersiz anahtarı.

    DİKKAT — telefona ilçe de girmek zorunda: aynı firmanın aynı ilde
    birden çok şubesi olabiliyor ve şubeler çoğu zaman AYNI merkezi
    numarayı paylaşıyor. Anahtar yalnızca marka+telefon olduğunda
    ikinci şube birinciyi eziyordu (Bajaj'da 98 satış noktasının 4'ü
    bu yüzden kayboluyordu: Hatay/Kenan Uslu, Mersin/Çetinkaya Moto,
    İstanbul/Mustafa Oktay, Denizli/Yiğitler).
    """
    marka = fold(rec["marka"])
    ilce = fold(rec.get("ilce", ""))
    if rec.get("telefon"):
        return f"{marka}|{rec['telefon']}|{ilce}"
    return f"{marka}|{fold(rec['bayi_adi'])}|{ilce}"


def _log_degisim(con, marka, tip, rec, detay=""):
    con.execute(
        "INSERT INTO degisim_log (tarih,marka,tip,bayi_adi,il,ilce,detay) "
        "VALUES (?,?,?,?,?,?,?)",
        (now(), marka, tip, rec.get("bayi_adi", ""), rec.get("il", ""),
         rec.get("ilce", ""), detay))


def marka_bilgi(con, marka) -> dict:
    r = con.execute("SELECT * FROM marka_durum WHERE marka=?", (marka,)).fetchone()
    return dict(r) if r else {}


# ============================================================================
#  TARAMA SONUCUNU İŞLE — tek giriş noktası
# ============================================================================
def commit_tarama(con, marka: str, kayitlar: list[dict], kapsam: float,
                  baslangic: str) -> dict:
    """Bir taramanın sonucunu değerlendirip işler.

    kapsam: başarıyla çekilen URL oranı (0-1). 81 il sayfasının 60'ı geldiyse
            0.74 gelir ve tarama "kısmi" sayılır — eksikler pasife çekilmez.

    Hiçbir dalda mevcut bir kayıt SİLİNMEZ.
    """
    t = now()
    onceki = marka_bilgi(con, marka)
    beklenen = onceki.get("son_basarili_adet") or 0
    adet = len(kayitlar)

    # 1. Hiç kayıt yok: seçici kırılmış ya da site kapalı. Veriye dokunma.
    if adet == 0:
        return _basarisiz(con, marka, baslangic, t, beklenen, kapsam,
                          "hiç kayıt çıkmadı — seçiciler kırılmış olabilir")

    # 2. Anomali: sayı çakılmış. Yeni veriyi al ama eskiyi düşürme.
    karantina = bool(beklenen and adet < beklenen * ANOMALI_ORANI)
    # 3. Kısmi kapsam: bazı sayfalar gelmedi. Görülmeyene dokunma.
    kismi = kapsam < KAPSAM_ORANI
    saglikli = not karantina and not kismi

    yeni, guncel, gorulen = _upsert(con, kayitlar, marka, t)

    supheli = 0
    if saglikli:
        supheli = _eksikleri_isaretle(con, marka, gorulen)
        con.execute("""
            INSERT INTO marka_durum (marka, son_basarili, son_basarili_adet,
                                     son_deneme, son_deneme_durum, son_hata,
                                     ardisik_hata, karantina)
            VALUES (?,?,?,?,'basarili','',0,0)
            ON CONFLICT(marka) DO UPDATE SET
                son_basarili=excluded.son_basarili,
                son_basarili_adet=excluded.son_basarili_adet,
                son_deneme=excluded.son_deneme,
                son_deneme_durum='basarili', son_hata='',
                ardisik_hata=0, karantina=0
        """, (marka, t, adet, t))
        durum, mesaj = "basarili", ""
    else:
        durum = "karantina" if karantina else "kismi"
        mesaj = (f"kayıt sayısı {beklenen} → {adet} düştü, karantinada"
                 if karantina else
                 f"sayfaların %{kapsam*100:.0f}'i çekilebildi, eksik tarama")
        con.execute("""
            INSERT INTO marka_durum (marka, son_deneme, son_deneme_durum,
                                     son_hata, ardisik_hata, karantina)
            VALUES (?,?,?,?,0,?)
            ON CONFLICT(marka) DO UPDATE SET
                son_deneme=excluded.son_deneme,
                son_deneme_durum=excluded.son_deneme_durum,
                son_hata=excluded.son_hata,
                karantina=excluded.karantina
        """, (marka, t, durum, mesaj, 1 if karantina else 0))

    con.execute(
        "INSERT INTO tarama_log (marka,baslangic,bitis,durum,adet,beklenen,kapsam,mesaj)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (marka, baslangic, t, durum, adet, beklenen, kapsam, mesaj))

    return {"durum": durum, "adet": adet, "yeni": yeni, "guncel": guncel,
            "supheli": supheli, "mesaj": mesaj}


def tarama_hatasi(con, marka: str, baslangic: str, hata: str) -> dict:
    """Site hiç açılmadı. Veriye kesinlikle dokunulmaz."""
    return _basarisiz(con, marka, baslangic, now(), 0, 0.0, hata)


def _basarisiz(con, marka, baslangic, t, beklenen, kapsam, mesaj):
    con.execute("""
        INSERT INTO marka_durum (marka, son_deneme, son_deneme_durum, son_hata, ardisik_hata)
        VALUES (?,?,'hatali',?,1)
        ON CONFLICT(marka) DO UPDATE SET
            son_deneme=excluded.son_deneme, son_deneme_durum='hatali',
            son_hata=excluded.son_hata, ardisik_hata=marka_durum.ardisik_hata+1
    """, (marka, t, mesaj[:400]))
    con.execute(
        "INSERT INTO tarama_log (marka,baslangic,bitis,durum,adet,beklenen,kapsam,mesaj)"
        " VALUES (?,?,?,'hatali',0,?,?,?)",
        (marka, baslangic, t, beklenen, kapsam, mesaj[:400]))
    return {"durum": "hatali", "adet": 0, "yeni": 0, "guncel": 0,
            "supheli": 0, "mesaj": mesaj}


def _ayni_firmayi_bul(con, rec, marka):
    """Aynı firmanın önceden kaydedilmiş halini arar.

    Telefon tutmayabilir (bayi sayfasında sabit hat, servis sayfasında cep).
    Bu yüzden aynı marka+il içindeki adayları çekip ad/adres benzerliğine
    bakıyoruz. Ayrıntı: bayiradar/eslestir.py
    """
    adaylar = con.execute(
        "SELECT * FROM bayiler WHERE marka=? AND il_key=?",
        (marka, fold(rec.get("il", "")))).fetchall()
    for a in adaylar:
        ok, _ = ayni_firma_mi(rec, dict(a))
        if ok:
            return a
    return None


def _upsert(con, kayitlar, marka, t):
    yeni = guncel = birlesen = 0
    gorulen = set()
    for rec in kayitlar:
        k = tekil_key(rec)
        gorulen.add(k)
        row = con.execute(
            "SELECT * FROM bayiler WHERE tekil_key=?", (k,)).fetchone()
        if not row:
            # Telefonla bulunamadı — ad/adres benzerliğiyle ara
            row = _ayni_firmayi_bul(con, rec, marka)
            if row:
                gorulen.add(row["tekil_key"])
                birlesen += 1
        vals = (rec["marka"], rec["bayi_adi"], rec["il"], rec["ilce"], rec["adres"],
                rec["telefon"], rec["email"], rec["website"], rec["kaynak_url"],
                fold(rec["il"]), fold(rec["ilce"]))
        rol = rec.get("rol", "satis")
        ks = rec.get("kaynak_url", "") if rol in ("satis", "satis_servis") else None
        kv = rec.get("kaynak_url", "") if rol in ("servis", "satis_servis") else None

        if row:
            if row["durum"] != "aktif":
                _log_degisim(con, marka, "geri_geldi", rec,
                             f"önceki durum: {row['durum']}")
            elif row["adres"] != rec["adres"] or row["telefon"] != rec["telefon"]:
                _log_degisim(con, marka, "guncellendi", rec, "adres/telefon değişti")
            yeni_rol = rolleri_birlestir(row["rol"] or "", rol)
            if yeni_rol != (row["rol"] or ""):
                _log_degisim(con, marka, "rol_degisti", rec,
                             f"{row['rol']} → {yeni_rol}")
            con.execute(
                """UPDATE bayiler SET marka=?,bayi_adi=?,il=?,ilce=?,adres=?,
                   telefon=?,email=?,website=?,kaynak_url=?,il_key=?,ilce_key=?,
                   son_gorulme=?, durum='aktif', kayip_sayaci=0, rol=?,
                   kaynak_satis=COALESCE(?,kaynak_satis),
                   kaynak_servis=COALESCE(?,kaynak_servis) WHERE id=?""",
                vals + (t, yeni_rol, ks, kv, row["id"]))
            guncel += 1
        else:
            con.execute(
                """INSERT INTO bayiler (marka,bayi_adi,il,ilce,adres,telefon,email,
                   website,kaynak_url,il_key,ilce_key,tekil_key,ilk_gorulme,
                   son_gorulme,durum,kayip_sayaci,rol,kaynak_satis,kaynak_servis)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,'aktif',0,?,?,?)""",
                vals + (k, t, t, rol, ks, kv))
            _log_degisim(con, marka, "eklendi", rec)
            yeni += 1
    return yeni, guncel, gorulen


def _eksikleri_isaretle(con, marka, gorulen: set) -> int:
    """Bu sağlıklı taramada GÖRÜLMEYEN kayıtların kayıp sayacını artırır.

    Zaman damgası karşılaştırması yerine açık küme kullanıyoruz; aynı saniye
    içinde çalışan taramalarda zaman karşılaştırması sessizce çalışmıyordu.
    Hiçbir kayıt SİLİNMEZ, sadece işaretlenir.
    """
    con.execute("CREATE TEMP TABLE IF NOT EXISTS _gorulen (k TEXT PRIMARY KEY)")
    con.execute("DELETE FROM _gorulen")
    con.executemany("INSERT OR IGNORE INTO _gorulen VALUES (?)",
                    [(k,) for k in gorulen])

    eksik = """marka=? AND durum!='kaldirildi'
               AND tekil_key NOT IN (SELECT k FROM _gorulen)"""
    con.execute(f"UPDATE bayiler SET kayip_sayaci = kayip_sayaci + 1, "
                f"durum='dogrulanamadi' WHERE {eksik}", (marka,))

    dusenler = con.execute(
        f"SELECT bayi_adi, il, ilce FROM bayiler WHERE {eksik} AND kayip_sayaci >= ?",
        (marka, KAYIP_ESIGI)).fetchall()
    for d in dusenler:
        _log_degisim(con, marka, "kaldirildi", dict(d),
                     f"{KAYIP_ESIGI} ardışık taramada görülmedi")
    con.execute(f"UPDATE bayiler SET durum='kaldirildi' "
                f"WHERE {eksik} AND kayip_sayaci >= ?", (marka, KAYIP_ESIGI))

    return con.execute(
        "SELECT COUNT(*) c FROM bayiler WHERE marka=? AND durum='dogrulanamadi'",
        (marka,)).fetchone()["c"]


# ============================================================================
#  SORGULAMA
# ============================================================================
def sorgula(con, il="", ilce="", markalar=None, kaldirilanlari_dahil_et=False):
    """Varsayılan: aktif + doğrulanamayan kayıtlar.

    'dogrulanamadi' olanlar GİZLENMEZ — gizlense kullanıcı "Pendik'te Honda
    bayisi yok" sanır. Listede kalır, tazelik etiketiyle işaretlenir.
    """
    durumlar = ["aktif", "dogrulanamadi"]
    if kaldirilanlari_dahil_et:
        durumlar.append("kaldirildi")
    q = f"""SELECT b.*, m.son_basarili, m.son_deneme_durum, m.karantina
            FROM bayiler b LEFT JOIN marka_durum m ON m.marka = b.marka
            WHERE b.durum IN ({','.join('?' * len(durumlar))})"""
    p = list(durumlar)
    if il:
        q += " AND b.il_key = ?"; p.append(fold(il))
    if ilce:
        q += " AND b.ilce_key LIKE ?"; p.append(f"%{fold(ilce)}%")
    if markalar:
        q += f" AND b.marka IN ({','.join('?' * len(markalar))})"; p += list(markalar)
    q += " ORDER BY b.marka, b.il, b.ilce, b.bayi_adi"

    out = []
    for r in con.execute(q, p).fetchall():
        d = dict(r)
        d["veri_durumu"] = tazelik_etiketi(d)
        out.append(d)
    return out


def tazelik_etiketi(rec: dict) -> str:
    """Kullanıcıya gösterilecek insan okunur veri durumu."""
    if rec.get("durum") == "kaldirildi":
        return "Bayilik düşmüş"
    if rec.get("durum") == "dogrulanamadi":
        return "Son taramada doğrulanamadı"
    if rec.get("karantina"):
        return "Karantina — son doğrulanmış veri"
    sb = rec.get("son_basarili")
    if not sb:
        # Hiç başarılı tarama olmamış: "Güncel" demek yanlış olur
        return ("Henüz taranamadı"
                if rec.get("son_deneme_durum") in ("hatali", "kismi", "karantina")
                else "Henüz taranmadı")
    yas = datetime.now(timezone.utc) - datetime.fromisoformat(sb)
    if rec.get("son_deneme_durum") in ("hatali", "kismi"):
        gun = yas.days
        return f"Son başarılı veri ({gun} gün önce)" if gun else "Son başarılı veri (bugün)"
    if yas > timedelta(days=7):
        return f"Eski ({yas.days} gün)"
    return "Güncel"


def marka_durumu(con) -> list[dict]:
    """Marka bazlı sağlık karnesi — arayüzdeki durum paneli bunu kullanır."""
    rows = con.execute("""
        SELECT m.marka,
               COALESCE(SUM(CASE WHEN b.durum='aktif' THEN 1 END), 0) aktif,
               COALESCE(SUM(CASE WHEN b.durum='dogrulanamadi' THEN 1 END), 0) supheli,
               COALESCE(SUM(CASE WHEN b.durum='kaldirildi' THEN 1 END), 0) dusen,
               m.son_basarili, m.son_deneme, m.son_deneme_durum,
               m.ardisik_hata, m.karantina, m.son_hata
        FROM marka_durum m LEFT JOIN bayiler b ON b.marka = m.marka
        GROUP BY m.marka ORDER BY m.marka
    """).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["toplam"] = d["aktif"] + d["supheli"]
        d["etiket"] = tazelik_etiketi({
            "son_basarili": d["son_basarili"],
            "son_deneme_durum": d["son_deneme_durum"],
            "karantina": d["karantina"], "durum": "aktif"})
        out.append(d)
    return out


def son_degisimler(con, limit=50, marka=None):
    q = "SELECT * FROM degisim_log"
    p = []
    if marka:
        q += " WHERE marka=?"; p.append(marka)
    q += " ORDER BY id DESC LIMIT ?"; p.append(limit)
    return [dict(r) for r in con.execute(q, p).fetchall()]
