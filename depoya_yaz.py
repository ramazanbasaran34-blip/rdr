#!/usr/bin/env python3
"""Bir dosyayı depoya yazar — ÜÇ YÖNTEMİ SIRAYLA DENER.

Tek yönteme güvenmek bu projede defalarca tıkandı:
  · git push  → checkout ayrık HEAD + rebase/merge zinciri kilitlendi
  · Contents API → 1 MB üstü dosyalarda GitHub bu ucu desteklemiyor
    ("Files larger than 1 MB must be uploaded using the Git Data API")
    ve bayiler_yeni.db ~25 MB.

Bu yüzden üç yol da burada. Hangisi tutarsa onunla devam ediyor,
hepsi başarısızsa hangisinin neden düştüğünü tek tek yazıyor.

    python depoya_yaz.py bayiler_yeni.db "Tarama sonucu"
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
REPO = os.environ.get("GITHUB_REPOSITORY", "")
DAL = os.environ.get("GITHUB_REF_NAME", "main")


def api(yontem: str, url: str, govde=None, ham=False):
    d = json.dumps(govde).encode() if govde else None
    r = urllib.request.Request(url, data=d, method=yontem)
    r.add_header("Authorization", f"Bearer {TOKEN}")
    r.add_header("Accept", "application/vnd.github+json")
    r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=300) as y:
        veri = y.read()
        return veri if ham else json.loads(veri or "{}")


# ---------------------------------------------------------------- 1
def yontem_git(yol: str, mesaj: str) -> tuple[bool, str]:
    """En basit yol: doğrudan dal üzerinde commit + push."""
    try:
        k = lambda *a: subprocess.run(a, capture_output=True, text=True)
        k("git", "config", "user.name", "bayi-radar-bot")
        k("git", "config", "user.email", "bot@users.noreply.github.com")
        import shutil
        yedek = yol + ".yedek"
        shutil.copy2(yol, yedek)
        k("git", "fetch", "origin", DAL)
        k("git", "checkout", "-B", DAL, f"origin/{DAL}")
        # checkout dosyayi origin surumuyle ezmis olabilir: yedegi geri koy
        shutil.copy2(yedek, yol)
        os.remove(yedek)
        k("git", "add", "-f", yol)
        if k("git", "diff", "--staged", "--quiet").returncode == 0:
            return True, "değişiklik yok"
        k("git", "commit", "-m", mesaj)
        p = k("git", "push", "origin", f"HEAD:{DAL}")
        if p.returncode == 0:
            return True, "git push"
        return False, (p.stderr or p.stdout)[:160]
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"


# ---------------------------------------------------------------- 2
def yontem_contents(yol: str, mesaj: str) -> tuple[bool, str]:
    """Contents API — küçük dosyalar için pratik."""
    url = f"https://api.github.com/repos/{REPO}/contents/{yol}"
    try:
        sha = None
        try:
            sha = api("GET", f"{url}?ref={DAL}").get("sha")
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
        govde = {"message": mesaj, "branch": DAL,
                 "content": base64.b64encode(open(yol, "rb").read()).decode()}
        if sha:
            govde["sha"] = sha
        c = api("PUT", url, govde)
        return True, "contents api " + (c.get("commit") or {}).get("sha", "")[:8]
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.read().decode('utf-8','replace')[:140]}"
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"


# ---------------------------------------------------------------- 3
def yontem_gitdata(yol: str, mesaj: str) -> tuple[bool, str]:
    """Git Data API — büyük dosyalar için GitHub'ın önerdiği yol.

    blob yükle → mevcut ağacı baz alıp yeni ağaç → commit → dalı ilerlet
    """
    kok = f"https://api.github.com/repos/{REPO}/git"
    try:
        ref = api("GET", f"{kok}/ref/heads/{DAL}")
        tepe = ref["object"]["sha"]
        eski_commit = api("GET", f"{kok}/commits/{tepe}")

        blob = api("POST", f"{kok}/blobs", {
            "content": base64.b64encode(open(yol, "rb").read()).decode(),
            "encoding": "base64"})

        agac = api("POST", f"{kok}/trees", {
            "base_tree": eski_commit["tree"]["sha"],
            "tree": [{"path": yol, "mode": "100644", "type": "blob",
                      "sha": blob["sha"]}]})

        commit = api("POST", f"{kok}/commits", {
            "message": mesaj, "tree": agac["sha"], "parents": [tepe]})

        api("PATCH", f"{kok}/refs/heads/{DAL}",
            {"sha": commit["sha"], "force": False})
        return True, "git data api " + commit["sha"][:8]
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.read().decode('utf-8','replace')[:140]}"
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"


def yerel_blob_sha(yol: str) -> str:
    import hashlib
    d = open(yol, "rb").read()
    return hashlib.sha1(b"blob %d\0" % len(d) + d).hexdigest()


def uzak_blob_sha(yol: str) -> str:
    """Daldaki dosyanin git blob sha'si. Yazmanin gercekten olup olmadigini
    'basarili' dedigine bakarak degil, uzaktan okuyarak dogruluyoruz."""
    try:
        t = api("GET", f"https://api.github.com/repos/{REPO}/git/trees/{DAL}")
        for e in t.get("tree", []):
            if e["path"] == yol:
                return e["sha"]
    except Exception as e:  # noqa: BLE001
        return f"HATA:{type(e).__name__}"
    return "YOK"


def not_dus(msg: str) -> None:
    """::notice:: satiri is uyarilarina dusuyor; gunluge erisemedigimizde
    tek okunabilir kanal bu."""
    print(f"::notice::[yazma] {msg}")


def main() -> int:
    if len(sys.argv) < 2:
        print("kullanım: depoya_yaz.py <dosya> [mesaj]")
        return 1
    yol = sys.argv[1]
    mesaj = (sys.argv[2] if len(sys.argv) > 2 else "güncelleme")
    mesaj += ": " + time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())

    if not TOKEN or not REPO:
        print("::error::GH_TOKEN / GITHUB_REPOSITORY yok")
        return 1
    if not os.path.exists(yol) or os.path.getsize(yol) == 0:
        print(f"::error::{yol} yok veya boş")
        return 1

    mb = os.path.getsize(yol) / 1024 / 1024
    print(f"yazılacak: {yol} ({mb:.1f} MB) -> {DAL}")

    # Büyük dosyada Git Data API önce denenir; küçükte Contents daha hızlı.
    sira = ([yontem_gitdata, yontem_git, yontem_contents] if mb > 1
            else [yontem_contents, yontem_gitdata, yontem_git])

    hedef = yerel_blob_sha(yol)
    not_dus(f"{yol} {mb:.1f} MB, hedef blob {hedef[:8]}, "
            f"uzakta su an {uzak_blob_sha(yol)[:8]}")

    raporlar = []
    for tur in range(1, 3):                 # her yöntem için 2 tur
        for f in sira:
            ok, mesaj_sonuc = f(yol, mesaj)
            etiket = f.__name__.replace("yontem_", "")
            if ok:
                # "basarili" demesi yetmez: uzakta gercekten duruyor mu?
                time.sleep(3)
                simdi = uzak_blob_sha(yol)
                if simdi == hedef:
                    not_dus(f"{etiket} DOGRULANDI: {mesaj_sonuc}")
                    print(f"✓ BAŞARILI ({etiket}): {mesaj_sonuc}")
                    return 0
                mesaj_sonuc = (f"'{mesaj_sonuc}' dedi ama uzakta {simdi[:8]} "
                               f"duruyor, olmasi gereken {hedef[:8]}")
                ok = False
            raporlar.append(f"{etiket} (tur {tur}): {mesaj_sonuc}")
            not_dus(f"× {etiket} tur{tur}: {mesaj_sonuc}")
            print(f"  × {etiket}: {mesaj_sonuc}")
        time.sleep(8)

    print("::error::Hicbir yontem yazamadi -- " + " | ".join(raporlar)[:800])
    return 1


if __name__ == "__main__":
    sys.exit(main())
