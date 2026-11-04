# mbr-anbernic

Trasforma una Anbernic con muOS in una console a tema **Master Boot Record**:
- all'accensione si apre una collezione con i giochi abbinati ai brani della playlist WAREZ;
- ogni gioco ha la copertina presa dalla miniatura del video del suo brano;
- fermandosi su un gioco parte il suo brano;
- tema bianco su nero con il font Topaz, loghi e suoni MBR;
- dal menu principale (tasto B) si raggiungono anche tutti gli altri giochi.

Pensato per RG35XX Plus con muOS 2606 (Andromeda), preparato da una Steam Deck in modalità desktop.

**Per rifare la scheda da zero vai a [Rifare la scheda da zero](#rifare-la-scheda-da-zero).**

## Stato

Provato su una RG35XX Plus con muOS 2606 (novembre 2026): funziona.

| Parte | Stato |
|---|---|
| 42 brani della playlist, 41 con un gioco (`data/songs.json`) | fatto; Ocean Loaders non e' un gioco (e' il suono di avvio) |
| Altri giochi nascosti in `ROMS_HIDDEN` (`hide`/`restore`) | provato; ora rimessi in `ROMS`, raggiungibili da Esplora |
| Copertine 272x204 dalle miniature dei video | provato |
| Anteprima con il brano: fermandosi su un gioco parte la sua musica | provato |
| Tema "MBR Terminal": Topaz, bianco su nero | provato |
| Logo di avvio, logo di spegnimento/riavvio, salvaschermo | provato |
| Suoni di avvio e spegnimento (pezzi dei brani) | provato |
| Modalità kiosk: all'accensione la collezione MBR; dal menu principale (B) Esplora porta a tutti gli altri giochi | provato |
| Giochi DOS (DOSBox Pure), ScummVM, Amiga (PUAE 2021), PlayStation multi-disco (.m3u) | installati, **da provare** |
| Kit privato: `export-kit`, `build-kit`, `install-kit` | provati su cartelle e su una scheda finta |
| `make-sd.sh flash` / `setup` su una scheda vera | **non ancora provati** (controlli di sicurezza si) |

## Cosa serve

**Per rifare una scheda da un kit** (`make-sd.sh`, `install-kit`):
- Linux con udisks: SteamOS va bene, come quasi tutte le distribuzioni desktop. Su Windows e macOS non funziona;
- `python3` (3.8 o superiore), `gzip`, `dd`, `sudo`;
- un lettore di schede SD e una scheda da almeno 8 GB (il kit pesa circa 3,5 GB più muOS).

**Per creare il kit dai file sorgente** (`build-kit`) o usare i singoli comandi di generazione, in più:
- **Pillow**: `pip install --user pillow`. Su SteamOS non c'è pip: crea un ambiente virtuale con `python3 -m venv .venv && .venv/bin/pip install pillow` e usa `.venv/bin/python` al posto di `python3`;
- **ffmpeg**, per le anteprime con il brano e i suoni (su SteamOS c'è gia');
- **Node.js** (comando `npx`), per convertire il font nel formato di muOS. SteamOS non ce l'ha: scarica il pacchetto `linux-x64` da nodejs.org, scompattalo in `~/.local/opt` e collega `node`, `npm` e `npx` in `~/.local/bin` (non serve sudo);
- una connessione a internet, per scaricare le miniature dei video da YouTube.

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
- Il menu principale ha 8 voci fisse: il kiosk le blocca ma non le nasconde, e B dalla collezione torna sempre li'.
- L'emulatore di una cartella viene assegnato da solo solo aprendola nell'esploratore. Per le cartelle nuove usate dal kiosk va scritto a mano `share/info/content/<CARTELLA>/core.cfg`.

## Rifare la scheda da zero

Tutto il lavoro sta in due posti:

