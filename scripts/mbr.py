#!/usr/bin/env python3
"""mbr-anbernic: copertine, elenco giochi e pulizia della lista ROM per muOS.

Sicuro per default: hide, restore e install-covers simulano soltanto, a meno
di --apply. Nessun file viene cancellato: i giochi nascosti vengono spostati
in ROMS_HIDDEN, sulla stessa scheda, e restore li rimette dove erano.
"""
import argparse
import io
import json
import os
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SONGS_FILE = ROOT / "data" / "songs.json"
MUOS_FILE = ROOT / "data" / "muos.json"
BUILD = ROOT / "build"
HIDDEN_DIR = "ROMS_HIDDEN"
MANIFEST = ".mbr-hidden.json"
DEFAULT_SD = os.environ.get("MBR_SD", "/run/media/deck/MustardOS")
UA = {"User-Agent": "mbr-anbernic/0.1"}
BG = (0, 0, 0)  # sfondo delle copertine, come il tema (bianco su nero)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def songs():
    return load_json(SONGS_FILE)["songs"]


def kept():
    return [s for s in songs() if s.get("rom")]


def rel_of(song):
    return "%s/%s" % (song["rom"]["system"], song["rom"]["file"])


def keep_paths():
    return {rel_of(s) for s in kept()}


def rom_root(sd):
    root = Path(sd) / "ROMS"
    if not root.is_dir():
        sys.exit("Cartella ROMS non trovata in %s (usa --sd o la variabile MBR_SD)" % sd)
    return root


def iter_files(root):
    for p in sorted(root.rglob("*")):
        if p.is_file() and not p.name.startswith("."):
            yield p


def load_manifest(hidden_root):
    f = hidden_root / MANIFEST
    return load_json(f) if f.is_file() else []


