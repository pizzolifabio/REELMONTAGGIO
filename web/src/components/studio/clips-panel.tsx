"use client";

import { useState } from "react";
import { Check, Film, Music, Trash2 } from "lucide-react";
import type { Asset, ProjectDetail } from "@/lib/api";
import { api, upload } from "@/lib/api";
import { formatTime, useResource } from "@/lib/hooks";
import { DropZone } from "../dropzone";
import { Button, Field, IconButton, Pill, Progress, Section, Select, TextArea, useAction } from "../ui";

export function ClipsPanel({ project, onChanged }: { project: ProjectDetail; onChanged: () => void }) {
  const [script, setScript] = useState(project.script);
  const [brief, setBrief] = useState(project.brief);
  const [progress, setProgress] = useState<number | null>(null);
  const [openTranscript, setOpenTranscript] = useState<number | null>(null);
  const { busy, run } = useAction();
  const library = useResource<Asset[]>("/api/library");
  const music = library.data?.filter((a) => a.kind === "music") ?? [];
  const videos = project.assets.filter((a) => a.kind === "video");

  const add = (files: File[]) => run("upload", async () => {
    setProgress(0);
    await upload(`/api/projects/${project.id}/assets`, files, setProgress);
    setProgress(null);
    onChanged();
  });

  return (
    <div>
      <Section title={`Clip · ${videos.length}`} footer="Il primo montaggio usa tutte le clip. Dopo averne aggiunte altre, usa “Rimonta da zero”.">
        {videos.map((a) => (
          <div key={a.id} className="border-b border-separator last:border-0">
            <div className="flex items-center gap-3 px-4 py-2.5">
              {a.thumb_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={a.thumb_url} alt="" className="h-14 w-9 rounded-md bg-fill object-cover" />
              ) : <div className="flex h-14 w-9 items-center justify-center rounded-md bg-fill"><Film className="size-4 text-label-3" /></div>}
              <div className="min-w-0 flex-1">
                <div className="truncate text-[14px] font-medium">{a.label}</div>
                <div className="mt-0.5 flex items-center gap-2 text-[12px] text-label-2">
                  <span className="tabular">{formatTime(a.duration)}</span>
                  <span>{a.width}×{a.height}</span>
                  {a.transcribed ? <Pill color="green"><Check className="size-3" />trascritta</Pill> : <Pill>da trascrivere</Pill>}
                  <span className="text-label-3">ID {a.id}</span>
                </div>
              </div>
              {a.transcript && (
                <Button variant="plain" size="sm" onClick={() => setOpenTranscript(openTranscript === a.id ? null : a.id)}>
                  {openTranscript === a.id ? "Chiudi" : "Testo"}
                </Button>
              )}
              <IconButton label="Elimina clip" onClick={() => confirm(`Eliminare ${a.label}?`) && run("del", async () => { await api(`/api/assets/${a.id}`, { method: "DELETE" }); onChanged(); })} className="hover:text-red">
                <Trash2 className="size-4" />
              </IconButton>
            </div>
            {openTranscript === a.id && a.transcript && (
              <div className="mx-4 mb-3 max-h-48 overflow-y-auto rounded-lg bg-fill/60 p-3 text-[13px] leading-relaxed">
                {a.transcript.segments.map((s, i) => (
                  <p key={i}><span className="mr-2 font-mono text-[11px] text-label-3 tabular">{formatTime(s.s, true)}</span>{s.text}</p>
                ))}
                {!a.transcript.segments.length && <p className="text-label-2">Nessun parlato rilevato.</p>}
              </div>
            )}
          </div>
        ))}
        <div className="p-3">
          <DropZone compact accept="video/*" title="Aggiungi clip" onFiles={add} />
          {progress !== null && <Progress className="mt-2" value={progress} />}
        </div>
      </Section>

      <Section title="Musica di sottofondo" footer="La musica viene abbassata automaticamente quando parli (ducking). Carica le tracce nella Libreria.">
        <div className="p-3">
          <Select
            value={project.music_asset_id ?? ""}
            onChange={(e) => run("music", async () => {
              await api(`/api/projects/${project.id}`, { method: "PATCH", json: { music_asset_id: e.target.value ? Number(e.target.value) : null } });
              onChanged();
            }, "Preferenza salvata: verrà usata al prossimo montaggio")}
          >
            <option value="">Scelta dall'agente</option>
            {music.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
          </Select>
          {!music.length && <p className="mt-2 flex items-center gap-1.5 text-[12px] text-label-2"><Music className="size-3.5" />Nessuna traccia in libreria.</p>}
        </div>
      </Section>

      <Section title="Script e indicazioni">
        <div className="space-y-3 p-4">
          <Field label="Script"><TextArea value={script} onChange={(e) => setScript(e.target.value)} /></Field>
          <Field label="Indicazioni per il montaggio"><TextArea value={brief} onChange={(e) => setBrief(e.target.value)} className="min-h-[64px]" /></Field>
          <div className="flex justify-end">
            <Button size="sm" variant="tinted" loading={busy === "save"} onClick={() => run("save", async () => {
              await api(`/api/projects/${project.id}`, { method: "PATCH", json: { script, brief } });
              onChanged();
            }, "Salvato")}>Salva</Button>
          </div>
        </div>
      </Section>
    </div>
  );
}