- **questo repository**: i comandi e le configurazioni;
- **un kit privato**, cioè una cartella tua, mai su GitHub, con giochi, brani, copertine, tema completo, loghi e impostazioni di muOS. Come crearlo è spiegato [piu' sotto](#creare-il-kit).

### 1. Scarica muOS

Scarica **muOS 2606.0 Andromeda per RG35XX Plus** dal sito ufficiale di MustardOS (https://muos.dev). Il file si chiama come `MustardOS_RG35XX-PLUS_2606.0_ANDROMEDA-<codice>.img.gz` e va messo nella cartella `muos/` del kit. Non scompattarlo: lo script lo legge compresso.

Il kit è stato fatto con questa versione, scritta in `KIT.json`. Con una versione diversa le impostazioni potrebbero non corrispondere: provala prima su una scheda di riserva.

### 2. Trova il nome della scheda

Inserisci la scheda e lancia:

```bash
lsblk -o NAME,SIZE,RM,TYPE,LABEL,MOUNTPOINT
```

Cerca il **disco intero** (`TYPE` = `disk`) con la misura della tua scheda (una da 64 GB appare come circa `57,6G`):

- nel lettore interno della Steam Deck di solito è **`/dev/mmcblk0`**;
- in un lettore USB è `/dev/sdX`, con `RM` = 1;
- **non** usare un nome che finisce con un numero di partizione (`mmcblk0p6`, `sdb1`);
- **mai** `nvme0n1`: è il disco della Deck.

Se hai dubbi, togli la scheda, rilancia `lsblk` e guarda quale riga è sparita.

### 3. Scrivi muOS sulla scheda

```bash
git clone https://github.com/fdamore1984/mbr-anbernic
cd mbr-anbernic
scripts/make-sd.sh flash /dev/mmcblk0 ~/mbr-kit
```

Lo script mostra il disco e **cancella tutto quello che c'e' sopra** solo dopo che hai riscritto il nome del disco. Poi chiede la password di `sudo`. La scrittura dura qualche minuto.

Si rifiuta di andare avanti se il disco non e' rimovibile, se e' una singola partizione o se contiene il sistema.

### 4. Primo avvio nella console

1. Metti la scheda nell'Anbernic, nello slot **TF1**, e accendi.
2. Al primo avvio muOS allarga le partizioni fino a riempire la scheda e crea le sue cartelle: puo' metterci qualche minuto. Potrebbe anche chiederti lingua, data o fuso orario: rispondi pure.
3. Quando vedi il **menu principale di muOS**, spegni dal menu (non togliendo la scheda).
4. Rimetti la scheda nel computer.

### 5. Installa il kit

```bash
scripts/make-sd.sh setup ~/mbr-kit
```

Lo script:

1. riconosce le partizioni dalle etichette (`MustardOS`, `BOOT`, `ROOTFS`) e le monta;
2. copia giochi, copertine, anteprime con i brani, tema, collezione e suono di avvio;
3. mette il logo nella partizione di avvio;
4. con `sudo`, scrive le impostazioni di muOS nella partizione di sistema: kiosk, avvio sulla collezione, suoni, tema attivo ed emulatore di ogni cartella. Lascia `build/kit-rootfs-undo.sh` per tornare indietro;
5. smonta tutte le partizioni.

Quando dice "Scheda pronta", toglila e mettila nell'Anbernic. Se al primo avvio il tema non e' MBR Terminal, attivalo da Configuration → Customisation → Theme.

## Creare il kit

### Dalla scheda che funziona (consigliato)

```bash
python3 scripts/mbr.py export-kit --apply --image MustardOS_...img.gz   # crea ~/mbr-kit (cambia con --out)
```

Copia esattamente cio' che c'e' sulla scheda: i giochi della collezione con i file collegati (tracce dei CD, dischi, cartelle ScummVM), copertine, anteprime, tema, collezione, loghi, impostazioni ed emulatori assegnati. Conserva il kit su un disco esterno o su un cloud privato.

### Dai file sorgente, senza scheda

Serve se hai perso sia la scheda sia il kit. Prepara:

| Cosa | Formato |
|---|---|
| **Giochi** (`--roms`) | una cartella come `ROMS` di muOS: `<cartella>/<SISTEMA>/<file>`, con i nomi di `data/songs.json`. Vedi sotto i formati speciali |
| **Brani** (`--media`) | una cartella di file audio o video, chiamati `... [<video_id>].mp4` (come li salva un download da YouTube) oppure `NN - Titolo.mp3` (NN = numero del brano nella playlist) |
| **Logo di avvio** (`--logo`) | un'immagine; diventa anche il salvaschermo |
| **Logo di spegnimento** (`--outro`) | facoltativo |
| **Font** (`--font`) | `topaz.ttf` |

Formati speciali dei giochi, come li vuole muOS:

- **DOS** (`DOS/`): un `.zip` con il gioco e un `DOSBOX.BAT` che lo avvia (per esempio `C:` e `DOOM2.EXE`). I CD vanno nello zip come `.iso`;
- **ScummVM** (`SCUMMVM/`): un file `Nome.scummvm` che contiene l'identificativo ScummVM (`loom`, `monkey`, `zak`) e accanto la cartella `.Nome/` con i file del gioco;
- **piu' dischi** (`PS/`, `AMIGA/`): un `.m3u` con un disco per riga e i dischi in una sottocartella nascosta (`.Red Alert/`, `.Dune/`);
- **CD PlayStation**: `.cue` con i suoi `.bin` nella stessa cartella.

```bash
.venv/bin/python scripts/mbr.py build-kit --roms ROM --media BRANI \
    --logo logo_start.png --outro logo_outro.jpg --font topaz.ttf \
    --image MustardOS_...img.gz --apply
```

`build-kit` esegue in ordine `covers`, `install-covers`, `install-logo`, `install-sounds`, `install-theme`, `install-previews`, `install-names` e `install-kiosk`, usando il kit al posto della scheda. Aggiunge gli emulatori delle cartelle da `data/muos.json` (voce `cores`) e le impostazioni di muOS.

Il risultato e' uguale a quello di `export-kit`, con un'eccezione: i suoni di navigazione del menu vengono copiati dal tema "GB Dark" di muOS, che si trova solo su una scheda. Con una scheda muOS montata aggiungi `--base "GB Dark"`; senza, il menu resta muto e restano solo i suoni di avvio e spegnimento.

## Su un'altra Anbernic o con altri giochi

1. Monta la scheda e lancia `check`: elenca i giochi che non trova con quel nome esatto.
2. Correggi il campo `rom` in `data/songs.json` (sistema = nome della cartella in `ROMS`, file = nome esatto).
3. Per una cartella che non e' ancora in `data/muos.json`, aggiungi:
   - il nome del catalogo in `systems`;
   - l'emulatore in `cores`. Lo trovi in `share/info/content/<CARTELLA>/core.cfg` della partizione di sistema, dopo averla aperta una volta dall'esploratore di muOS.
4. Rilancia i comandi di [Uso](#uso), oppure `build-kit` e poi `make-sd.sh setup`.
5. Con un altro modello cambiano la risoluzione (il tema e' fatto per 640x480) e la misura delle copertine: lancia prima `inspect` e `theme-dump`.

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
