"use client";

import { useMemo, useState } from "react";
import { CalendarDays, ChevronLeft, ChevronRight, Plus } from "lucide-react";
import { PlatformBadge } from "@/components/platforms";
import { PostRow } from "@/components/posts-list";
import { PublishForm } from "@/components/publish-form";
import { Button, cn, EmptyState, Field, IconButton, PageHeader, Section, Segmented, Select, Sheet, Spinner } from "@/components/ui";
import type { Post, ProjectSummary } from "@/lib/api";
import { useResource } from "@/lib/hooks";

const DAYS = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"];

function dayKey(d: Date) {
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
}

export function Calendar() {
  const { data: posts, loading, reload } = useResource<Post[]>("/api/posts", { pollWhile: (ps) => ps.some((p) => p.status === "publishing") });
  const [month, setMonth] = useState(() => { const d = new Date(); return new Date(d.getFullYear(), d.getMonth(), 1); });
  const [selected, setSelected] = useState<string | null>(null);
  const [filter, setFilter] = useState<"upcoming" | "published" | "all">("upcoming");
  const [creating, setCreating] = useState(false);

  const byDay = useMemo(() => {
    const m = new Map<string, Post[]>();
    posts?.forEach((p) => {
      const k = dayKey(new Date(p.scheduled_at));
      m.set(k, [...(m.get(k) ?? []), p]);
    });
    return m;
  }, [posts]);

  const cells = useMemo(() => {
    const first = (month.getDay() + 6) % 7;
    const start = new Date(month.getFullYear(), month.getMonth(), 1 - first);
    return Array.from({ length: 42 }, (_, i) => new Date(start.getFullYear(), start.getMonth(), start.getDate() + i));
  }, [month]);

  const visible = (posts ?? [])
    .filter((p) => (selected ? dayKey(new Date(p.scheduled_at)) === selected : true))
    .filter((p) => filter === "all" || (filter === "published" ? p.status === "published" : ["scheduled", "publishing", "failed"].includes(p.status)))
    .sort((a, b) => (filter === "published" ? b.scheduled_at.localeCompare(a.scheduled_at) : a.scheduled_at.localeCompare(b.scheduled_at)));

  const today = dayKey(new Date());

  return (
    <>
      <PageHeader
        title="Calendario"
        subtitle="Programma la pubblicazione contemporanea su Instagram Reels, YouTube Shorts e TikTok."
        actions={<Button icon={<Plus className="size-4" />} onClick={() => setCreating(true)}>Nuovo post</Button>}
      />
      <div className="grid gap-8 lg:grid-cols-[400px_1fr]">
        <div className="rounded-2xl bg-surface p-4 shadow-card lg:self-start">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-[17px] font-semibold capitalize">{month.toLocaleDateString("it-IT", { month: "long", year: "numeric" })}</h2>
            <div className="flex">
              <IconButton label="Mese precedente" onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))}><ChevronLeft className="size-5" /></IconButton>
              <IconButton label="Mese successivo" onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))}><ChevronRight className="size-5" /></IconButton>
            </div>
          </div>
          <div className="grid grid-cols-7 text-center text-[11px] font-medium text-label-3 uppercase">
            {DAYS.map((d) => <div key={d} className="py-1">{d}</div>)}
          </div>
          <div className="grid grid-cols-7 gap-0.5">
            {cells.map((d) => {
              const k = dayKey(d);
              const items = byDay.get(k) ?? [];
              const inMonth = d.getMonth() === month.getMonth();
              return (
                <button
                  key={k}
                  onClick={() => setSelected(selected === k ? null : k)}
                  className={cn(
                    "flex aspect-square flex-col items-center justify-start gap-1 rounded-lg pt-1.5 text-[14px] tabular transition",
                    !inMonth && "text-label-3",
                    selected === k ? "bg-accent text-white" : "hover:bg-fill",
                  )}
                >
                  <span className={cn("flex size-6 items-center justify-center rounded-full", k === today && selected !== k && "bg-red font-semibold text-white")}>{d.getDate()}</span>
                  <span className="flex gap-0.5">
                    {items.slice(0, 3).map((p) => (
                      <span key={p.id} className={cn("size-1.5 rounded-full", selected === k ? "bg-white" : p.status === "published" ? "bg-green" : p.status === "failed" ? "bg-red" : "bg-accent")} />
                    ))}
                  </span>
                </button>
              );
            })}
          </div>
          {selected && <button className="mt-3 text-[13px] text-accent" onClick={() => setSelected(null)}>Mostra tutti i giorni</button>}
        </div>

        <div className="min-w-0">
          <Segmented className="mb-4" value={filter} onChange={setFilter} options={[
            { value: "upcoming", label: "In programma" }, { value: "published", label: "Pubblicati" }, { value: "all", label: "Tutti" },
          ]} />
          {loading ? <Spinner /> : visible.length ? (
            <Section>{visible.map((p) => <PostRow key={p.id} post={p} onChanged={reload} showProject />)}</Section>
          ) : (
            <div className="rounded-2xl bg-surface shadow-card">
              <EmptyState icon={<CalendarDays />} title="Niente in programma" text="Programma un video montato su una o più piattaforme." />
            </div>
          )}
          <div className="mt-2 flex items-center gap-3 px-1 text-[12px] text-label-2">
            <PlatformBadge platform="instagram" size={16} /> <PlatformBadge platform="youtube" size={16} /> <PlatformBadge platform="tiktok" size={16} />
            Lo scheduler controlla i post in scadenza ogni 20 secondi, finché Reel Studio è acceso.
          </div>
        </div>
      </div>
      <NewPostSheet open={creating} onClose={() => setCreating(false)} onDone={() => { setCreating(false); reload(); }} />
    </>
  );
}

function NewPostSheet({ open, onClose, onDone }: { open: boolean; onClose: () => void; onDone: () => void }) {
  const projects = useResource<ProjectSummary[]>(open ? "/api/projects" : null);
  const ready = projects.data?.filter((p) => p.render_url) ?? [];
  const [projectId, setProjectId] = useState<number | null>(null);
  const project = ready.find((p) => p.id === projectId) ?? ready[0];
  return (
    <Sheet open={open} onClose={onClose} title="Nuovo post" wide>
      {!ready.length ? (
        <p className="text-[14px] text-label-2">Nessun progetto con un video pronto.</p>
      ) : (
        <div className="space-y-4">
          <Field label="Video">
            <Select value={project?.id} onChange={(e) => setProjectId(Number(e.target.value))}>
              {ready.map((p) => <option key={p.id} value={p.id}>{p.name} · v{p.current_version}</option>)}
            </Select>
          </Field>
          {project && <PublishForm key={project.id} projectId={project.id} version={project.current_version} onDone={onDone} />}
        </div>
      )}
    </Sheet>
  );
}
