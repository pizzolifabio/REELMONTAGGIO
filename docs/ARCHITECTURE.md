# Reel Studio — Architettura

## Principio guida: la timeline (EDL) è l'unica fonte di verità

L'agente non scrive comandi FFmpeg. Produce e modifica una timeline JSON
(`backend/app/pipeline/timeline.schema.json`) che un renderer deterministico compila in un solo comando FFmpeg.

- **Feedback a timestamp = modifica della timeline.** L'agente riceve la timeline attuale e i feedback, e restituisce la nuova timeline.
- **Ogni revisione è una versione**: si può confrontare, ripristinare o modificare a mano (Studio → Versioni → Modifica timeline).
- **Validazione prima del render.** Schema, durate, asset esistenti e overlay entro la durata vengono controllati. Se qualcosa non va, l'errore torna all'agente, che corregge una volta.
- **I sottotitoli non li scrive l'agente.** Vengono dalla trascrizione parola per parola, rimappata sui tagli. L'agente può solo correggere parole (`captions.corrections`), evidenziarle (`emphasis`) e cambiarne lo stile.

## Flusso

```
Upload clip ──► ffprobe + miniatura
     │
     ▼  job "process_project" (worker interno)
faster-whisper (timestamp per parola) ──► agente: timeline v1 ──► validazione ──► render
     │
     ▼
Studio: feedback a timestamp ──► job "apply_feedback" ──► timeline vN ──► render
     │
     ├─► Self-Learning: feedback ──► proposta di modifica a skills/*.md ──► approvazione ──► scrittura (+ backup)
     ├─► Contenuti: trascrizione finale ──► lead magnet (HTML → PDF con Chrome) + caption + keyword
     └─► Calendario: scheduler (ogni 20s) ──► job "publish" ──► Instagram / YouTube / TikTok
                                                              │
Webhook Instagram (tunnel) ──► commento con keyword ──► private reply con quick reply
                           └─► messaggio/quick reply ──► is_user_follow_business ──► risorsa o richiesta follow
```

## Stack

| Livello | Scelta | Motivo |
|---|---|---|
| Interfaccia | Next.js 16 (App Router, Cache Components), Tailwind 4, lucide | Componenti client in stile Apple HIG, modalità chiara e scura |
| API e worker | FastAPI, thread worker e scheduler interni | Un solo processo, nessun Redis o Docker per uso personale |
| Dati | SQLite (WAL) + file in `data/media` | Zero configurazione e backup facile |
| Trascrizione | faster-whisper `large-v3-turbo` int8 | Locale e gratuita, timestamp per parola |
| Render | FFmpeg (`ffmpeg-full`, libass) | Sottotitoli karaoke ASS, zoompan, overlay, sidechain ducking, loudnorm |
| Agente | `claude -p` senza strumenti (`--tools ""`), oppure Codex o API | Usa il tuo abbonamento; i provider sono intercambiabili da `.env` |
| PDF | Chrome headless `--print-to-pdf` | Nessuna dipendenza aggiuntiva |

## Vincoli delle piattaforme

- **Instagram, pubblicazione**: con Instagram Login l'upload diretto (resumable) non è disponibile, perché è riservato alle app con Facebook Login. Il video viene quindi servito via tunnel da `/public/renders/...`, con un URL firmato HMAC.
- **Instagram, DM**: è consentita una sola private reply per commento, entro 7 giorni. `is_user_follow_business` si può leggere solo dopo che l'utente ha scritto nella conversazione, e per questo serve il pulsante quick reply. Lo stesso commento non viene mai gestito due volte (dedup su `comment_id`).
- **YouTube**: i video sono privati finché l'app non è verificata da Google; ogni upload costa circa 1.600 unità di quota.
- **TikTok**: un'app non verificata pubblica solo come `SELF_ONLY`. Il sistema lo rileva e lo segnala nel post.

## Sicurezza (uso personale)

- Dal tunnel pubblico sono raggiungibili solo webhook, pagine delle risorse, video firmati e callback OAuth: un middleware blocca il resto se la richiesta non arriva da `localhost`.
- I webhook Meta vengono verificati con la firma `X-Hub-Signature-256` quando è impostato `IG_APP_SECRET`.
- I token dei social restano nel database SQLite locale.
