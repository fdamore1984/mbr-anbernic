# mbr-anbernic

Trasforma una Anbernic con muOS in una console a tema **Master Boot Record**: sulla scheda restano visibili solo i giochi abbinati ai brani della playlist WAREZ, ognuno con la copertina presa dalla miniatura del video del suo brano. Tutti gli altri giochi vengono nascosti, mai cancellati.

Pensato per RG35XX Plus con muOS 2606, preparato da una Steam Deck in modalità desktop. Per ripetere l'operazione su un'altra Anbernic bastano gli stessi comandi.

## Stato

| Parte | Stato |
|---|---|
| Elenco dei 42 brani, ID video e gioco scelto (30 abbinati, 12 senza gioco) | fatto, in `data/songs.json` |
| `check`, `hide`, `restore`, `covers`, `install-covers` | provati su una scheda simulata con 175 file |
| Provato su muOS reale | **non ancora** |
| Download delle miniature da YouTube | **non ancora provato** (nei test erano immagini finte) |
| Nomi delle cartelle del catalogo muOS (`data/muos.json`) | verificati su muOS 2606 |
| Pacchetto del tema (font Topaz, colori del sito) | da fare dopo `inspect` |
| Musica del brano in riproduzione automatica | da fare, serve una fonte audio legittima |

## Cosa serve

- Python 3.8 o superiore (c'è già su SteamOS)
- Pillow, solo per `covers`: `pip install --user pillow`
- la scheda SD di muOS montata (default `/run/media/deck/MustardOS`, cambiabile con `--sd` o con la variabile `MBR_SD`)

## Uso

Tutti i comandi che modificano la scheda fanno prima una simulazione: per eseguire davvero si aggiunge `--apply`.

```bash
git clone https://github.com/fdamore1984/mbr-anbernic
cd mbr-anbernic

python3 scripts/mbr.py list              # brani e giochi abbinati
python3 scripts/mbr.py inspect           # descrive la struttura di muOS sulla scheda
python3 scripts/mbr.py check             # i 30 giochi scelti ci sono tutti?

python3 scripts/mbr.py hide              # simulazione: cosa verrebbe nascosto
python3 scripts/mbr.py hide --apply      # sposta gli altri giochi in ROMS_HIDDEN

python3 scripts/mbr.py covers --only-kept          # scarica le miniature, crea i PNG in build/covers
python3 scripts/mbr.py install-covers              # simulazione
python3 scripts/mbr.py install-covers --apply      # copia i PNG nel catalogo di muOS

python3 scripts/mbr.py theme-dump                  # elenca i temi installati
python3 scripts/mbr.py theme-dump --name "GB Dark" # descrive un tema da usare come modello (build/theme-dump.txt)

python3 scripts/mbr.py restore --apply   # rimette tutto com'era
```

`hide` sposta i file in `ROMS_HIDDEN/<sistema>/` sulla stessa scheda (spostamento istantaneo) e ricorda cosa ha spostato in `ROMS_HIDDEN/.mbr-hidden.json`. Si rifiuta di procedere se uno dei giochi da tenere non si trova.

## Su un'altra Anbernic

1. Monta la scheda e lancia `check`: elenca i giochi che non trova con quel nome esatto.
2. Se i nomi dei file sono diversi, correggi il campo `rom` in `data/songs.json`.
3. Lancia `inspect` e confronta con `data/muos.json`, poi procedi con `hide`, `covers` e `install-covers`.

`covers` accetta `--size` (default `282x216`, la misura delle copertine che muOS 2606 ha già nel catalogo) e `--fit cover|contain`.

## Cosa non è nel repository

- Le ROM: vanno tenute solo se possiedi i giochi originali.
- Il font Topaz: lo usa il sito di MBR; per uso personale si scarica da `https://mbrserver.com/topaz.ttf`. È ignorato da git.
- Le miniature dei video e l'audio: appartengono all'artista, vengono scaricate in `build/` sul tuo dispositivo e non vanno ridistribuite.
- Il tema è ispirato ai colori del sito (`theme/palette.json`) e non contiene loghi o copertine dell'artista.
