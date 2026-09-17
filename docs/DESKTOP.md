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

## Coach AI opzionale

Senza configurazione, tutte le funzioni locali restano disponibili e il Coach AI risulta
disattivato. Per abilitarlo nella prima versione creare `desktop-settings.json` nella cartella
dati personale:

```json
{
  "openai_api_key": "INSERIRE_LA_PROPRIA_CHIAVE",
  "openai_model": "gpt-5.4-mini"
}
```

La chiave viene letta localmente all'avvio, non è inserita nel database e non viene inviata al
browser. Una schermata Impostazioni interna sostituirà questo passaggio manuale prima della
prima release pubblica.

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
