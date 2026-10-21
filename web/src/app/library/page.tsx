"use client";

import { useState } from "react";
import { Images, Music, Trash2 } from "lucide-react";
import { DropZone } from "@/components/dropzone";
import { EmptyState, IconButton, Input, PageHeader, Progress, Section, Segmented, Spinner, useAction } from "@/components/ui";
import { api, upload, type Asset } from "@/lib/api";
import { formatTime, useResource } from "@/lib/hooks";

export default function LibraryPage() {
  const { data, loading, reload } = useResource<Asset[]>("/api/library");
  const [kind, setKind] = useState<"image" | "music">("image");
  const [progress, setProgress] = useState<number | null>(null);
  const { run } = useAction();
  const items = data?.filter((a) => a.kind === kind) ?? [];

  const add = (files: File[]) => run("up", async () => {
    setProgress(0);
    try { await upload("/api/library", files, setProgress); } finally { setProgress(null); }
    reload();
  }, "Caricato");

  const rename = (a: Asset, label: string) => label !== a.label && run("r", async () => { await api(`/api/assets/${a.id}`, { method: "PATCH", json: { label } }); reload(); });
  const remove = (a: Asset) => confirm(`Eliminare ${a.label}?`) && run("d", async () => { await api(`/api/assets/${a.id}`, { method: "DELETE" }); reload(); });

  return (
    <>
      <PageHeader title="Libreria" subtitle="Loghi, grafiche e musica disponibili all'agente in tutti i montaggi. Dai nomi chiari: l'agente li sceglie leggendoli." />
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <Segmented value={kind} onChange={setKind} options={[{ value: "image", label: "Immagini e loghi" }, { value: "music", label: "Musica" }]} />
      </div>
      <div className="mb-6">
        <DropZone
          accept={kind === "image" ? "image/png,image/jpeg,image/webp" : "audio/*"}
          title={kind === "image" ? "Trascina loghi o grafiche (PNG trasparente consigliato)" : "Trascina tracce musicali"}
          hint={kind === "image" ? "PNG, JPG, WEBP" : "MP3, M4A, WAV"}
          onFiles={add}
        />
        {progress !== null && <Progress className="mt-2" value={progress} />}
      </div>
      {loading ? <Spinner /> : !items.length ? (
        <EmptyState icon={kind === "image" ? <Images /> : <Music />} title="Ancora vuota" />
      ) : kind === "image" ? (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
          {items.map((a) => (
            <div key={a.id} className="group overflow-hidden rounded-2xl bg-surface shadow-card">
              <div className="flex aspect-square items-center justify-center bg-[conic-gradient(var(--fill)_25%,transparent_0_50%,var(--fill)_0_75%,transparent_0)] bg-[length:16px_16px] p-4">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={a.url ?? ""} alt={a.label} className="max-h-full max-w-full object-contain" />
              </div>
              <div className="flex items-center gap-1 p-2">
                <Input defaultValue={a.label} onBlur={(e) => rename(a, e.target.value)} className="h-8 bg-transparent text-[13px]" aria-label="Nome" />
                <IconButton label="Elimina" onClick={() => remove(a)} className="hover:text-red"><Trash2 className="size-4" /></IconButton>
              </div>
              <div className="px-3 pb-2 text-[11px] text-label-3">ID {a.id}</div>
            </div>
          ))}
        </div>
      ) : (
        <Section>
          {items.map((a) => (
            <div key={a.id} className="flex items-center gap-3 border-b border-separator px-4 py-2.5 last:border-0">
              <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-[#ff375f] to-[#ff9f0a] text-white"><Music className="size-4" /></div>
              <Input defaultValue={a.label} onBlur={(e) => rename(a, e.target.value)} className="h-8 flex-1 bg-transparent" aria-label="Nome" />
              <span className="text-[12px] text-label-2 tabular">{formatTime(a.duration)}</span>
              {a.url && <audio src={a.url} controls preload="none" className="h-8 w-48" />}
              <IconButton label="Elimina" onClick={() => remove(a)} className="hover:text-red"><Trash2 className="size-4" /></IconButton>
            </div>
          ))}
        </Section>
      )}
    </>
  );
}
