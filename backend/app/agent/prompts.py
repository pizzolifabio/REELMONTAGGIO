"""Prompt dell'agente. Il contesto (skill, trascrizioni, timeline) viene costruito qui."""
import json
from typing import Any

from ..pipeline.edl import SCHEMA

EDITOR_SYSTEM = """Sei il montatore video di Reel Studio. Monti short verticali (Reels, Shorts, TikTok) a partire
da clip grezze, lavorando SOLO tramite una timeline JSON (EDL) che un renderer FFmpeg trasforma in video.

Regole tecniche:
- Rispondi esclusivamente con un oggetto JSON valido secondo lo schema fornito, in un blocco ```json.
- clips[].source è l'ID numerico di un asset video; in/out sono secondi nel video SORGENTE.
- Taglia sui confini delle parole usando i timestamp parola-per-parola: inizia ~0.05s prima della prima
  parola e termina ~0.10s dopo l'ultima, mai a metà parola.
- Elimina silenzi, false partenze, ripetizioni e frasi ripetute: tieni la versione migliore (di solito l'ultima).
- overlays[].start/end sono secondi nel video FINALE (dopo i tagli).
- I sottotitoli sono generati automaticamente dalla trascrizione: usa captions.corrections per correggere
  parole trascritte male e captions.emphasis per le parole chiave da evidenziare.
- Usa solo asset presenti nell'elenco fornito.
- Le skill di stile sono regole apprese dalle preferenze dell'utente: rispettale sempre, salvo che un
  feedback esplicito dica il contrario."""

LEARNING_SYSTEM = """Sei il modulo Self-Learning di Reel Studio. Ricevi i feedback dati dall'utente durante le
revisioni dei montaggi e i file di skill attuali. Il tuo compito è distillare REGOLE GENERALI e riutilizzabili
(stile, ritmo, sottotitoli, grafica, copy) e aggiornare i file di skill.

- Ignora richieste specifiche di un singolo video (es. "togli la frase sul prezzo") che non diventano regole.
- Una regola va scritta in modo operativo e misurabile quando possibile (es. "sottotitoli a position_y 0.70",
  "massimo 2 secondi senza cambio inquadratura o zoom").
- Se più feedback si contraddicono, prevale il più recente.
- Mantieni il formato Markdown dei file, non cancellare regole valide esistenti, unisci i duplicati.
- Rispondi solo con JSON in un blocco ```json:
  {"summary": "...", "changes": [{"path": "captions/rules.md", "reason": "...", "content": "<contenuto completo aggiornato>"}]}
- path è relativo alla cartella skills/ e deve terminare con .md. Includi solo i file che cambiano."""

CONTENT_SYSTEM = """Sei il content strategist di Reel Studio. Dal contenuto di un video crei:
1) un lead magnet (guida, checklist o mini-risorsa) che approfondisce davvero il tema del video, utile e
   concreto, non un riassunto;
2) la caption del post con hook iniziale e una CTA del tipo "Commenta PAROLA e ti mando la guida in DM";
3) una parola chiave breve (una parola, maiuscola, facile da scrivere) per il commento;
4) il messaggio DM che accompagna la risorsa.
Scrivi nella lingua del video. Rispondi solo con JSON in un blocco ```json."""


def _schema() -> str:
    return json.dumps(SCHEMA, ensure_ascii=False)


def _transcript_block(asset) -> str:
    t = asset.transcript or {}
    lines = [f"### Asset video {asset.id} — \"{asset.label or asset.filename}\" ({asset.duration:.2f}s, "
             f"{asset.width}x{asset.height}, audio: {'sì' if asset.has_audio else 'no'})"]
    if not t.get("words"):
        lines.append("(nessun parlato rilevato)")
        return "\n".join(lines)
    lines.append("Segmenti:")
    lines += [f"  [{s['s']:.2f}–{s['e']:.2f}] {s['text']}" for s in t.get("segments", [])]
    lines.append("Parole (inizio|fine|parola):")
    lines += [f"  {w['s']:.2f}|{w['e']:.2f}|{w['w']}" for w in t["words"]]
    return "\n".join(lines)


