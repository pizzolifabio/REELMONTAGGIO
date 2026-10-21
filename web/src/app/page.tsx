"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Clapperboard, Film, Plus, X } from "lucide-react";
import { DropZone } from "@/components/dropzone";
import { JobBar, ProjectStatus } from "@/components/status";
import { Button, EmptyState, Field, Input, PageHeader, Progress, Sheet, Spinner, TextArea, useAction } from "@/components/ui";
import { api, upload, type ProjectSummary } from "@/lib/api";
import { formatDate, useResource } from "@/lib/hooks";

export default function ProjectsPage() {
  const { data, loading, error, reload } = useResource<ProjectSummary[]>("/api/projects", {
    pollWhile: (ps) => ps.some((p) => p.status === "processing"),
  });
  const [creating, setCreating] = useState(false);

  return (
    <>
      <PageHeader
        title="Progetti"
        subtitle="Carica le clip grezze: l'agente le trascrive, le monta e aggiunge sottotitoli, grafica e musica."
        actions={<Button icon={<Plus className="size-4" />} onClick={() => setCreating(true)}>Nuovo progetto</Button>}
      />
      {loading ? (
        <div className="flex justify-center py-24"><Spinner /></div>
      ) : error ? (
        <EmptyState icon={<Clapperboard />} title="Backend non raggiungibile" text={error} action={<Button variant="gray" onClick={reload}>Riprova</Button>} />
      ) : !data?.length ? (
        <EmptyState
          icon={<Film />}
          title="Nessun progetto"
          text="Crea il primo progetto caricando da 1 a 10 clip e, se vuoi, lo script di partenza."
          action={<Button onClick={() => setCreating(true)} icon={<Plus className="size-4" />}>Nuovo progetto</Button>}
        />
      ) : (
        <div className="grid grid-cols-2 gap-x-5 gap-y-7 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
          {data.map((p) => (
            <Link key={p.id} href={`/projects/${p.id}`} className="group">
              <div className="relative aspect-[9/16] overflow-hidden rounded-2xl bg-surface-2 shadow-card transition duration-300 ease-(--ease-apple) group-hover:-translate-y-0.5 group-hover:shadow-pop">
                {p.thumb_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={p.thumb_url} alt="" className="size-full object-cover" />
                ) : (
                  <div className="flex size-full items-center justify-center text-label-3"><Film className="size-10" strokeWidth={1.2} /></div>
                )}
                <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/60 to-transparent p-3 pt-10">
                  {p.job ? <div className="[&_*]:!text-white/90 [&_.bg-fill]:!bg-white/25"><JobBar job={p.job} /></div> : (
                    <div className="text-[12px] text-white/85">{p.clip_count} clip</div>
                  )}
                </div>
              </div>
              <div className="mt-2.5 px-0.5">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="truncate text-[15px] font-semibold">{p.name}</h3>
                </div>
                <div className="mt-1 flex items-center gap-2">
                  <ProjectStatus project={p} />
                  <span className="text-[12px] text-label-2">{formatDate(p.created_at, { day: "numeric", month: "short" })}</span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
      <NewProjectSheet open={creating} onClose={() => setCreating(false)} />
    </>
  );
}

function NewProjectSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const router = useRouter();
  const [name, setName] = useState("");
  const [script, setScript] = useState("");
  const [brief, setBrief] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [progress, setProgress] = useState<number | null>(null);
  const { busy, run } = useAction();

  const create = (process: boolean) =>
    run("create", async () => {
      if (!name.trim()) throw new Error("Dai un nome al progetto");
      const p = await api<ProjectSummary>("/api/projects", { method: "POST", json: { name, script, brief } });
      if (files.length) {
        setProgress(0);
        await upload(`/api/projects/${p.id}/assets`, files, setProgress);
        if (process) await api(`/api/projects/${p.id}/process`, { method: "POST" });
      }
      router.push(`/projects/${p.id}`);
    });

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="Nuovo progetto"
      footer={
        <>
          <Button variant="gray" onClick={() => create(false)} disabled={!!busy}>Crea senza montare</Button>
          <Button onClick={() => create(true)} loading={busy === "create"} disabled={!files.length}>Carica e monta</Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="Nome">
          <Input autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="Es. 3 errori di design" />
        </Field>
        <Field label="Clip video" hint="Da 1 a 10 file. Verranno trascritti e montati nell'ordine più efficace.">
          <DropZone accept="video/*" title="Trascina qui le clip o fai clic" hint="MP4, MOV, MKV…" onFiles={(f) => setFiles((prev) => [...prev, ...f].slice(0, 10))} />
        </Field>
        {files.length > 0 && (
          <ul className="overflow-hidden rounded-xl bg-surface">
            {files.map((f, i) => (
              <li key={i} className="flex items-center gap-3 border-b border-separator px-3 py-2 text-[14px] last:border-0">
                <Film className="size-4 text-label-2" />
                <span className="flex-1 truncate">{f.name}</span>
                <span className="text-[12px] text-label-2 tabular">{(f.size / 1e6).toFixed(1)} MB</span>
                <button aria-label="Rimuovi" onClick={() => setFiles(files.filter((_, j) => j !== i))} className="text-label-3 hover:text-red"><X className="size-4" /></button>
              </li>
            ))}
          </ul>
        )}
        {progress !== null && <div className="space-y-1"><div className="text-[12px] text-label-2">Caricamento {Math.round(progress * 100)}%</div><Progress value={progress} /></div>}
        <Field label="Script di partenza (opzionale)">
          <TextArea value={script} onChange={(e) => setScript(e.target.value)} placeholder="Hook, punti chiave, CTA…" />
        </Field>
        <Field label="Indicazioni per il montaggio (opzionale)">
          <TextArea value={brief} onChange={(e) => setBrief(e.target.value)} className="min-h-[64px]" placeholder="Es. ritmo veloce, massimo 45 secondi, logo in alto a destra" />
        </Field>
      </div>
    </Sheet>
  );
}
