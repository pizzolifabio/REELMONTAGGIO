"use client";

import { useEffect, useRef, useState } from "react";
import { CheckCircle2, CircleDashed, ImagePlus, Trash2, Wand2, XCircle } from "lucide-react";
import type { Asset, Feedback, ProjectDetail } from "@/lib/api";
import { api, upload } from "@/lib/api";
import { formatTime, useResource } from "@/lib/hooks";
import { Button, cn, IconButton, Pill, Select, TextArea, useAction } from "../ui";

export function FeedbackPanel({ project, at, onSeek, onChanged, focusKey }: {
  project: ProjectDetail; at: number; onSeek: (t: number) => void; onChanged: () => void; focusKey: number;
}) {
  const [text, setText] = useState("");
  const [assetId, setAssetId] = useState<string>("");
  const { busy, run } = useAction();
  const textarea = useRef<HTMLTextAreaElement>(null);
  const library = useResource<Asset[]>("/api/library");
  const images = library.data?.filter((a) => a.kind === "image") ?? [];

  useEffect(() => {
    if (focusKey) textarea.current?.focus();
  }, [focusKey]);

  const pending = project.feedback.filter((f) => f.status === "pending" || f.status === "failed" || f.status === "applying");
  const history = project.feedback.filter((f) => f.status === "applied").reverse();
  const disabled = project.current_version === 0;

  const add = () => run("add", async () => {
    if (!text.trim()) return;
    await api(`/api/projects/${project.id}/feedback`, { method: "POST", json: { timestamp: at, text, asset_id: assetId ? Number(assetId) : null } });
    setText("");
    setAssetId("");
    onChanged();
  });

  const uploadImage = (files: File[]) => run("img", async () => {
    const [a] = await upload<Asset[]>("/api/library", files);
    await library.reload();
    setAssetId(String(a.id));
  });

  return (
    <div className="space-y-5">
      <div className="rounded-2xl bg-surface p-4 shadow-card">
        <div className="mb-2 flex items-center justify-between">
          <button onClick={() => onSeek(at)} className="rounded-full bg-accent-tint px-2.5 py-0.5 font-mono text-[13px] font-medium text-accent tabular">
            ⏱ {formatTime(at, true)}
          </button>
          <span className="text-[12px] text-label-2">Metti in pausa e descrivi la modifica</span>
        </div>
        <TextArea
          ref={textarea}
          value={text}
          disabled={disabled}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => (e.metaKey || e.ctrlKey) && e.key === "Enter" && add()}
          placeholder={disabled ? "Disponibile dopo il primo montaggio" : "Es. Sostituisci questo logo con quello nuovo, rendi l'animazione più dinamica…"}
        />
        <div className="mt-2.5 flex flex-wrap items-center gap-2">
          <Select value={assetId} onChange={(e) => setAssetId(e.target.value)} className="h-8 w-auto max-w-[200px] text-[13px]" aria-label="Allega immagine">
            <option value="">Nessuna immagine</option>
            {images.map((a) => <option key={a.id} value={a.id}>{a.label}</option>)}
          </Select>
          <label className="inline-flex h-8 cursor-pointer items-center gap-1 rounded-full px-2 text-[13px] text-accent hover:bg-accent-tint">
            <ImagePlus className="size-4" /> Carica
            <input type="file" accept="image/*" className="hidden" onChange={(e) => e.target.files?.length && uploadImage(Array.from(e.target.files))} />
          </label>
          <Button className="ml-auto" size="sm" onClick={add} loading={busy === "add"} disabled={disabled || !text.trim()}>Aggiungi ⌘↩</Button>
        </div>
      </div>

      <div>
        <div className="mb-2 flex items-center justify-between px-1">
          <h3 className="text-[13px] font-medium tracking-wide text-label-2 uppercase">Da applicare · {pending.length}</h3>
          <Button
            size="sm"
            icon={<Wand2 className="size-4" />}
            disabled={!pending.length || project.status === "processing"}
            loading={busy === "apply"}
            onClick={() => run("apply", async () => { await api(`/api/projects/${project.id}/feedback/apply`, { method: "POST" }); onChanged(); }, "Revisione avviata")}
          >
            Applica e rigenera
          </Button>
        </div>
        {pending.length ? (
          <ul className="overflow-hidden rounded-xl bg-surface shadow-card">
            {pending.map((f) => <FeedbackRow key={f.id} f={f} onSeek={onSeek} onDelete={() => run("del", async () => { await api(`/api/feedback/${f.id}`, { method: "DELETE" }); onChanged(); })} />)}
          </ul>
        ) : (
          <p className="rounded-xl bg-surface px-4 py-6 text-center text-[13px] text-label-2 shadow-card">Nessun feedback in attesa.</p>
        )}
      </div>

      {history.length > 0 && (
        <div>
          <h3 className="mb-2 px-1 text-[13px] font-medium tracking-wide text-label-2 uppercase">Applicati</h3>
          <ul className="overflow-hidden rounded-xl bg-surface shadow-card">
            {history.map((f) => <FeedbackRow key={f.id} f={f} onSeek={onSeek} />)}
          </ul>
        </div>
      )}
    </div>
  );
}

function FeedbackRow({ f, onSeek, onDelete }: { f: Feedback; onSeek: (t: number) => void; onDelete?: () => void }) {
  const icon = f.status === "applied" ? <CheckCircle2 className="size-[18px] text-green" />
    : f.status === "failed" ? <XCircle className="size-[18px] text-red" />
    : <CircleDashed className={cn("size-[18px] text-orange", f.status === "applying" && "animate-spin")} />;
  return (
    <li className="flex items-start gap-3 border-b border-separator px-4 py-3 last:border-0">
      <div className="mt-0.5">{icon}</div>
      <div className="min-w-0 flex-1">
        <div className="mb-0.5 flex items-center gap-2">
          <button onClick={() => onSeek(f.timestamp)} className="font-mono text-[12px] text-accent tabular hover:underline">{formatTime(f.timestamp, true)}</button>
          <span className="text-[12px] text-label-3">v{f.version}</span>
          {f.applied_in_version && <Pill color="green">→ v{f.applied_in_version}</Pill>}
          {f.consolidated && <Pill color="purple">appreso</Pill>}
        </div>
        <p className="text-[14px] leading-snug">{f.text}</p>
      </div>
      {onDelete && f.status !== "applying" && (
        <IconButton label="Elimina" onClick={onDelete} className="-mr-2 hover:text-red"><Trash2 className="size-4" /></IconButton>
      )}
    </li>
  );
}