def save_manifest(hidden_root, items):
    hidden_root.mkdir(parents=True, exist_ok=True)
    (hidden_root / MANIFEST).write_text(
        json.dumps(sorted(set(items)), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- list / check

def cmd_list(a):
    n_keep = 0
    for s in songs():
        if s.get("rom"):
            n_keep += 1
            flag = " (abbinamento incerto)" if s.get("match") == "loose" else ""
            print("%2d  %-40s -> %s%s" % (s["n"], s["title"], rel_of(s), flag))
        else:
            print("%2d  %-40s -> nessun gioco" % (s["n"], s["title"]))
    print("\n%d brani con gioco, %d senza" % (n_keep, len(songs()) - n_keep))
    return 0


def cmd_check(a):
    root = rom_root(a.sd)
    bad = 0
    for s in kept():
        rel = rel_of(s)
        if (root / rel).is_file():
            continue
        bad += 1
        folder = root / s["rom"]["system"]
        near = []
        if folder.is_dir():
            want = s["rom"]["file"].lower()
            near = [p.name for p in folder.iterdir() if p.name.lower() == want]
        print("MANCA  %s%s" % (rel, ("  (stesso nome con maiuscole diverse: %s)" % near[0]) if near else ""))
    print("%d/%d giochi trovati" % (len(kept()) - bad, len(kept())))
    return 1 if bad else 0


# ------------------------------------------------------------------ inspect

def tree(path, depth, maxdepth, out, limit=40):
    try:
        entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except OSError as e:
        out.append("%s[errore: %s]" % ("  " * depth, e))
        return
    for p in entries[:limit]:
        out.append("%s%s%s" % ("  " * depth, p.name, "/" if p.is_dir() else ""))
        if p.is_dir() and depth + 1 < maxdepth:
            tree(p, depth + 1, maxdepth, out, limit)
    if len(entries) > limit:
        out.append("%s... altri %d elementi" % ("  " * depth, len(entries) - limit))


def cmd_inspect(a):
    sd = Path(a.sd)
    if not sd.is_dir():
        sys.exit("Scheda non trovata in %s" % sd)
    out = ["# Radice della scheda: %s" % sd]
    tree(sd, 0, 1, out, limit=80)
    muos = sd / "MUOS"
    if muos.is_dir():
        out += ["", "# MUOS (profondita' 3)"]
        tree(muos, 0, 3, out)
    else:
        out += ["", "# Cartella MUOS non trovata nella radice"]
    roms = sd / "ROMS"
    if roms.is_dir():
        out += ["", "# ROMS: file per sistema"]
        for d in sorted(p for p in roms.iterdir() if p.is_dir()):
            out.append("%-12s %d" % (d.name, sum(1 for _ in iter_files(d))))
    text = "\n".join(out) + "\n"
    BUILD.mkdir(exist_ok=True)
    (BUILD / "inspect.txt").write_text(text, encoding="utf-8")
    print(text)
    print("Salvato in %s: incollalo a Claude per aggiornare data/muos.json" % (BUILD / "inspect.txt"))
    return 0


# ---------------------------------------------------------------- hide / restore

def cmd_hide(a):
    sd = Path(a.sd)
    root = rom_root(sd)
    hidden_root = sd / HIDDEN_DIR
    keep = keep_paths()
    present = {p.relative_to(root).as_posix() for p in iter_files(root)}
    missing = sorted(keep - present)
    if missing and not a.allow_missing:
        print("Mancano %d giochi da tenere, non nascondo nulla:" % len(missing))
        for m in missing:
            print("  " + m)
        print("Correggi data/songs.json oppure usa --allow-missing.")
        return 2
    to_move = sorted(present - keep)
    per_system = {}
    for rel in to_move:
        per_system[rel.split("/")[0]] = per_system.get(rel.split("/")[0], 0) + 1
    print("Restano visibili: %d giochi" % len(keep & present))
    print("Da nascondere (spostati in %s): %d file" % (HIDDEN_DIR, len(to_move)))
    for system, n in sorted(per_system.items()):
        print("  %-12s %d" % (system, n))
    if not a.apply:
        print("\nSimulazione: non e' stato spostato nulla. Aggiungi --apply per eseguire.")
        return 0
    if hidden_root.exists() and hidden_root.stat().st_dev != root.stat().st_dev:
        sys.exit("ROMS_HIDDEN e ROMS sono su dischi diversi: spostamento annullato.")
    if sd.stat().st_dev != root.stat().st_dev:
        sys.exit("ROMS e' su un disco diverso dalla radice: spostamento annullato.")
    manifest = load_manifest(hidden_root)
    moved = 0
    try:
        for rel in to_move:
            src, dst = root / rel, hidden_root / rel
            if dst.exists():
                print("SALTATO (esiste gia' in ROMS_HIDDEN): " + rel)
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            manifest.append(rel)
            moved += 1
    finally:
        save_manifest(hidden_root, manifest)
    print("Spostati %d file. Per ripristinare: python3 scripts/mbr.py restore --apply" % moved)
    return 0


def cmd_restore(a):
    sd = Path(a.sd)
    root = rom_root(sd)
    hidden_root = sd / HIDDEN_DIR
    manifest = load_manifest(hidden_root)
    if not manifest:
        print("Niente da ripristinare.")
        return 0
    todo = []
    for rel in manifest:
        src, dst = hidden_root / rel, root / rel
        if not src.is_file():
            print("NON TROVATO in ROMS_HIDDEN (lo tolgo dall'elenco): " + rel)
        elif dst.exists():
            print("CONFLITTO (esiste gia' in ROMS, lo lascio dov'e'): " + rel)
            todo.append((rel, None))
        else:
            todo.append((rel, (src, dst)))
    movable = [t for t in todo if t[1]]
    print("Da ripristinare: %d file" % len(movable))
    if not a.apply:
        print("Simulazione: non e' stato spostato nulla. Aggiungi --apply per eseguire.")
        return 0
    remaining = [rel for rel, mv in todo if mv is None]
    for rel, mv in todo:
        if mv:
            mv[1].parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(mv[0]), str(mv[1]))
    save_manifest(hidden_root, remaining)
    for d in sorted((p for p in hidden_root.rglob("*") if p.is_dir()), reverse=True):
        try:
            d.rmdir()  # solo cartelle vuote: fallisce se contengono file
        except OSError:
            pass
    print("Ripristinati %d file." % len(movable))
    return 0


# ---------------------------------------------------------------------- covers

def fetch(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def thumbnail(video_id):
    cache = BUILD / "thumbs" / (video_id + ".jpg")
    if cache.is_file():
        return cache.read_bytes()
    for name in ("maxresdefault", "hqdefault"):
        data = fetch("https://i.ytimg.com/vi/%s/%s.jpg" % (video_id, name))
        if data:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_bytes(data)
            return data
    return None


def cmd_covers(a):
    try:
        from PIL import Image, ImageOps
    except ImportError:
        sys.exit("Serve Pillow: pip install --user pillow")
    try:
        w, h = (int(x) for x in a.size.lower().split("x"))
    except ValueError:
        sys.exit("--size deve essere del tipo 640x480")
    resample = getattr(Image, "Resampling", Image).LANCZOS
    out = Path(a.out)
    done = 0
    for s in songs():
        if a.only_kept and not s.get("rom"):
            continue
        data = thumbnail(s["video_id"])
        if not data:
            print("Miniatura non disponibile: %s (%s)" % (s["title"], s["video_id"]))
            continue
        im = Image.open(io.BytesIO(data)).convert("RGB")
        if a.fit == "cover":
            im = ImageOps.fit(im, (w, h), resample, centering=(0.5, 0.5))
        else:
            im = ImageOps.contain(im, (w, h), resample)
            canvas = Image.new("RGB", (w, h), BG)
            canvas.paste(im, ((w - im.width) // 2, (h - im.height) // 2))
            im = canvas
        targets = []
        if s.get("rom"):
            targets.append(out / s["rom"]["system"] / (Path(s["rom"]["file"]).stem + ".png"))
        targets.append(out / "by-song" / ("%02d.png" % s["n"]))
        for t in targets:
            t.parent.mkdir(parents=True, exist_ok=True)
            im.save(t, "PNG")
        done += 1
        print("%2d  %s" % (s["n"], s["title"]))
    print("\n%d copertine in %s (%dx%d, %s)" % (done, out, w, h, a.fit))
    return 0


def cmd_install_covers(a):
    sd = Path(a.sd)
    muos = load_json(MUOS_FILE)
    if not muos.get("_verified"):
        print("ATTENZIONE: data/muos.json non e' verificato. Lancia prima 'inspect'.\n")
    src_root = Path(a.covers)
    cat = sd / muos["catalogue_root"]
    copied = skipped = 0
    for system, cat_name in muos["systems"].items():
        folder = src_root / system
        if not folder.is_dir():
            continue
        dest = cat / cat_name / muos["box_dir"]
        if not dest.is_dir() and not a.create:
            print("Cartella assente, salto %s: %s (usa --create per crearla)" % (system, dest))
            skipped += len(list(folder.glob("*.png")))
            continue
        for png in sorted(folder.glob("*.png")):
            print("%s -> %s" % (png.name, dest))
            if a.apply:
                dest.mkdir(parents=True, exist_ok=True)
                shutil.copy2(png, dest / png.name)
            copied += 1
    print("\n%s %d copertine, %d saltate" % ("Copiate" if a.apply else "Da copiare", copied, skipped))
    if not a.apply:
        print("Simulazione: aggiungi --apply per copiare.")
    return 0


# ------------------------------------------------------------------- theme-dump

TEXT_EXT = {".ini", ".txt", ".json", ".cfg", ".sh", ".md", ".html", ".xml"}
IMG_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".gif"}


def image_size(path):
    try:
        from PIL import Image
        with Image.open(path) as im:
            return "%dx%d" % im.size
    except Exception:
        return None


def cmd_theme_dump(a):
    sd = Path(a.sd)
    base = sd / "MUOS" / "theme"
    if not base.is_dir():
        sys.exit("Cartella dei temi non trovata: %s" % base)
    themes = sorted(p.name for p in base.iterdir() if p.is_dir())
    if a.name not in themes:
        print("Temi disponibili:\n  " + "\n  ".join(themes))
        return 2 if a.name else 0
    theme = base / a.name
    budget = a.max_kb * 1024
    files = [p for p in sorted(theme.rglob("*")) if p.is_file()]
    out = ["# Tema %s: %d file" % (a.name, len(files))]
    for p in files:
        out.append("%8d  %s" % (p.stat().st_size, p.relative_to(theme).as_posix()))
    out += ["", "# Contenuto dei file di testo (max 20 KB ciascuno)"]
    for p in files:
        if p.suffix.lower() in TEXT_EXT and p.stat().st_size <= 20000 and budget > 0:
            text = p.read_text(encoding="utf-8", errors="replace")
            budget -= len(text)
            out += ["=== %s ===" % p.relative_to(theme).as_posix(), text.rstrip(), ""]
    out += ["# Immagini (dimensioni) e altri file (primi 16 byte in esadecimale)"]
    for p in files:
        rel = p.relative_to(theme).as_posix()
        ext = p.suffix.lower()
        if ext in IMG_EXT:
            out.append("%-10s %s" % (image_size(p) or "?", rel))
        elif ext not in TEXT_EXT:
            with open(p, "rb") as f:
                out.append("%s  %s" % (f.read(16).hex(), rel))
    muos = load_json(MUOS_FILE)
    out += ["", "# Copertine gia' presenti nel catalogo (prime 3 per sistema)"]
    for system, cat_name in muos["systems"].items():
        box = sd / muos["catalogue_root"] / cat_name / muos["box_dir"]
        pngs = sorted(box.glob("*.png")) if box.is_dir() else []
        out.append("%s (%d file)" % (cat_name, len(pngs)))
        for p in pngs[:3]:
            out.append("  %-10s %s" % (image_size(p) or "?", p.name))
    for name in ("global.json", "folder.json", "tag.txt"):
        p = sd / "MUOS" / "info" / "name" / name
        if p.is_file():
            out += ["", "# MUOS/info/name/%s (primi 3000 caratteri)" % name,
                    p.read_text(encoding="utf-8", errors="replace")[:3000]]
    music = sd / "MUOS" / "music"
    if music.is_dir():
        out += ["", "# MUOS/music"]
        out += ["%8d  %s" % (p.stat().st_size, p.name) for p in sorted(music.iterdir()) if p.is_file()]
    text = "\n".join(out) + "\n"
    BUILD.mkdir(exist_ok=True)
    dest = BUILD / "theme-dump.txt"
    dest.write_text(text, encoding="utf-8")
    print("Salvato in %s (%d righe, %d KB)" % (dest, len(out), len(text) // 1024))
    return 0


# ---------------------------------------------------------- install-theme / names

def cmd_install_theme(a):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import build_theme
    font = Path(a.font)
    if not font.is_file():
        sys.exit("Font non trovato: %s (scaricalo da https://mbrserver.com/topaz.ttf o usa --font)" % font)
    sd = Path(a.sd)
    base = sd / "MUOS" / "theme" / a.base if a.base else None
    out = BUILD / "theme"
    theme = build_theme.build(font, out, a.name, base_theme=base, logo=a.logo, outro=OUTRO_FILE)
    print("Tema generato in %s" % theme)
    dest = sd / "MUOS" / "theme" / a.name
    if not a.apply:
        print("Simulazione: andrebbe copiato in %s. Aggiungi --apply." % dest)
        return 0
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(theme, dest)
    print("Installato in %s. Su muOS: Configuration > Customisation > Theme > %s" % (dest, a.name))
    return 0


def cmd_install_names(a):
    sd = Path(a.sd)
    path = sd / "MUOS" / "info" / "name" / "global.json"
    names = {Path(s["rom"]["file"]).stem: s["title"].upper() for s in kept()}
    data = {}
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
    new = {k: v for k, v in names.items() if data.get(k) != v}
    for k, v in new.items():
        print("%s -> %s" % (k, v))
    print("\n%d nomi da scrivere in %s" % (len(new), path))
    if not a.apply:
        print("Simulazione: aggiungi --apply.")
        return 0
    if path.is_file():
        if not Path(str(path) + ".bak").exists():  # tiene la copia dell'originale, non delle versioni successive
            shutil.copy2(path, str(path) + ".bak")
    path.parent.mkdir(parents=True, exist_ok=True)
    data.update(names)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Fatto (copia di sicurezza: global.json.bak)")
    return 0


# ------------------------------------------------------------------ file dei brani

def media_files(folder):
    """{video_id: file}. Riconosce "... [video_id].ext" (download da YouTube) e "NN - Titolo.ext"
    (numero del brano nella playlist). Se ci sono tutti e due, vince il primo."""
    import re
    by_n = {s["n"]: s["video_id"] for s in songs()}
    found = {}
    for f in sorted(Path(folder).expanduser().iterdir()):
        if not f.is_file():
            continue
        m = re.search(r"\[([A-Za-z0-9_-]{11})\]\.[^.]+$", f.name)
        if m:
            found.setdefault(m.group(1), f)
            continue
        m = re.match(r"(\d{1,2})\s*-\s", f.name)
        if m and int(m.group(1)) in by_n:
            found.setdefault(by_n[int(m.group(1))], f)
    return found


# ------------------------------------------------------------------ install-logo

LOGO_FILE = BUILD / "logo.png"          # copia del logo scelto, riusata da install-theme
OUTRO_FILE = BUILD / "logo_outro.png"   # logo di spegnimento/riavvio
SAVER_FILE = BUILD / "screensaver.png"  # logo che rimbalza nel salvaschermo DVD
DEFAULT_BOOT = os.environ.get("MBR_BOOT", "/run/media/deck/BOOT")


def cmd_install_logo(a):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import build_theme
    src = Path(a.image).expanduser()
    if not src.is_file():
        sys.exit("Immagine non trovata: %s" % src)
    sd, boot = Path(a.sd), Path(a.boot)
    res = "%dx%d" % (build_theme.W, build_theme.H)
    logo = build_theme.logo_screen(src)
    outro_src = Path(a.outro).expanduser() if a.outro else src
    if not outro_src.is_file():
        sys.exit("Immagine non trovata: %s" % outro_src)
    outro = build_theme.logo_screen(outro_src)
    targets = []
    for base in (BUILD / "theme" / a.theme, sd / "MUOS" / "theme" / a.theme):
        # bootlogo all'accensione; shutdown/reboot li mostra musplash allo spegnimento e al riavvio
        targets += [base / res / "image" / n for n in ("bootlogo.bmp", "shutdown.png", "reboot.png")]
    if boot.is_dir():
        targets += [boot / "bootlogo.bmp", boot / "bat" / "battery_charge.bmp"]
    else:
        print("Partizione di avvio non montata (%s): aggiorno solo il tema." % boot)
        print("muOS la aggiorna da solo quando riattivi il tema.")
    for t in targets:
        print("logo -> %s" % t)
    if not a.apply:
        print("\nSimulazione: aggiungi --apply.")
        return 0
    logo.save(LOGO_FILE)
    outro.save(OUTRO_FILE)
    saver = build_theme.saver_image(src)
    saver.save(SAVER_FILE)
    for base in (BUILD / "theme" / a.theme, sd / "MUOS" / "theme" / a.theme):
        if base.is_dir():
            saver.save(base / res / "image" / "screensaver.png")
            print("salvaschermo -> %s" % (base / res / "image" / "screensaver.png"))
    backup = BUILD / "boot-backup"
    for t in targets:
        if t.parent.parent.parent.is_dir() or t.is_relative_to(boot):
            t.parent.mkdir(parents=True, exist_ok=True)
            if t.is_relative_to(boot) and t.is_file():
                b = backup / t.relative_to(boot)
                if not b.exists():  # salva solo l'originale, non le versioni successive
                    b.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(t, b)
            img = outro if t.name in ("shutdown.png", "reboot.png") else logo
            img.save(t, format="BMP" if t.suffix == ".bmp" else "PNG")
    os.sync()
    print("\nFatto. Originali della partizione di avvio in %s" % backup)
    return 0


# ----------------------------------------------------------------- install-kiosk

ROM_MOUNT = "/mnt/mmc"   # dove muOS monta la scheda (device/config/storage/rom/mount)

# 1 = bloccato in modalita' kiosk. Tutto bloccato tranne le collezioni.
KIOSK = {
    "enable": 1, "message": 1,
    "collect/access": 1, "collect/add_con": 1, "collect/new_dir": 1, "collect/remove": 1,
    "launch/apps": 1, "launch/config": 1, "launch/explore": 1, "launch/history": 1, "launch/info": 1,
    "launch/collection": 0,
}


def fnv1a(text):
    h = 0x811C9DC5
    for c in text.encode("utf-8"):
        h = ((h ^ c) * 0x01000193) & 0xFFFFFFFF
    return h


def cmd_install_kiosk(a):
    sd = Path(a.sd)
    roms = rom_root(sd)
    dest = sd / "MUOS" / "info" / "collection" / "kiosk"
    entries = []
    for s in kept():
        r = s["rom"]
        if not (roms / r["system"] / r["file"]).is_file():
            print("Manca sulla scheda, salto: %s" % rel_of(s))
            continue
        full = "%s/ROMS/%s/%s" % (ROM_MOUNT, r["system"], r["file"])
        stem = Path(r["file"]).stem
        entries.append(("%s-%08X.cfg" % (stem, fnv1a(full)), "%s\n%s\n%s" % (full, r["system"], stem)))
    for name, _ in entries:
        print("%s/%s" % (dest, name))
    script = BUILD / "kiosk-rootfs.sh"
    rootfs = Path(a.rootfs) / "opt" / "muos"
    lines = ["#!/bin/sh", "# Attiva la modalita' kiosk e l'avvio sulla collezione. Lancia con sudo.",
             "# Salva i valori attuali in kiosk-rootfs-undo.sh (stessa cartella).", "set -e",
             'R="%s"' % rootfs, 'U="%s"' % (BUILD / "kiosk-rootfs-undo.sh"),
             '[ -d "$R/kiosk" ] || { echo "ROOTFS non montata: $R"; exit 1; }',
             '[ -e "$U" ] || { echo "#!/bin/sh"; for f in $(cd "$R/kiosk" && find . -type f); do '
             'echo "printf %s $(cat "$R/kiosk/$f") > \\"$R/kiosk/$f\\""; done; '
             'echo "printf %s $(cat "$R/config/settings/general/startup") > \\"$R/config/settings/general/startup\\""; '
             'echo "printf %s $(cat "$R/config/settings/general/sound") > \\"$R/config/settings/general/sound\\""; } > "$U"']
    for k, v in KIOSK.items():
        lines.append('printf %d > "$R/kiosk/%s"' % (v, k))
    lines += ['printf collection > "$R/config/settings/general/startup"',
              'printf 2 > "$R/config/settings/general/sound"  # suoni del tema (avvio/spegnimento MBR)', "sync",
              'echo "Kiosk attivo. Per annullare: sudo sh $U"']
    print("\nScript per la partizione di sistema: %s" % script)
    if not a.apply:
        print("Simulazione: aggiungi --apply.")
        return 0
    dest.mkdir(parents=True, exist_ok=True)
    for name, body in entries:
        (dest / name).write_text(body, encoding="utf-8")
    BUILD.mkdir(exist_ok=True)
    script.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.sync()
    print("Scritte %d voci. Ora lancia: sudo sh %s" % (len(entries), script))
    return 0


# -------------------------------------------------------------- install-previews

def cmd_install_previews(a):
    """Copertina ferma + brano in un MP4 (H.264 + AAC): muOS lo riproduce, con l'audio, al posto della PNG.

    muOS mostra il video alla sua misura reale (con boxartscale=0), quindi va fatto piccolo."""
    import re
    import subprocess
    if not shutil.which("ffmpeg"):
        sys.exit("Serve ffmpeg.")
    media = Path(a.media).expanduser()
    by_id = media_files(media)
    sd = Path(a.sd)
    muos = load_json(MUOS_FILE)
    cat = sd / muos["catalogue_root"]
    out_root = BUILD / "previews"
    todo, missing = [], []
    for s in kept():
        r = s["rom"]
        stem = Path(r["file"]).stem
        cover = Path(a.covers) / r["system"] / (stem + ".png")
        src = by_id.get(s["video_id"])
        if not src or not cover.is_file():
            missing.append("%s (%s)" % (s["title"], "brano" if not src else "copertina"))
            continue
        todo.append((s, cover, src, out_root / r["system"] / (stem + ".mp4"),
                     cat / muos["systems"][r["system"]] / muos["box_dir"] / (stem + ".mp4")))
    for s, cover, src, out, dest in todo:
        print("%-40s <- %s" % (s["title"], src.name))
    if missing:
        print("\nSenza anteprima: %s" % ", ".join(missing))
    if not a.apply:
        print("\nSimulazione: %d anteprime. Aggiungi --apply." % len(todo))
        return 0
    for s, cover, src, out, dest in todo:
        if not out.is_file() or a.force:
            out.parent.mkdir(parents=True, exist_ok=True)
            dur = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
                                  "format=duration", "-of", "default=nw=1:nk=1", str(src)],
                                 check=True, capture_output=True, text=True).stdout.strip()
            acodec = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
                                     "stream=codec_name", "-of", "default=nw=1:nk=1", str(src)],
                                    check=True, capture_output=True, text=True).stdout.strip()
            # il lettore di muOS 2606 decodifica solo AAC, MP3 e PCM (niente Opus/Vorbis)
            audio = ["-c:a", "copy"] if acodec == "aac" else ["-c:a", "aac", "-b:a", a.bitrate]  # AAC provato sulla console
            cmd = ["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", "2", "-i", str(cover), "-i", str(src),
                   "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-profile:v", "baseline", "-tune", "stillimage",
                   "-vf", "scale=%s:flags=lanczos" % a.size.replace("x", ":"),
                   "-pix_fmt", "yuv420p", "-r", "2", *audio,
                   "-t", dur, "-movflags", "+faststart", str(out)]
            subprocess.run(cmd, check=True)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(out, dest)
        print("ok  %s" % dest)
    os.sync()
    print("\nFatto: %d anteprime. Le PNG restano accanto come riserva." % len(todo))
    return 0


# ---------------------------------------------------------------- install-sounds

# (ruolo, video_id del brano, inizio in secondi, durata, dissolvenza finale). Scelti dal profilo di volume.
SOUNDS = [
    ("startup", "XNQvm-q__tQ", 46.0, 4.0, 1.2),   # OCEAN LOADERS, primo attacco pieno
    ("shutdown", "3HSpWQH4iRs", 18.0, 4.0, 2.5),  # DOOM, entrata del riff
    ("reboot", "3HSpWQH4iRs", 18.0, 4.0, 2.5),
]


INIT_SCRIPT = r"""#!/bin/sh
# mbr-anbernic: suono di avvio. muOS lancia gli script di MUOS/init se user_init = 1.
WAV="$(dirname "$0")/mbr-startup.wav"
[ -f "$WAV" ] || exit 0
export XDG_RUNTIME_DIR=/run PIPEWIRE_RUNTIME_DIR=/run
i=0
while [ "$(cat /opt/muos/device/config/audio/ready 2>/dev/null)" != 1 ] && [ $i -lt 150 ]; do
    sleep 0.2; i=$((i + 1))
done
sleep 0.5
pw-play "$WAV" 2>/dev/null || aplay -q "$WAV"
"""


def cmd_install_sounds(a):
    """Pezzi brevi dei brani come suoni di avvio/spegnimento del tema (WAV 16 bit 44.1 kHz)."""
    import re
    import subprocess
    media = Path(a.media).expanduser()
    by_id = media_files(media)
    jobs = []
    for role, vid, start, dur, fade in SOUNDS:
        if vid not in by_id:
            print("Manca il brano %s per %s, salto" % (vid, role))
            continue
        jobs.append((role, by_id[vid], start, dur, fade))
        print("%-9s <- %s da %.0fs, %.0fs, dissolvenza %.1fs" % (role, by_id[vid].name, start, dur, fade))
    dests = [BUILD / "theme" / a.theme / "sound", Path(a.sd) / "MUOS" / "theme" / a.theme / "sound"]
    if not a.apply:
        print("\nSimulazione: andrebbero in %s. Aggiungi --apply." % ", ".join(map(str, dests)))
        return 0
    out = BUILD / "sounds"
    out.mkdir(parents=True, exist_ok=True)
    for role, src, start, dur, fade in jobs:
        wav = out / (role + ".wav")
        af = "afade=t=in:d=0.05,afade=t=out:st=%.2f:d=%.2f,loudnorm=I=-14:TP=-1.5" % (dur - fade, fade)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(start), "-t", str(dur), "-i", str(src), "-vn",
                        "-af", af, "-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le", str(wav)], check=True)
        for d in dests:
            if d.parent.is_dir():
                d.mkdir(exist_ok=True)
                shutil.copyfile(wav, d / wav.name)
        print("ok  %s" % role)
    # Il "chime" di muOS si perde quando si parte direttamente dalla collezione (kiosk): lo suona
    # invece uno script utente in MUOS/init appena PipeWire e' pronto.
    init = Path(a.sd) / "MUOS" / "init"
    if init.is_dir() and (out / "startup.wav").is_file():
        shutil.copyfile(out / "startup.wav", init / "mbr-startup.wav")
        (init / "mbr-startup.sh").write_text(INIT_SCRIPT, encoding="utf-8")
        print("ok  %s" % (init / "mbr-startup.sh"))
    script = BUILD / "sound-rootfs.sh"
    keys = [("general/sound", 2), ("advanced/user_init", 1), ("general/chime", 0)]
    lines = ["#!/bin/sh", "# Suoni del tema, script utente all'avvio, chime di muOS spento. Lancia con sudo.", "set -e",
             'C="%s/opt/muos/config/settings"' % a.rootfs,
             '[ -d "$C/general" ] || { echo "ROOTFS non montata"; exit 1; }',
             'U="%s"' % (BUILD / "sound-rootfs-undo.sh"),
             '[ -e "$U" ] || echo "#!/bin/sh" > "$U"']
    for k, v in keys:
        lines += ['F="$C/%s"' % k,
                  'grep -qF "$F" "$U" || printf \'printf %%s %s > "%s"\\n\' "$(cat "$F")" "$F" >> "$U"',
                  'printf %d > "$F"' % v]
    lines += ["sync", 'echo "Fatto. Per annullare: sudo sh $U"']
    script.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.sync()
    print("\nOra lancia: sudo sh %s" % script)
    return 0


