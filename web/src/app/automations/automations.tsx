"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowRight, CheckCircle2, Clock, MessageCircle, MessageCircleHeart, Pencil, Plus, Send, Trash2, UserCheck } from "lucide-react";
import { Button, cn, EmptyState, Field, IconButton, Input, PageHeader, Pill, Section, Select, Sheet, Spinner, TextArea, Toggle, useAction } from "@/components/ui";
import { api, type Automation, type Lead, type ProjectSummary } from "@/lib/api";
import { formatDate, useResource } from "@/lib/hooks";

type IgMedia = { id: string; caption?: string; permalink: string; timestamp: string; thumbnail_url?: string; media_url?: string };

const LEAD_STATUS: Record<Lead["status"], { label: string; color: string }> = {
  contacted: { label: "Contattato", color: "blue" },
  awaiting_follow: { label: "Attende follow", color: "orange" },
  sent: { label: "Risorsa inviata", color: "green" },
  error: { label: "Errore", color: "red" },
};

export function Automations() {
  const params = useSearchParams();
  const autos = useResource<Automation[]>("/api/automations");
  const leads = useResource<Lead[]>("/api/leads");
  const [editing, setEditing] = useState<Partial<Automation> | null>(null);
  const { run } = useAction();

  useEffect(() => {
    const project = params.get("project");
    if (project) setEditing({ project_id: Number(project), keyword: params.get("keyword") ?? "", require_follow: true, active: true });
  }, [params]);

  const autoName = (id: number) => autos.data?.find((a) => a.id === id)?.keyword ?? `#${id}`;

  return (
    <>
      <PageHeader
        title="Automazioni DM"
        subtitle="Chi commenta la parola chiave riceve la risorsa in DM, dopo la verifica che segua la pagina."
        actions={<Button icon={<Plus className="size-4" />} onClick={() => setEditing({ require_follow: true, active: true, keyword: "" })}>Nuova automazione</Button>}
      />

      <FlowDiagram />

      {autos.loading ? <Spinner /> : !autos.data?.length ? (
        <div className="mb-8 rounded-2xl bg-surface shadow-card">
          <EmptyState icon={<MessageCircleHeart />} title="Nessuna automazione" text="Crea un'automazione da un progetto (scheda Contenuti) o da qui." />
        </div>
      ) : (
        <div className="mb-10 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {autos.data.map((a) => (
            <div key={a.id} className={cn("rounded-2xl bg-surface p-5 shadow-card transition", !a.active && "opacity-60")}>
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-[12px] font-medium text-label-2 uppercase">Commento</div>
                  <div className="font-display truncate text-[28px] leading-tight font-bold tracking-tight">{a.keyword}</div>
                  <div className="mt-0.5 truncate text-[13px] text-label-2">{a.project_name ?? a.name ?? "Automazione"} · {a.ig_media_id ? "post specifico" : "tutti i post"}</div>
                </div>
                <Toggle label="Attiva" checked={a.active} onChange={(v) => run("t", async () => { await api(`/api/automations/${a.id}`, { method: "PATCH", json: { active: v } }); autos.reload(); })} />
              </div>
              <div className="mt-4 grid grid-cols-3 gap-2 text-center">
                <Stat label="Contattati" value={(a.stats.contacted ?? 0) + (a.stats.awaiting_follow ?? 0)} />
                <Stat label="Attesa follow" value={a.stats.awaiting_follow ?? 0} />
                <Stat label="Inviati" value={a.stats.sent ?? 0} accent />
              </div>
              {!a.link && <p className="mt-3 rounded-lg bg-orange/10 px-3 py-2 text-[12px] text-orange">Manca il link della risorsa: imposta PUBLIC_BASE_URL o un link manuale.</p>}
              <div className="mt-4 flex justify-end gap-1">
                <IconButton label="Modifica" onClick={() => setEditing(a)}><Pencil className="size-4" /></IconButton>
                <IconButton label="Elimina" className="hover:text-red" onClick={() => confirm(`Eliminare l'automazione ${a.keyword}?`) && run("d", async () => { await api(`/api/automations/${a.id}`, { method: "DELETE" }); autos.reload(); })}><Trash2 className="size-4" /></IconButton>
              </div>
            </div>
          ))}
        </div>
      )}

      <Section title="Ultimi lead" action={<Button variant="plain" size="sm" onClick={leads.reload}>Aggiorna</Button>}>
        {leads.data?.length ? leads.data.map((l) => (
          <div key={l.id} className="flex items-center gap-3 border-b border-separator px-4 py-3 last:border-0">
            <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-[#feda75] via-[#d62976] to-[#4f5bd5] text-[13px] font-semibold text-white">
              {(l.username || "?").slice(0, 1).toUpperCase()}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="truncate text-[14px] font-medium">@{l.username || l.igsid}</span>
                <Pill color={LEAD_STATUS[l.status].color}>{LEAD_STATUS[l.status].label}</Pill>
              </div>
              <div className="truncate text-[12px] text-label-2">“{l.comment_text}” · {autoName(l.automation_id)} · {formatDate(l.updated_at)}</div>
              {l.error && <div className="truncate text-[12px] text-red">{l.error}</div>}
            </div>
          </div>
        )) : <p className="px-4 py-6 text-center text-[13px] text-label-2">I lead appariranno qui quando qualcuno commenterà.</p>}
      </Section>

      <AutomationSheet value={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); autos.reload(); }} />
    </>
  );
}

