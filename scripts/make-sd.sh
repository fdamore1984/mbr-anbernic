#!/bin/sh
# make-sd.sh: prepara da zero una scheda SD per l'Anbernic con muOS e il kit MBR.
#
#   1) scripts/make-sd.sh flash /dev/mmcblk0 [immagine.img.gz | cartella-kit]
#        scrive muOS sulla scheda (CANCELLA TUTTO quello che c'e' sopra)
#   2) metti la scheda nell'Anbernic, accendi, aspetta il menu di muOS, spegni
#        (al primo avvio muOS allarga le partizioni e crea le sue cartelle)
#   3) scripts/make-sd.sh setup ~/mbr-kit
#        copia giochi, brani, tema, loghi, collezione e imposta il kiosk
#
# Il kit si crea dalla scheda che funziona con: python3 scripts/mbr.py export-kit --apply
# Serve: Linux con udisks (SteamOS va bene), python3, sudo.
set -eu

HERE=$(cd "$(dirname "$0")/.." && pwd)
PY=python3
[ -x "$HERE/.venv/bin/python" ] && PY="$HERE/.venv/bin/python"

die() { echo "ERRORE: $*" >&2; exit 1; }

partitions() { lsblk -rno PATH "$1" | tail -n +2; }

unmount_all() {
	for p in $(partitions "$1"); do
		if [ -n "$(lsblk -rno MOUNTPOINT "$p")" ]; then
			udisksctl unmount -b "$p" >/dev/null 2>&1 || sudo umount "$p"
		fi
	done
}

flash() {
	DEV="${1:-}"
	SRC="${2:-}"
	[ -b "$DEV" ] || die "indica la scheda, per esempio /dev/mmcblk0 (vedi: lsblk)"
	[ "$(lsblk -dno TYPE "$DEV")" = disk ] || die "$DEV non e' un disco intero (niente numero di partizione)"
	case "$DEV" in /dev/mmcblk*) ;; *)
		[ "$(lsblk -dno RM "$DEV" | tr -d ' ')" = 1 ] || die "$DEV non e' un disco rimovibile: mi fermo" ;;
	esac
	for mp in $(lsblk -rno MOUNTPOINT "$DEV"); do
		case "$mp" in / | /home | /var | /efi | /esp | /boot*) die "$DEV contiene il sistema ($mp): mi fermo" ;; esac
	done

	if [ -d "$SRC" ]; then SRC=$(ls "$SRC"/muos/*.img.gz 2>/dev/null | head -n 1); fi
	[ -n "$SRC" ] || SRC=$(ls "$HOME"/Downloads/MustardOS_*.img.gz 2>/dev/null | head -n 1)
	[ -f "$SRC" ] || die "immagine di muOS non trovata: passala come secondo argomento"

	echo "Immagine: $SRC"
	lsblk -o NAME,SIZE,MODEL,LABEL,MOUNTPOINT "$DEV"
	echo
	echo "Tutto il contenuto di $DEV verra' CANCELLATO."
	printf "Per confermare riscrivi il nome del disco (%s): " "$DEV"
	read -r ANSWER
	[ "$ANSWER" = "$DEV" ] || die "conferma non valida, non ho toccato niente"

	unmount_all "$DEV"
	gzip -dc "$SRC" | sudo dd of="$DEV" bs=4M conv=fsync status=progress
	sync
	sleep 2
	unmount_all "$DEV"
	echo
	echo "Fatto. Ora:"
	echo "  1. metti la scheda nell'Anbernic (slot TF1), accendi e aspetta il menu di muOS"
	echo "  2. spegni dal menu, rimetti la scheda qui"
	echo "  3. lancia: $0 setup CARTELLA-DEL-KIT"
}

find_part() { # etichetta -> percorso della partizione (una sola)
	FOUND=$(lsblk -rno PATH,LABEL | awk -v l="$1" '$2 == l { print $1 }')
	[ "$(printf '%s\n' "$FOUND" | grep -c .)" = 1 ] || die "trovo $(printf '%s\n' "$FOUND" | grep -c .) partizioni '$1': inserisci una sola scheda muOS"
	echo "$FOUND"
}

mount_of() { # partizione -> punto di montaggio (la monta se serve)
	MP=$(lsblk -rno MOUNTPOINT "$1")
	if [ -z "$MP" ]; then
		udisksctl mount -b "$1" >/dev/null
		MP=$(lsblk -rno MOUNTPOINT "$1")
	fi
	[ -n "$MP" ] || die "non riesco a montare $1"
	printf '%s' "$MP" | sed 's/\\x20/ /g'
}

setup() {
	KIT="${1:-}"
	[ -f "$KIT/KIT.json" ] || die "indica la cartella del kit (quella con KIT.json)"
	DATA=$(find_part MustardOS) || exit 1
	BOOTP=$(find_part BOOT) || exit 1
	ROOTP=$(find_part ROOTFS) || exit 1
	DISK="/dev/$(lsblk -rno PKNAME "$DATA")"
	SD=$(mount_of "$DATA")
	BOOT=$(mount_of "$BOOTP")
	ROOT=$(mount_of "$ROOTP")
	echo "Scheda $DISK: dati $SD, avvio $BOOT, sistema $ROOT"
	[ -d "$SD/MUOS" ] || die "manca $SD/MUOS: avvia muOS una volta nella console prima del setup"

	"$PY" "$HERE/scripts/mbr.py" install-kit --kit "$KIT" --sd "$SD" --boot "$BOOT" --rootfs "$ROOT" --apply
	echo
	echo "Ora le impostazioni della partizione di sistema (serve la password):"
	sudo sh "$HERE/build/kit-rootfs.sh"
	sync
	unmount_all "$DISK"
	echo
	echo "Scheda pronta: puoi toglierla e metterla nell'Anbernic."
}

case "${1:-}" in
	flash) shift; flash "$@" ;;
	setup) shift; setup "$@" ;;
	*) sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac
