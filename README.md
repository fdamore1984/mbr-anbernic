# mbr-anbernic

Trasforma una Anbernic con muOS in una console a tema **Master Boot Record**: sulla scheda restano visibili solo i giochi abbinati ai brani della playlist WAREZ, ognuno con la copertina presa dalla miniatura del video del suo brano. Tutti gli altri giochi vengono nascosti, mai cancellati.

Pensato per RG35XX Plus con muOS 2606, preparato da una Steam Deck in modalità desktop. Per ripetere l'operazione su un'altra Anbernic bastano gli stessi comandi.

## Stato

Provato su una RG35XX Plus con muOS 2606 (novembre 2026): funziona.

| Parte | Stato |
|---|---|
| 42 brani della playlist, 36 con un gioco (`data/songs.json`) | fatto; mancano Red Alert, DOOM II, Dune: Spice Opera, Ocean Loaders, Monkey Island, Super Metroid |
| Solo i giochi scelti visibili (`hide`), gli altri in `ROMS_HIDDEN` | provato sulla console |
| Copertine 272x204 dalle miniature dei video | provato |
| Anteprima con il brano: fermandosi su un gioco parte la sua musica | provato |
| Tema "MBR Terminal": Topaz, bianco su nero | provato |
| Logo di avvio, logo di spegnimento/riavvio, salvaschermo | provato |
| Suoni di avvio e spegnimento (pezzi dei brani) | provato |
| Modalità kiosk: all'accensione solo la collezione dei giochi | provato |
| Giochi DOS (DOSBox Pure) e ScummVM | installati, **da provare** |

## Cosa serve

- Python 3.8 o superiore (c'è già su SteamOS)
- Pillow, per `covers` e `install-theme`: `pip install --user pillow`
- Node.js (comando `npx`), solo per `install-theme`: converte il font nel formato di muOS. SteamOS non ce l'ha: scarica il pacchetto `linux-x64` da nodejs.org, scompattalo in `~/.local/opt` e collega `node`, `npm` e `npx` in `~/.local/bin` (non serve sudo). Senza `npx` il tema non viene installato.
- la scheda SD di muOS montata (default `/run/media/deck/MustardOS`, cambiabile con `--sd` o con la variabile `MBR_SD`)

## Uso

Tutti i comandi che modificano la scheda fanno prima una simulazione: per eseguire davvero si aggiunge `--apply`. Su SteamOS Pillow sta in un ambiente virtuale: usa `.venv/bin/python` al posto di `python3`.

```bash
git clone https://github.com/fdamore1984/mbr-anbernic
cd mbr-anbernic

python3 scripts/mbr.py list              # brani e giochi abbinati
python3 scripts/mbr.py inspect           # descrive la struttura di muOS sulla scheda
python3 scripts/mbr.py check             # i giochi scelti ci sono tutti?
python3 scripts/mbr.py hide --apply      # sposta gli altri giochi in ROMS_HIDDEN
python3 scripts/mbr.py restore --apply   # li rimette dove erano

# copertine e nomi
python3 scripts/mbr.py covers --only-kept --size 272x204 --out build/covers-272
python3 scripts/mbr.py install-covers --covers build/covers-272 --create --apply
python3 scripts/mbr.py install-names --apply                     # i titoli dei brani come nomi

# tema, loghi e suoni (immagini e brani sono tuoi, non nel repository)
python3 scripts/mbr.py install-logo logo_start.png --outro logo_outro.jpg --apply
python3 scripts/mbr.py install-sounds --media cartella_brani --apply
python3 scripts/mbr.py install-theme --font topaz.ttf --apply

# la musica del brano sul gioco selezionato
python3 scripts/mbr.py install-previews --media cartella_brani --covers build/covers-272 --apply

# avvio diretto sulla collezione, modalita' kiosk
python3 scripts/mbr.py install-kiosk --apply
```

I file dei brani in `cartella_brani` vengono riconosciuti se il nome contiene il codice del video (`... [3HSpWQH4iRs].mp4`) oppure comincia con il numero del brano (`32 - Flashback.mp3`).

`install-kiosk`, `install-sounds` e i giochi DOS/ScummVM richiedono anche modifiche alla partizione di sistema di muOS (`ROOTFS`), che appartiene a root. Per queste i comandi scrivono uno script in `build/` da lanciare con `sudo`. Ognuno salva i valori precedenti in un file `*-undo.sh`, che serve per tornare indietro.

### Cosa ha imparato il progetto su muOS 2606

- Una copertina può essere un video, `box/<rom>.mp4`, e ha la precedenza sulla PNG. Viene riprodotta con l'audio quando ci si ferma sul gioco.
- Il lettore decodifica solo **H.264/HEVC/MPEG-4 per il video e AAC/MP3/PCM per l'audio**. Niente Opus né Vorbis: con quei formati il video resta muto.
- Con "scala copertina" a 0, immagini e video vengono mostrati alla loro misura reale. Se sono grandi quanto lo schermo, coprono la lista.
- Il logo di avvio è `bootlogo.bmp` (BMP 24 bit, 640x480) nella partizione `BOOT`. muOS lo copia dal tema quando il tema viene attivato.
- Spegnimento e riavvio mostrano `shutdown.png` e `reboot.png` del tema. Il salvaschermo "DVD" fa rimbalzare `screensaver.png`.
- Il suono di avvio di muOS (*chime*) si perde se si parte direttamente da una collezione. Lo suona invece uno script utente, `MUOS/init/mbr-startup.sh` (`settings/advanced/user_init = 1`).
- Le voci di una collezione sono file `.cfg` di tre righe (percorso, sistema, nome). Il nome del file è `<nome>-<FNV-1a del percorso>.cfg`. La collezione kiosk è `MUOS/info/collection/kiosk/`.
- L'emulatore di una cartella viene assegnato da solo solo aprendola nell'esploratore. Per le cartelle nuove usate dal kiosk va scritto a mano `share/info/content/<CARTELLA>/core.cfg`.

## Su un'altra Anbernic

1. Monta la scheda e lancia `check`: elenca i giochi che non trova con quel nome esatto.
2. Se i nomi dei file sono diversi, correggi il campo `rom` in `data/songs.json`.
3. Lancia `inspect` e confronta con `data/muos.json`, poi procedi con `hide`, `covers` e `install-covers`.

`covers` accetta `--size` (usa `272x204`, lo spazio accanto alla lista del tema) e `--fit cover|contain`.

## Se l'Anbernic resta ferma sul logo

È già successo (3 novembre 2026). Le modifiche del progetto non c'entravano: era rovinata la partizione di sistema di muOS.

- **Causa**: quando inserisci la scheda, SteamOS monta da solo anche `ROOTFS`, la partizione ext4 di sistema di muOS, in lettura e scrittura. Se togli la scheda dopo aver smontato solo `MustardOS`, `ROOTFS` resta sporca. Nel nostro caso la lista degli inode orfani era corrotta e muOS non arrivava al menu.
- **Come evitarlo**: prima di togliere la scheda smonta entrambe le partizioni:
  `udisksctl unmount -b /dev/mmcblk0p6; udisksctl unmount -b /dev/mmcblk0p5`
- **Come accorgersene**: `sudo fsck.ext4 -n` dice "clean" anche quando ci sono errori, perché legge solo il flag. Serve il controllo forzato, in sola lettura: `sudo fsck.ext4 -fn /dev/mmcblk0p5`.
- **Come ripararlo**: `sudo fsck.ext4 -fy /dev/mmcblk0p5`, a scheda smontata. La partizione dati è exFAT: `sudo fsck.exfat -n /dev/mmcblk0p6`.
- Dopo tanti avvii bloccati la batteria si scarica del tutto, e la console resta nera anche col cavo collegato per un po'. Lasciala in carica 1-2 ore prima di pensare a un guasto.
- È normale che il bootloader sulla scheda (settori 16 e 512) sia diverso dall'immagine: al primo avvio il chip Allwinner ci salva la calibrazione della RAM.

## Cosa c'è nel repository e cosa no

Il repository è pubblico, quindi contiene solo ciò che il progetto crea:

- `scripts/`: tutti i comandi;
- `data/`: brani, giochi abbinati e struttura di muOS;
- `theme/palette.json` e `assets/theme/MBR Terminal/`: il tema già generato, cioè configurazione, sfondi e anteprima.

Non contiene, e non va caricato:

- **le ROM**: tienile solo se possiedi i giochi originali;
- **i brani, le miniature dei video e i loghi** (logo di avvio, spegnimento, salvaschermo): appartengono all'artista. Si mettono in una cartella tua e i comandi li elaborano in `build/`, che git ignora;
- **il font Topaz**: per uso personale si scarica da `https://mbrserver.com/topaz.ttf`. Anche il font convertito (`font/default.bin`) resta fuori;
- **i suoni di navigazione** del tema: vengono copiati dal tema "GB Dark" di muOS già presente sulla scheda.