function Stat({ label, value, accent }: { label: string; value: number; accent?: boolean }) {
  return (
    <div className="rounded-xl bg-fill/60 py-2">
      <div className={cn("text-[20px] font-semibold tabular", accent && "text-green")}>{value}</div>
      <div className="text-[11px] text-label-2">{label}</div>
    </div>
  );
}

function FlowDiagram() {
  const steps = [
    { icon: MessageCircle, title: "Commento", text: "con la parola chiave" },
    { icon: Send, title: "Risposta privata", text: "con pulsante “Inviamela”" },
    { icon: UserCheck, title: "Verifica follow", text: "quando l'utente tocca il pulsante" },
    { icon: CheckCircle2, title: "Risorsa in DM", text: "oppure richiesta di follow" },
  ];
  return (
    <div className="mb-8 flex flex-wrap items-stretch gap-2 rounded-2xl bg-surface p-4 shadow-card">
      {steps.map((s, i) => (
        <div key={s.title} className="flex min-w-[150px] flex-1 items-center gap-2">
          <div className="flex flex-1 items-center gap-3 rounded-xl bg-fill/50 px-3 py-2.5">
            <s.icon className="size-5 shrink-0 text-accent" strokeWidth={1.8} />
            <div><div className="text-[13px] font-semibold">{s.title}</div><div className="text-[11px] text-label-2">{s.text}</div></div>
          </div>
          {i < steps.length - 1 && <ArrowRight className="hidden size-4 shrink-0 text-label-3 xl:block" />}
        </div>
      ))}
    </div>
  );
}

