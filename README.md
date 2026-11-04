# mbr-anbernic

Trasforma una Anbernic con muOS in una console a tema **Master Boot Record**. All'accensione compare solo la collezione dei giochi abbinati ai brani della playlist WAREZ, ciascuno con la copertina del video e la musica del suo brano. Gli altri giochi vengono nascosti, mai cancellati.

## Cosa serve

- Una Anbernic con schermo 640x480 (provata su RG35XX Plus) e **muOS 2606** sulla scheda SD. Accendila una volta con la scheda nuova, così muOS crea le sue cartelle.
- Le ROM dei giochi della lista, copiate in `ROMS/<SISTEMA>/` sulla scheda. `./mbr list` mostra quali sono.
- Una Steam Deck in modalità desktop (o un PC Linux) collegata a internet. Python, ffmpeg e Node.js li prepara `./mbr` da solo al primo uso, dentro la cartella della repo.

## Installazione

```bash
git clone https://github.com/fdamore1984/mbr-anbernic
cd mbr-anbernic
mkdir miei-file
```

Metti in `miei-file/` i tuoi file. Sono tutti facoltativi:

- `logo.png` (o `.jpg`): il logo di avvio e del salvaschermo;
- `logo_spegnimento.png` (o `.jpg`): il logo di spegnimento e riavvio. Se manca, si usa `logo`;
- i brani, audio o video. Il nome deve contenere il codice del video (`... [3HSpWQH4iRs].mp4`) oppure cominciare con il numero del brano (`32 - Flashback.mp3`). Servono per la musica sui giochi e per i suoni di avvio e spegnimento.

Il font Topaz viene scaricato da solo.

Inserisci la scheda nella Deck, poi:

```bash
./mbr setup            # prova: mostra cosa farebbe, senza toccare la scheda
./mbr setup --apply    # esegue tutto, chiede la password di sudo e alla fine smonta la scheda
```

Poi metti la scheda nella console e:

1. scegli il tema in **Configuration > Customisation > Theme > MBR Terminal**;
2. dal menu principale (tasto B) vai in **Esplora** e apri una volta le cartelle DOS, SCUMMVM e AMIGA. Così muOS assegna l'emulatore a quei giochi.

## Se qualcosa non va

- **Mancano dei giochi**: `setup` si ferma e li elenca. Correggi il nome del file nel campo `rom` di `data/songs.json`, oppure rilancia con `--allow-missing`.
- **Scheda montata altrove** (non su Steam Deck): indica le tre partizioni con `--sd`, `--boot` e `--rootfs`, oppure con le variabili `MBR_SD`, `MBR_BOOT` e `MBR_ROOTFS`.
- **La console resta ferma sul logo**: la partizione di sistema `ROOTFS` si è rovinata. Succede se togli la scheda senza smontarla. `setup` la smonta da solo. Per ripararla, a scheda smontata: `sudo fsck.ext4 -fy /dev/mmcblk0p5`. Se la batteria si è scaricata nei tentativi, lasciala in carica 1-2 ore.

## Tornare indietro

- Giochi nascosti: `./mbr restore --apply`.
- Avvio sulla collezione e suoni: `sudo sh <scheda>/MBR_BACKUP/kiosk-rootfs-undo.sh` e `sudo sh <scheda>/MBR_BACKUP/sound-rootfs-undo.sh`.
- Logo di avvio originale: si trova in `<scheda>/MBR_BACKUP/boot/`.

## Cosa non va nella repo

La repo è pubblica. ROM, brani, loghi e font non vanno caricati: restano in `miei-file/` e `build/`, che git ignora.

I singoli passaggi sono comandi separati (`./mbr --help`). Le note tecniche su muOS 2606 sono in [`docs/muos-2606.md`](docs/muos-2606.md).
