"""Kit privato: tutto cio' che serve per rifare la scheda MBR da zero, senza rigenerare niente.

export-kit copia dalla scheda attuale (che funziona) in una cartella:

    kit/
      KIT.json                         elenco dei giochi e versione
      sd/ROMS/...                      i giochi scelti, con CD, dischi e cartelle ScummVM collegati
      sd/MUOS/info/catalogue/...       copertine PNG e anteprime MP4 con il brano
      sd/MUOS/info/collection/kiosk/   le voci della collezione
      sd/MUOS/theme/MBR Terminal/      il tema completo (font, loghi, suoni)
      sd/MUOS/init/                    lo script del suono di avvio
      names.json                       i nomi dei giochi (uniti a global.json)
      boot/                            logo di avvio e di carica (partizione BOOT)
      rootfs/content/<SISTEMA>/        emulatore assegnato a ogni cartella usata
      rootfs/settings.json             impostazioni di muOS (kiosk, avvio, suoni, tema)
      muos/                            l'immagine di muOS (facoltativa)

install-kit fa il percorso inverso su una scheda appena preparata (muOS avviato una volta).
Copia soltanto file: non servono Pillow, ffmpeg o Node. Le modifiche alla partizione di sistema,
che appartiene a root, finiscono in uno script da lanciare con sudo, con il suo file di annullamento.

Il kit contiene giochi, brani e immagini dell'artista: va tenuto privato, mai nel repository.
"""
import json
import os
import re
import shlex
import shutil
import sys
import time
from pathlib import Path

# impostazioni di muOS salvate nel kit, relative a /opt/muos; valori di riserva se mancano sulla scheda
SETTINGS = {
    "config/settings/general/startup": "collection",
    "config/settings/general/sound": "2",
    "config/settings/general/chime": "0",
    "config/settings/advanced/user_init": "1",
    "config/theme/active": "MBR Terminal",
}
CORE_FILES = ("core.cfg", "core.con", "core.gov", "core.rac")


def companions(rom):
    """Il file del gioco piu' quelli che gli servono: tracce di un .cue, voci di un .m3u,
    cartella dei dati di un .scummvm."""
    out = [rom]
    ext = rom.suffix.lower()
    if ext == ".cue":
        for line in rom.read_text(errors="replace").splitlines():
            m = re.match(r'\s*FILE\s+"(.+)"', line)
            if m:
                out.append(rom.parent / m.group(1))
    elif ext == ".m3u":
        for line in rom.read_text(errors="replace").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                out += companions(rom.parent / line)
    elif ext == ".scummvm":
        for name in ("." + rom.stem, "_" + rom.stem, rom.stem):
            d = rom.parent / name
            if d.is_dir():
                out.append(d)
                break
    return out


def copy_any(src, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dest, dirs_exist_ok=True)
    else:
        shutil.copy2(src, dest)


def size_of(p):
    if p.is_dir():
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
    return p.stat().st_size


def export_kit(a, kept, muos, kiosk, theme_name):
    sd, boot, rootfs, out = Path(a.sd), Path(a.boot), Path(a.rootfs) / "opt" / "muos", Path(a.out).expanduser()
    for p, what in ((sd / "ROMS", "partizione dati"), (boot, "partizione BOOT"), (rootfs / "config", "partizione ROOTFS")):
        if not p.exists():
            sys.exit("Non trovo la %s: %s (e' montata?)" % (what, p))
    plan, missing = [], []
    cat = sd / muos["catalogue_root"]
    systems = set()
    games = []
    for s in kept:
        r = s["rom"]
        rom = sd / "ROMS" / r["system"] / r["file"]
        if not rom.is_file():
            missing.append("%s/%s" % (r["system"], r["file"]))
            continue
        systems.add(r["system"])
        for f in companions(rom):
            if not f.exists():
                missing.append(str(f.relative_to(sd)))
                continue
            plan.append((f, out / "sd" / f.relative_to(sd)))
        box = cat / muos["systems"][r["system"]] / muos["box_dir"]
        for ext in (".png", ".mp4"):
            f = box / (Path(r["file"]).stem + ext)
            if f.is_file():
                plan.append((f, out / "sd" / f.relative_to(sd)))
        games.append({"n": s["n"], "title": s["title"], "system": r["system"], "file": r["file"]})
    for rel in ("MUOS/info/collection/kiosk", "MUOS/theme/" + theme_name):
        if (sd / rel).is_dir():
            plan.append((sd / rel, out / "sd" / rel))
    for f in sorted((sd / "MUOS" / "init").glob("mbr-startup.*")):
        plan.append((f, out / "sd" / f.relative_to(sd)))
    for rel in ("bootlogo.bmp", "bat/battery_charge.bmp"):
        if (boot / rel).is_file():
            plan.append((boot / rel, out / "boot" / rel))
    for system in sorted(systems):
        d = rootfs / "share" / "info" / "content" / system
        for name in CORE_FILES:
            if (d / name).is_file():
                plan.append((d / name, out / "rootfs" / "content" / system / name))
    image = Path(a.image).expanduser() if a.image else None
    if image and image.is_file():
        plan.append((image, out / "muos" / image.name))

    total = sum(size_of(src) for src, _ in plan)
    print("%d elementi, %.1f GB -> %s" % (len(plan), total / 1e9, out))
    if missing:
        print("Mancano sulla scheda: %s" % ", ".join(missing))
    if not a.apply:
        print("Simulazione: aggiungi --apply.")
        return 0

    for src, dest in plan:
        copy_any(src, dest)
    names = load_names(sd / "MUOS" / "info" / "name" / "global.json", kept)
    (out / "names.json").write_text(json.dumps(names, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    settings = {}
    for rel, default in SETTINGS.items():
        f = rootfs / rel
        settings[rel] = f.read_text().strip() if f.is_file() else default
    for k, v in kiosk.items():
        f = rootfs / "kiosk" / k
        settings["kiosk/" + k] = f.read_text().strip() if f.is_file() else str(v)
    (out / "rootfs").mkdir(parents=True, exist_ok=True)
    (out / "rootfs" / "settings.json").write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    version = rootfs / "config" / "system" / "version"
    (out / "KIT.json").write_text(json.dumps({
        "created": time.strftime("%Y-%m-%d %H:%M"),
        "muos": version.read_text().strip() if version.is_file() else "",
        "theme": theme_name,
        "games": games,
    }, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    os.sync()
    print("Kit pronto: %s. Tienilo privato (giochi, brani e immagini non vanno nel repository)." % out)
    return 0


def load_names(global_json, kept):
    """Solo i nomi dei giochi del progetto, presi da global.json."""
    data = json.loads(global_json.read_text(encoding="utf-8")) if global_json.is_file() else {}
    stems = {Path(s["rom"]["file"]).stem for s in kept}
    return {k: v for k, v in data.items() if k in stems}


def install_kit(a, build):
    kit, sd, boot, rootfs = Path(a.kit).expanduser(), Path(a.sd), Path(a.boot), Path(a.rootfs) / "opt" / "muos"
    if not (kit / "KIT.json").is_file():
        sys.exit("Non e' un kit: manca %s" % (kit / "KIT.json"))
    if not (sd / "MUOS").is_dir():
        sys.exit("Sulla scheda manca la cartella MUOS: avvia muOS una volta nella console, poi riprova.")
    info = json.loads((kit / "KIT.json").read_text(encoding="utf-8"))
    print("Kit del %s, muOS %s, %d giochi" % (info["created"], info["muos"], len(info["games"])))
    items = [p for p in sorted((kit / "sd").iterdir())] if (kit / "sd").is_dir() else []
    boot_files = [p for p in (kit / "boot").rglob("*") if p.is_file()] if (kit / "boot").is_dir() else []
    print("Da copiare sulla scheda: %s; nella partizione BOOT: %d file" %
          (", ".join(p.name for p in items), len(boot_files)))
    if not a.apply:
        print("Simulazione: aggiungi --apply.")
        return 0

    for p in items:
        copy_any(p, sd / p.name)
    print("ok  giochi, copertine, anteprime, tema, collezione, suono di avvio")

    names_file = kit / "names.json"
    if names_file.is_file():
        g = sd / "MUOS" / "info" / "name" / "global.json"
        data = json.loads(g.read_text(encoding="utf-8")) if g.is_file() else {}
        if g.is_file() and not Path(str(g) + ".bak").exists():
            shutil.copy2(g, str(g) + ".bak")
        data.update(json.loads(names_file.read_text(encoding="utf-8")))
        g.parent.mkdir(parents=True, exist_ok=True)
        g.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("ok  nomi dei giochi in %s" % g)

    if boot.is_dir():
        backup = build / "boot-backup-kit"
        for f in boot_files:
            rel = f.relative_to(kit / "boot")
            if (boot / rel).is_file() and not (backup / rel).exists():
                (backup / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(boot / rel, backup / rel)
            copy_any(f, boot / rel)
        print("ok  logo di avvio (originali in %s)" % backup)

    script = build / "kit-rootfs.sh"
    undo = build / "kit-rootfs-undo.sh"
    q = shlex.quote
    lines = ["#!/bin/sh",
             "# Impostazioni di muOS e emulatori delle cartelle, dal kit. Lancia con sudo.",
             "set -e",
             "R=%s" % q(str(rootfs)),
             'U=%s' % q(str(undo)),
             '[ -d "$R/config" ] || { echo "ROOTFS non montata: $R"; exit 1; }',
             '[ -e "$U" ] || echo "#!/bin/sh" > "$U"']
    content = kit / "rootfs" / "content"
    if content.is_dir():
        for d in sorted(content.iterdir()):
            lines.append('mkdir -p "$R/share/info/content/%s"' % d.name)
            for f in sorted(d.iterdir()):
                lines.append('cp %s "$R/share/info/content/%s/%s"' % (q(str(f)), d.name, f.name))
    settings = json.loads((kit / "rootfs" / "settings.json").read_text())
    for rel, value in settings.items():
        lines += ['F="$R/%s"' % rel,
                  'mkdir -p "$(dirname "$F")"',
                  # valore precedente nel file di annullamento (i valori di muOS non hanno apostrofi)
                  'if [ -f "$F" ] && ! grep -qF "$F" "$U"; then '
                  'echo "printf %s \'$(cat "$F")\' > \\"$F\\"" >> "$U"; fi',
                  'printf %%s %s > "$F"' % q(value)]
    lines += ["sync", 'echo "Impostazioni applicate. Per annullarle: sudo sh $U"']
    build.mkdir(exist_ok=True)
    script.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.sync()
    print("\nScritto %s: va lanciato con sudo (make-sd.sh lo fa da solo)." % script)
    return 0