def _assets_block(videos, images, music) -> str:
    out = ["## Asset video", *(_transcript_block(a) for a in videos)]
    out.append("\n## Immagini disponibili (per overlays kind=image)")
    out += [f"- {a.id}: {a.label or a.filename}" for a in images] or ["(nessuna)"]
    out.append("\n## Musica disponibile (music.asset)")
    out += [f"- {a.id}: {a.label or a.filename} ({a.duration:.0f}s)" for a in music] or ["(nessuna)"]
    return "\n".join(out)


def initial_edit(project, videos, images, music, skills: str, preferred_music: int | None) -> str:
    return f"""# Nuovo montaggio: {project.name}

## Skill di stile apprese
{skills}

## Script di partenza
{project.script or "(nessuno: deduci la struttura migliore dal parlato)"}

## Indicazioni per questo video
{project.brief or "(nessuna)"}

{_assets_block(videos, images, music)}

Musica scelta dall'utente: {preferred_music if preferred_music else "nessuna preferenza"}

## Schema della timeline
{_schema()}

Crea la timeline del montaggio. Ordina le clip seguendo lo script (se presente), apri con l'hook più forte,
elimina tutto ciò che è superfluo. Rispondi solo con il JSON della timeline."""


def apply_feedback(project, current_edl: dict[str, Any], feedbacks, videos, images, music, skills: str) -> str:
    fb_lines = []
    for fb in feedbacks:
        extra = f" (asset allegato: {fb.asset_id})" if fb.asset_id else ""
        fb_lines.append(f"- al secondo {fb.timestamp:.2f} del video finale: \"{fb.text}\"{extra}")
    return f"""# Revisione montaggio: {project.name}

## Skill di stile apprese
{skills}

## Timeline attuale
```json
{json.dumps(current_edl, ensure_ascii=False, indent=1)}
```

## Feedback dell'utente (timestamp sul video finale attuale)
{chr(10).join(fb_lines)}

{_assets_block(videos, images, music)}

## Schema della timeline
{_schema()}

Applica TUTTI i feedback modificando la timeline il meno possibile. Per individuare cosa c'è al secondo
indicato, calcola la posizione sommando le durate delle clip (out-in) nell'ordine. Rispondi solo con il JSON
completo della nuova timeline, con in più un campo di primo livello "_note" che descrive in una frase cosa
hai cambiato."""


def self_learning(feedback_rows: list[dict[str, Any]], skill_files: dict[str, str]) -> str:
    files = "\n\n".join(f"### skills/{path}\n```markdown\n{content}\n```" for path, content in skill_files.items())
    fb = "\n".join(
        f"- [{r['date']}] progetto \"{r['project']}\", sec {r['timestamp']:.1f}: \"{r['text']}\"" for r in feedback_rows
    )
    return f"""## Feedback raccolti (dal più vecchio al più recente)
{fb}

## File di skill attuali
{files or "(nessuno)"}

Proponi gli aggiornamenti alle skill."""


def content(project, transcript_text: str, skills: str) -> str:
    return f"""## Skill (copywriting e lead magnet)
{skills}

## Video: {project.name}
Script: {project.script or "(nessuno)"}

Trascrizione del montaggio finale:
{transcript_text}

Rispondi con questo JSON:
{{
  "title": "titolo breve del contenuto",
  "keyword": "PAROLA",
  "caption": "caption completa con hook e CTA che cita la keyword",
  "hashtags": "#tag1 #tag2 ...",
  "dm_message": "messaggio che accompagna il link alla risorsa",
  "lead_magnet": {{
    "type": "guida | checklist | template | cheat sheet",
    "title": "...",
    "subtitle": "...",
    "intro": "paragrafo introduttivo",
    "sections": [{{"heading": "...", "body": "testo (opzionale)", "items": ["punto 1", "punto 2"]}}],
    "closing": "chiusura con invito a seguire la pagina"
  }}
}}"""