# ------------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, fn, help_, sd=True, apply=False):
        p = sub.add_parser(name, help=help_)
        if sd:
            p.add_argument("--sd", default=DEFAULT_SD, help="radice della scheda (default: %(default)s)")
        if apply:
            p.add_argument("--apply", action="store_true", help="esegui davvero (altrimenti simulazione)")
        p.set_defaults(fn=fn)
        return p

    add("list", cmd_list, "mostra i 42 brani e il gioco abbinato", sd=False)
    add("check", cmd_check, "verifica che i giochi scelti esistano sulla scheda")
    add("inspect", cmd_inspect, "descrive la struttura di muOS sulla scheda")
    p = add("hide", cmd_hide, "sposta in ROMS_HIDDEN tutti i giochi non scelti", apply=True)
    p.add_argument("--allow-missing", action="store_true", help="procedi anche se mancano dei giochi scelti")
    add("restore", cmd_restore, "rimette a posto i giochi nascosti", apply=True)
    p = add("covers", cmd_covers, "scarica le miniature e prepara le copertine PNG", sd=False)
    p.add_argument("--out", default=str(BUILD / "covers"))
    p.add_argument("--size", default="282x216", help="misura delle copertine gia' presenti in muOS (default: %(default)s)")
    p.add_argument("--fit", choices=["cover", "contain"], default="cover")
    p.add_argument("--only-kept", action="store_true", help="solo i brani con un gioco")
    p = add("install-covers", cmd_install_covers, "copia le copertine nel catalogo di muOS", apply=True)
    p.add_argument("--covers", default=str(BUILD / "covers"))
    p.add_argument("--create", action="store_true", help="crea le cartelle del catalogo se mancano")
    p = add("install-theme", cmd_install_theme, "genera e installa il tema MBR Terminal", apply=True)
    p.add_argument("--font", default="topaz.ttf", help="percorso di topaz.ttf (default: %(default)s)")
    p.add_argument("--name", default="MBR Terminal")
    p.add_argument("--base", default="GB Dark", help="tema da cui copiare i suoni ('' per nessuno)")
    p.add_argument("--logo", default=str(LOGO_FILE), help="logo di avvio (default: quello salvato da install-logo)")
    p = add("install-logo", cmd_install_logo, "mette un'immagine come logo di avvio", apply=True)
    p.add_argument("image", help="immagine del logo di avvio (jpg/png)")
    p.add_argument("--outro", help="immagine per spegnimento e riavvio (default: la stessa)")
    p.add_argument("--boot", default=DEFAULT_BOOT, help="partizione di avvio montata (default: %(default)s)")
    p.add_argument("--theme", default="MBR Terminal")
    p = add("install-kiosk", cmd_install_kiosk, "collezione kiosk con i giochi scelti + script di attivazione", apply=True)
    p.add_argument("--rootfs", default="/run/media/deck/ROOTFS", help="partizione di sistema di muOS montata")
    p = add("install-sounds", cmd_install_sounds, "pezzi dei brani come suoni di avvio e spegnimento", apply=True)
    p.add_argument("--media", required=True, help="cartella con i file dei brani (nome con [video_id])")
    p.add_argument("--theme", default="MBR Terminal")
    p.add_argument("--rootfs", default="/run/media/deck/ROOTFS", help="partizione di sistema di muOS montata")
    p = add("install-previews", cmd_install_previews, "anteprime MP4: copertina + brano, suonano mentre scorri", apply=True)
    p.add_argument("--media", required=True, help="cartella con i file audio/video dei brani (nome con [video_id])")
    p.add_argument("--covers", default=str(BUILD / "covers"))
    p.add_argument("--bitrate", default="160k", help="audio AAC se va convertito (default: %(default)s)")
    p.add_argument("--size", default="272x204", help="misura del video: lo spazio a destra della lista (default: %(default)s)")
    p.add_argument("--force", action="store_true", help="rigenera anche gli MP4 gia' pronti")
    add("install-names", cmd_install_names, "scrive i titoli dei brani come nomi dei giochi", apply=True)
    p = add("theme-dump", cmd_theme_dump, "descrive un tema muOS esistente da usare come modello")
    p.add_argument("--name", help="nome del tema (senza: elenca i temi installati)")
    p.add_argument("--max-kb", type=int, default=300, help="tetto ai file di testo inclusi (default: %(default)s)")

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
