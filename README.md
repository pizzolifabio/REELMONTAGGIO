# Reel Studio

Piattaforma personale che:

- monta automaticamente i tuoi video grezzi;
- impara dai tuoi feedback;
- crea lead magnet e caption;
- gestisce i DM da commento con verifica del follow;
- pubblica su Instagram Reels, YouTube Shorts e TikTok.

Gira interamente sul tuo Mac. L'agente usa la tua sessione di Claude Code (`claude -p`), quindi non serve una API key.

## Avvio

Requisiti: Homebrew, Python 3.12+, Node 20+, Claude Code con il login già fatto.

```bash
brew install ffmpeg-full cloudflared
./scripts/dev.sh
```

Apri http://localhost:3000. Al primo avvio lo script:

- crea `.env` partendo da `.env.example`;
- installa le dipendenze di backend e interfaccia.

> Avvia `scripts/dev.sh` da un normale Terminale. `claude -p` si rifiuta di partire se lanciato dall'interno di un'altra sessione di Claude Code.

La prima trascrizione scarica il modello Whisper (`large-v3-turbo`, circa 1,6 GB).

## Come si usa

1. **Progetti → Nuovo progetto.** Carica da 1 a 10 clip, più lo script facoltativo, e scegli "Carica e monta". Il sistema poi:
   - trascrive ogni parola con il suo timestamp;
   - fa scrivere all'agente la timeline del montaggio;
   - renderizza con FFmpeg: tagli, zoom, sottotitoli animati, overlay, musica con ducking e volume normalizzato a −14 LUFS.
2. **Studio.** Metti in pausa nel punto giusto e premi **C** (o "Feedback qui"), poi scrivi la modifica a parole. Se serve un logo nuovo, puoi allegare un'immagine. "Applica e rigenera" produce una nuova versione.
3. **Self-Learning.** L'agente trasforma i feedback accumulati in regole generali nei file `skills/*.md`. Vedi le modifiche riga per riga e approvi solo quello che vuoi; prima di ogni modifica viene salvata una copia in `data/skills_history/`.
4. **Contenuti** (scheda dello Studio). Genera:
   - un lead magnet in PDF, impaginato in stile Apple;
   - caption e hashtag;
   - la parola chiave e il messaggio DM.
5. **Automazioni DM.** Chi commenta la parola chiave riceve:
   - una risposta privata con il pulsante "Inviamela";
   - poi la verifica del follow;
   - infine il link alla risorsa, oppure la richiesta di seguire la pagina.
6. **Calendario.** Programma il video su una o più piattaforme. Lo scheduler gira finché Reel Studio è acceso.

## Collegare i social

### Tunnel pubblico (serve per Instagram)

Instagram deve poter raggiungere il tuo Mac per tre cose:

- inviare i webhook dei commenti;
- scaricare il video da pubblicare;
- far aprire i link ai lead magnet.

```bash
./scripts/dev.sh --tunnel
```

Copia l'URL `https://….trycloudflare.com` in `PUBLIC_BASE_URL` nel file `.env` e riavvia. L'URL di un tunnel rapido cambia a ogni avvio; per averne uno fisso crea un *named tunnel* Cloudflare con un tuo dominio.

Dal tunnel sono raggiungibili solo `/webhooks`, `/r` (pagine delle risorse), `/public` (video firmati) e le callback OAuth. Il resto dell'API risponde solo su `localhost`.

### Instagram

1. Su developers.facebook.com crea un'app con il prodotto **Instagram → API setup with Instagram login**.
2. Il tuo account Instagram deve essere Professional (Creator o Business).
3. Inserisci `IG_APP_ID` e `IG_APP_SECRET` in `.env`.
4. Collega l'account in **Impostazioni**:
   - **Token**: incolla il token generato nella dashboard (il metodo più rapido);
   - **Collega**: usa OAuth, con redirect `PUBLIC_BASE_URL/oauth/instagram/callback`.
5. **Webhooks**: callback URL e verify token li trovi in Impostazioni. Iscriviti ai campi `comments` e `messages`.
6. Finché l'app è in modalità sviluppo, funziona solo con gli account aggiunti come tester. Per uso personale col tuo account basta questo.

### YouTube

1. Su Google Cloud abilita **YouTube Data API v3**.
2. Crea un client OAuth di tipo "Web application" con redirect `http://localhost:8000/oauth/youtube/callback`.
3. Inserisci `GOOGLE_CLIENT_ID` e `GOOGLE_CLIENT_SECRET`.

Finché Google non verifica l'app, i video caricati restano privati. Ogni upload consuma circa 1.600 delle 10.000 unità di quota giornaliere.

### TikTok

1. Su developers.tiktok.com crea un'app con **Login Kit** e **Content Posting API** (Direct Post).
2. Redirect: `PUBLIC_BASE_URL/oauth/tiktok/callback`.

Finché TikTok non approva l'app, i post sono visibili solo a te.

## Struttura

```
reel-studio/
├── backend/              FastAPI + worker interno (SQLite, file locali)
│   ├── app/pipeline/     schema timeline, trascrizione, sottotitoli ASS, render FFmpeg
│   ├── app/agent/        runner headless (claude -p / codex / API) e prompt
│   ├── app/social/       Instagram, YouTube, TikTok, automazioni DM, pubblicazione
│   ├── app/routers/      API REST
│   └── tests/            pipeline reale con FFmpeg + flusso end-to-end con agente simulato
├── web/                  Next.js 16 + Tailwind 4, design in stile Apple
├── skills/               memoria del Self-Learning (Markdown, versionabile con git)
├── data/                 database, media, render (creato all'avvio, escluso da git)
└── scripts/dev.sh
```

Dettagli tecnici in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Test

```bash
cd backend && .venv/bin/python -m pytest -q
```
