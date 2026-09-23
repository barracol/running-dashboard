# Running Dashboard

[![Desktop builds](https://github.com/barracol/running-dashboard/actions/workflows/desktop-build.yml/badge.svg)](https://github.com/barracol/running-dashboard/actions/workflows/desktop-build.yml)

MVP personale e leggero per registrare e visualizzare attività sportive su Raspberry Pi. Usa FastAPI, SQLite, HTML/CSS e Chart.js.


### Sincronizzazione Intervals.icu

La dashboard può leggere e importare le attività ricevute da Garmin tramite Intervals.icu. Imposta `INTERVALS_ATHLETE_ID` e `INTERVALS_API_KEY` nell’ambiente del server; la chiave non va salvata nel repository. Il flusso mostra prima un’anteprima e importa soltanto le attività nuove, usando l’ID Intervals.icu e un controllo su data, sport, distanza e durata per evitare duplicati.

## Funzioni

- CRUD di attività con data, distanza in metri, durata in secondi, calorie, FC media, tipo e note.
- Dashboard multisport responsive con filtro per disciplina, riepilogo, diario e grafici settimanali, mensili e annuali.
- Bacheca dei tempi migliori di corsa su 10 km, mezza maratona e maratona, con tolleranza GPS del 3%.
- Pagina dettaglio attività con metriche, metadati Strava, note, download originale, tracce GPX/FIT,
  mappa interattiva OpenStreetMap, profilo altimetrico e grafici di FC, passo/velocità, cadenza e potenza.
- Archivio ufficiale separato dai dati manuali: gli import Strava sono marcati `verified`.
- Sezione Pianificazione con diario draft, trend settimanale e calendario degli allenamenti programmati.
- Esportazione CSV completa degli allenamenti draft e generatore PNG trasparente distanza/passo.
- Archivio delle scarpe da running con foto, soglia chilometrica, carosello e stato di usura.
- Associazione delle scarpe alle attività ufficiali e draft, con ricalcolo automatico dei km percorsi.
- Planning Gare con costi, luoghi, stato d'iscrizione e finestra mobile dal mese corrente ai 9 successivi.
- Diario smart scale con misurazioni corporee e grafico a metrica selezionabile.
- Filtri testuali per colonna sull'intero archivio delle attività ufficiali.
- Libreria Esercizi estendibile con schede Markdown dedicate e tavole dimostrative realistiche.
- Promemoria documenti sportivi con numero e scadenza RunCard e scadenza del certificato medico.
- Migrazioni SQLite automatiche all'avvio.
- Staging di file `.fit`/`.gpx` originali, limite 25 MB e deduplicazione SHA-256. Il parsing è volutamente predisposto ma non incluso nell'MVP.
- Docker multi-arch compatibile con Raspberry Pi 64 bit, cartella `data/` persistente e portabile, healthcheck e backup.

## Avvio locale

Richiede Python 3.11+.

```bash
make install
make seed
make run
```

Aprire `http://localhost:8000`. Documentazione API: `http://localhost:8000/docs`.

Test:

```bash
make test
```

## Applicazione desktop macOS e Windows

Il progetto include un launcher desktop e una configurazione PyInstaller. La versione desktop
usa una finestra nativa, avvia il server soltanto su localhost e conserva database e upload nella
cartella personale dell'utente. Può funzionare senza Coach AI; la relativa chiave è opzionale.

Istruzioni di build, percorsi dati e configurazione: [docs/DESKTOP.md](docs/DESKTOP.md).

Il codice è distribuito con licenza [MIT](LICENSE). Database, attività, upload, backup e chiavi API
restano locali e sono esclusi dal repository.

### Esportazione e grafico degli allenamenti Draft

Nella pagina **Pianificazione**, sotto “Attività inserite manualmente”, usare **Esporta CSV**.
Il file contiene distanza, durata, passo, velocità, scarpa e note ed è compatibile con Excel.

Per generare un grafico PNG trasparente, installare una volta la dipendenza opzionale e avviare:

```bash
python3 -m pip install -r requirements-plot.txt
python3 scripts/plot_draft_workouts.py allenamenti-draft-2026-08-30.csv \
  --output andamento-draft.png \
  --title "AGOSTO · ALLENAMENTI"
```

Il PNG raggruppa automaticamente gli allenamenti per settimana: mostra i chilometri totali e il
passo medio ponderato sulla distanza. Usa testo chiaro, distanza verde lime e passo turchese,
quindi può essere sovrapposto direttamente a un template scuro. Lo script riconosce CSV separati
con `;`, `,` o tabulazioni.

Importazione di uno o più archivi Strava già estratti (prima in anteprima, poi realmente):

```bash
.venv/bin/python -m scripts.import_strava --dry-run /percorso/export_account_1 /percorso/export_account_2
.venv/bin/python -m scripts.import_strava /percorso/export_account_1 /percorso/export_account_2
```

L'importatore riconosce CSV Strava in italiano e inglese, conserva gli originali compressi FIT/GPX,
mappa le discipline e può essere rilanciato senza creare duplicati.

## Raspberry Pi con Docker Compose

Su Raspberry Pi OS 64 bit con Docker e plugin Compose:

```bash
git clone <URL-DEL-REPOSITORY> running-dashboard
cd running-dashboard
mkdir -p backups
docker compose up -d --build
docker compose exec dashboard python -m scripts.seed_demo  # facoltativo
```

### Coach AI

La pagina **Pianificazione** può analizzare le ultime otto settimane, le gare confermate,
le scarpe attive e gli allenamenti già programmati. Mostra sempre un'anteprima: nessuna
seduta viene scritta nel planning senza una conferma esplicita.

Creare una chiave API OpenAI e configurarla esclusivamente sul server:

```bash
cp .env.example .env
nano .env
docker compose up -d --build
```

La chiave non viene mai inviata al browser né salvata nel database. Il modello predefinito
è `gpt-5.4-mini` e può essere cambiato tramite `RUNNING_OPENAI_MODEL`. Il Coach invia
all'API un riepilogo minimizzato, non il file SQLite e non i file originali FIT/GPX.

Il bind `8000:8000` rende la dashboard raggiungibile dai dispositivi della stessa rete locale. Non inoltrare la porta sul router. Per limitarla al solo host, usare `127.0.0.1:8000:8000`.

### Accesso remoto futuro con Tailscale

Installare Tailscale sull'host Raspberry e mantenere il servizio legato a localhost. Pubblicarlo solo nella tailnet con Tailscale Serve:

```bash
sudo tailscale serve --bg http://127.0.0.1:8000
```

Verificare il comando e le policy ACL con la versione Tailscale installata. Non è necessaria alcuna porta pubblica o regola di port forwarding.

## Dati, import e backup

La cartella `data/` contiene `running.db` e `uploads/` ed è montata nel container come `/data`. I file originali sono salvati col proprio SHA-256; il nome originale resta nel database. L'endpoint `POST /api/import` conserva FIT/GPX e crea una prima attività usando data, distanza e durata passate come query parameter.

Backup manuale consistente (SQLite `.backup` più archivio degli upload):

```bash
make backup
```

I file finiscono in `./backups` e quelli oltre 30 giorni vengono eliminati. Automatizzare sull'host, per esempio ogni notte alle 03:15:

```cron
15 3 * * * cd /opt/running-dashboard && /usr/bin/docker compose --profile backup run --rm backup >> /var/log/running-dashboard-backup.log 2>&1
```

Copiare regolarmente `backups/` su un altro dispositivo. Per ripristinare: fermare il container, sostituire `data/running.db` con il backup scelto, estrarre l'archivio upload in `data/uploads/` e riavviare.

## API principali

- `GET/POST /api/activities`
- `GET/PATCH/DELETE /api/activities/{id}`
- `GET /api/activities/{id}/detail`
- `GET /api/activities/{id}/original`
- `GET /api/stats/summary`
- `GET /api/stats/chart?period=week|month|year`
- `GET /api/stats/sports`
- `GET /api/stats/personal-bests`
- `GET/POST /api/drafts` e `PATCH/DELETE /api/drafts/{id}`
- `GET /api/drafts/export.csv`
- `GET /api/drafts/trend`
- `GET/POST /api/planned-workouts` e `PATCH/DELETE /api/planned-workouts/{id}`
- `GET /api/coach/status`, `POST /api/coach/plan`, `POST /api/coach/accept`
- `GET/POST /api/planned-races` e `PATCH/DELETE /api/planned-races/{id}`
- `GET/POST /api/scale-entries` e `PATCH/DELETE /api/scale-entries/{id}`
- `POST /api/import`
- `GET /health`

## Limiti e prossimi passi

L'app è pensata per un solo utente e non include autenticazione. Prima di un accesso condiviso aggiungere autenticazione o applicarla via reverse proxy/Tailscale. Prossimi incrementi naturali: parser FIT/GPX, metadati GPS, esportazione CSV e aggiornamenti Chart.js vendorizzati per uso completamente offline.