function AutomationSheet({ value, onClose, onSaved }: { value: Partial<Automation> | null; onClose: () => void; onSaved: () => void }) {
  const [form, setForm] = useState<Partial<Automation>>({});
  const projects = useResource<ProjectSummary[]>(value ? "/api/projects" : null);
  const media = useResource<IgMedia[]>(value ? "/api/instagram/media" : null);
  const { busy, run } = useAction();

  useEffect(() => {
    if (value) setForm(value);
  }, [value]);

  const set = <K extends keyof Automation>(k: K, v: Automation[K]) => setForm((f) => ({ ...f, [k]: v }));
  const text = (k: keyof Automation) => ({ value: (form[k] as string) ?? "", onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => set(k, e.target.value as never) });

  const save = () => run("save", async () => {
    const body = { ...form };
    delete (body as Record<string, unknown>).stats;
    delete (body as Record<string, unknown>).total;
    delete (body as Record<string, unknown>).project_name;
    delete (body as Record<string, unknown>).link;
    delete (body as Record<string, unknown>).id;
    delete (body as Record<string, unknown>).created_at;
    if (form.id) await api(`/api/automations/${form.id}`, { method: "PATCH", json: body });
    else await api("/api/automations", { method: "POST", json: body });
    onSaved();
  }, "Automazione salvata");

  return (
    <Sheet
      open={!!value}
      onClose={onClose}
      title={form.id ? "Modifica automazione" : "Nuova automazione"}
      wide
      footer={<><Button variant="gray" onClick={onClose}>Annulla</Button><Button onClick={save} loading={busy === "save"} disabled={!form.keyword?.trim()}>Salva</Button></>}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Parola chiave"><Input {...text("keyword")} className="uppercase" placeholder="DESIGN" /></Field>
        <Field label="Progetto (per il link della risorsa)">
          <Select value={form.project_id ?? ""} onChange={(e) => set("project_id", e.target.value ? Number(e.target.value) : null)}>
            <option value="">Nessuno</option>
            {projects.data?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </Select>
        </Field>
        <Field label="Post Instagram" hint={media.error ? "Collega Instagram per scegliere un post. Se pubblichi da Reel Studio, il post viene collegato in automatico." : "Vuoto = vale per i commenti su tutti i post."}>
          <Select value={form.ig_media_id ?? ""} onChange={(e) => set("ig_media_id", e.target.value)}>
            <option value="">Tutti i post</option>
            {media.data?.map((m) => <option key={m.id} value={m.id}>{formatDate(m.timestamp, { day: "numeric", month: "short" })} · {(m.caption ?? "").slice(0, 50)}</option>)}
          </Select>
        </Field>
        <Field label="Link risorsa (opzionale)" hint="Vuoto = guida del progetto pubblicata da Reel Studio."><Input {...text("resource_url")} placeholder="https://…" /></Field>
      </div>

      <div className="mt-6 space-y-4">
        <Field label="1 · Risposta privata al commento"><TextArea {...text("opening_message")} placeholder="Ciao! Ecco la risorsa che hai chiesto 👇" className="min-h-[64px]" /></Field>
        <Field label="Testo del pulsante" hint="Massimo 20 caratteri."><Input {...text("button_label")} maxLength={20} placeholder="Inviamela" /></Field>
        <div className="flex items-center justify-between rounded-xl bg-surface px-4 py-3">
          <div><div className="text-[15px]">Richiedi il follow</div><div className="text-[12px] text-label-2">Invia la risorsa solo a chi segue la pagina</div></div>
          <Toggle label="Richiedi il follow" checked={form.require_follow ?? true} onChange={(v) => set("require_follow", v)} />
        </div>
        {(form.require_follow ?? true) && (
          <Field label="2 · Messaggio se non segue la pagina"><TextArea {...text("follow_message")} placeholder="Per riceverla segui la pagina e tocca di nuovo il pulsante 🙏" className="min-h-[64px]" /></Field>
        )}
        <Field label="3 · Messaggio con la risorsa" hint="Il link viene aggiunto in fondo."><TextArea {...text("dm_message")} placeholder="Eccola! 🎁" className="min-h-[64px]" /></Field>
        <Field label="Risposta pubblica al commento (opzionale)"><Input {...text("public_reply")} placeholder="Ti ho scritto in DM 📩" /></Field>
        <p className="flex items-start gap-2 text-[12px] leading-relaxed text-label-2">
          <Clock className="mt-0.5 size-3.5 shrink-0" />
          Instagram consente una sola risposta privata per commento entro 7 giorni: la verifica del follow avviene quando l&apos;utente risponde o tocca il pulsante.
        </p>
      </div>
    </Sheet>
  );
}
