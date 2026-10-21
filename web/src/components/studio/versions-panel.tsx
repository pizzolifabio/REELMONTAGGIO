"use client";

import { useState } from "react";
import { Download, Eye, RefreshCw, RotateCcw } from "lucide-react";
import type { ProjectDetail } from "@/lib/api";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/hooks";
import { Button, cn, IconButton, Pill, Section, Sheet, TextArea, useAction } from "../ui";

export function VersionsPanel({ project, viewing, onView, onChanged }: {
  project: ProjectDetail; viewing: number; onView: (v: number) => void; onChanged: () => void;
}) {
  const { busy, run } = useAction();
  const [editing, setEditing] = useState(false);
  const current = project.versions.find((v) => v.version === project.current_version);
  const [json, setJson] = useState("");

  if (!project.versions.length) {
    return <p className="rounded-xl bg-surface px-4 py-8 text-center text-[14px] text-label-2 shadow-card">Ancora nessuna versione.</p>;
  }

  return (
    <div>
      <Section
        title="Versioni"
        action={current && (
          <Button variant="plain" size="sm" onClick={() => { setJson(JSON.stringify(current.edl, null, 2)); setEditing(true); }}>
            Modifica timeline
          </Button>
        )}
      >
        {project.versions.map((v) => (
          <div key={v.version} className={cn("flex items-center gap-3 border-b border-separator px-4 py-3 last:border-0", viewing === v.version && "bg-accent-tint/60")}>
            <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-fill font-semibold tabular">v{v.version}</div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="truncate text-[14px] font-medium">{v.note || "Montaggio"}</span>
                {v.version === project.current_version && <Pill color="blue">attuale</Pill>}
              </div>
              <div className="mt-0.5 text-[12px] text-label-2">
                {formatDate(v.created_at)} · {v.edl.clips.length} tagli ·{" "}
                {v.render_status === "done" ? "pronto" : v.render_status === "error" ? <span className="text-red">render fallito</span> : "render in corso"}
              </div>
              {v.render_error && <p className="mt-1 line-clamp-2 text-[12px] text-red">{v.render_error}</p>}
            </div>
            <div className="flex">
              {v.render_url && <IconButton label="Guarda" onClick={() => onView(v.version)}><Eye className="size-4" /></IconButton>}
              {v.render_url && <a href={v.render_url} download className="inline-flex size-8 items-center justify-center rounded-full text-label-2 hover:bg-fill hover:text-label" aria-label="Scarica" title="Scarica"><Download className="size-4" /></a>}
              {v.render_status === "error" && (
                <IconButton label="Rigenera render" onClick={() => run("render", async () => { await api(`/api/projects/${project.id}/versions/${v.version}/render`, { method: "POST" }); onChanged(); })}>
                  <RefreshCw className="size-4" />
                </IconButton>
              )}
              {v.version !== project.current_version && (
                <IconButton label="Ripristina come nuova versione" onClick={() => run("restore", async () => { await api(`/api/projects/${project.id}/versions/${v.version}/restore`, { method: "POST" }); onChanged(); }, "Versione ripristinata")}>
                  <RotateCcw className="size-4" />
                </IconButton>
              )}
            </div>
          </div>
        ))}
      </Section>

      <Sheet
        open={editing}
        onClose={() => setEditing(false)}
        wide
        title="Timeline (EDL)"
        footer={<>
          <Button variant="gray" onClick={() => setEditing(false)}>Annulla</Button>
          <Button loading={busy === "save"} onClick={() => run("save", async () => {
            let edl: unknown;
            try { edl = JSON.parse(json); } catch { throw new Error("JSON non valido"); }
            await api(`/api/projects/${project.id}/timeline`, { method: "PUT", json: { edl, note: "Modifica manuale della timeline" } });
            setEditing(false);
            onChanged();
          }, "Nuova versione in render")}>Salva come nuova versione</Button>
        </>}
      >
        <p className="mb-3 text-[13px] leading-relaxed text-label-2">
          Modifica direttamente tagli (secondi del video sorgente), sottotitoli, overlay e musica. La timeline viene validata prima del render.
        </p>
        <TextArea value={json} onChange={(e) => setJson(e.target.value)} spellCheck={false} className="min-h-[50vh] font-mono text-[12px]" />
      </Sheet>
    </div>
  );
}
