# Running Dashboard Desktop

La versione desktop esegue FastAPI esclusivamente su `127.0.0.1` e lo mostra in una finestra
nativa. Non richiede Docker e non espone il database sulla rete locale.

## Dove salva i dati

- macOS: `~/Library/Application Support/Running Dashboard/`
- Windows: `%LOCALAPPDATA%\Running Dashboard\`

La cartella contiene configurazione, log e due archivi completamente separati:

- `profiles/demo/`: dati dimostrativi;
- `profiles/user/`: dati reali dell'utente.

Gli
aggiornamenti dell'applicazione non devono sostituire questa cartella.

## Selezione del profilo

All'avvio l'app propone **Demo** e **Il mio profilo**. Non viene richiesta una password: è un
selettore locale, non un meccanismo di sicurezza. Il pulsante fisso in basso a destra consente di
cambiare profilo. Nella versione desktop il collegamento HomeHub non viene caricato.

## Tema modificabile

Al primo avvio viene creato `theme.json` nella cartella dati. Il campo `preset` accetta `running`, `community-violet` o `borgorun`; la mappa `colors` può sovrascrivere `background`, `panel`, `surface`, `surface_alt`, `line`, `muted`, `text`, `primary`, `secondary`, `warning`, `danger` e `glow` con valori esadecimali. Salvare il file e ricaricare la pagina o riavviare l’app.

```json
{
  "preset": "community-violet",
  "colors": {"primary": "#7c3aed", "secondary": "#06b6d4"}
}
```

## Running Community

Con un profilo community attivo, la pagina **Gare** mostra anche gare e allenamenti pubblicati nel feed dedicato. Le scelte **Interessato** e **Partecipo** restano nel profilo locale e non vengono inviate online. L'ultima copia valida del feed resta disponibile offline.

La configurazione può essere esplicitata o personalizzata in `theme.json`:

```json
{
  "preset": "community-violet",
  "community": {
    "enabled": true,
    "feed_url": "https://leobarra.it/data/running-community.json",
    "name": "Running Community"
  },
  "colors": {}
}
```

## Integrazioni opzionali

Il pulsante **Integrazioni** della versione desktop permette di configurare Intervals.icu e il
Coach AI senza modificare file manualmente. Athlete ID, API key e modello vengono conservati in
`desktop-settings.json` nella cartella dati personale, con permessi limitati all'utente. Le chiavi
non vengono restituite al browser, inserite nel database o incluse nelle esportazioni.

Lo stesso pannello accetta un codice community. Un codice valido abilita il tema e le funzioni
dedicate; il codice viene verificato localmente e non viene salvato nel file delle impostazioni.

## Build locale macOS

```bash
./scripts/build-desktop.sh
open "dist/Running Dashboard.app"
```

## Build locale Windows

Da PowerShell:

```powershell
.\scripts\build-desktop.ps1
```

Il risultato è una cartella portabile `dist\RunningDashboard`; non serve un installer.

## Release multipiattaforma

PyInstaller deve compilare sul sistema operativo di destinazione. Il workflow
`.github/workflows/desktop-build.yml` produce separatamente il pacchetto macOS ARM64 e quello
Windows x64 quando viene avviato manualmente o quando viene pubblicato un tag `v*`.
