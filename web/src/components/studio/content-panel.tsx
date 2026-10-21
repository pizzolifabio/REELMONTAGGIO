"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Copy, ExternalLink, FileText, MessageCircleHeart, Sparkles } from "lucide-react";
import type { Content, ProjectDetail } from "@/lib/api";
import { api, API_URL } from "@/lib/api";
import { useResource } from "@/lib/hooks";
import { Button, EmptyState, Field, Input, Section, TextArea, useAction, useToast } from "../ui";

export function ContentPanel({ project, onChanged }: { project: ProjectDetail; onChanged: () => void }) {
  const { data, reload } = useResource<Content | null>(`/api/projects/${project.id}/content`);
  const { busy, run } = useAction();
  const toast = useToast();
  const [form, setForm] = useState<Partial<Content>>({});
  const generating = project.jobs.some((j) => j.kind === "generate_content" && (j.status === "queued" || j.status === "running"));

  useEffect(() => {
    if (data) setForm(data);
  }, [data]);

  useEffect(() => {
    if (!generating) reload();
  }, [generating, reload]);

  const generate = () => run("gen", async () => {
    await api(`/api/projects/${project.id}/content/generate`, { method: "POST" });
    onChanged();
  }, "L'agente sta scrivendo lead magnet e caption");

  if (!data) {
    return (
      <div className="rounded-2xl bg-surface shadow-card">
        <EmptyState
          icon={<FileText />}
          title="Lead magnet e caption"
          text="L'agente analizza il video montato e crea una risorsa da regalare (PDF), la caption con la CTA e la parola chiave per i commenti."
          action={<Button icon={<Sparkles className="size-4" />} loading={busy === "gen" || generating} disabled={!project.current_version} onClick={generate}>
            {generating ? "Generazione in corso" : "Genera contenuti"}
          </Button>}
        />
      </div>
    );
  }

  const set = (k: keyof Content) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setForm({ ...form, [k]: e.target.value });
  const copy = (text: string) => { navigator.clipboard.writeText(text); toast("ok", "Copiato"); };

  return (
    <div>
      <div className="mb-6 overflow-hidden rounded-2xl bg-gradient-to-br from-[#0a84ff] to-[#bf5af2] p-5 text-white shadow-card">
        <div className="text-[12px] font-semibold tracking-wider uppercase opacity-80">Commenta</div>
        <div className="font-display text-[40px] leading-none font-bold tracking-tight">{data.keyword}</div>
        <div className="mt-2 text-[14px] opacity-90">per ricevere “{data.lead_magnet.title}”</div>
        <div className="mt-4 flex flex-wrap gap-2">
          <Link href={`/automations?project=${project.id}&keyword=${data.keyword}`} className="inline-flex h-8 items-center gap-1.5 rounded-full bg-white/95 px-3.5 text-[13px] font-medium text-[#1d1d1f] transition hover:bg-white">
            <MessageCircleHeart className="size-4" /> Crea automazione DM
          </Link>
          <a href={`${API_URL}/api/projects/${project.id}/content/preview`} target="_blank" className="inline-flex h-8 items-center gap-1.5 rounded-full bg-white/20 px-3.5 text-[13px] font-medium transition hover:bg-white/30">
            <ExternalLink className="size-4" /> Anteprima guida
          </a>
          {data.pdf_url && <a href={data.pdf_url} target="_blank" className="inline-flex h-8 items-center gap-1.5 rounded-full bg-white/20 px-3.5 text-[13px] font-medium transition hover:bg-white/30"><FileText className="size-4" /> PDF</a>}
        </div>
      </div>

      <Section title="Post">
        <div className="space-y-3 p-4">
          <Field label="Titolo (YouTube)"><Input value={form.title ?? ""} onChange={set("title")} /></Field>
          <Field label="Caption"><TextArea value={form.caption ?? ""} onChange={set("caption")} className="min-h-[140px]" /></Field>
          <Field label="Hashtag"><Input value={form.hashtags ?? ""} onChange={set("hashtags")} /></Field>
          <Field label="Parola chiave"><Input value={form.keyword ?? ""} onChange={set("keyword")} className="uppercase" /></Field>
          <Field label="Messaggio DM con la risorsa"><TextArea value={form.dm_message ?? ""} onChange={set("dm_message")} className="min-h-[64px]" /></Field>
          <Field
            label="Link della risorsa"
            hint={data.public_url ? "Vuoto = pagina della guida servita da Reel Studio tramite il tunnel." : "Imposta PUBLIC_BASE_URL oppure incolla qui un link (Drive, Notion…)."}
          >
            <div className="flex gap-2">
              <Input value={form.resource_url ?? ""} onChange={set("resource_url")} placeholder={data.public_url ?? "https://…"} />
              {data.link && <Button variant="gray" size="sm" className="h-9" onClick={() => copy(data.link!)} icon={<Copy className="size-4" />}>Copia</Button>}
            </div>
          </Field>
          <div className="flex justify-between pt-1">
            <Button variant="plain" size="sm" loading={busy === "gen" || generating} onClick={generate} icon={<Sparkles className="size-4" />}>Rigenera tutto</Button>
            <Button size="sm" loading={busy === "save"} onClick={() => run("save", async () => {
              await api(`/api/projects/${project.id}/content`, { method: "PATCH", json: {
                title: form.title, caption: form.caption, hashtags: form.hashtags, keyword: form.keyword,
                dm_message: form.dm_message, resource_url: form.resource_url,
              } });
              reload();
            }, "Contenuti salvati")}>Salva</Button>
          </div>
        </div>
      </Section>

      <Section title="Lead magnet" footer="Per modificare i contenuti della guida, modifica il testo e salva: il PDF viene rigenerato.">
        <LeadMagnetEditor content={data} onSaved={reload} projectId={project.id} />
      </Section>
    </div>
  );
}

function LeadMagnetEditor({ content, projectId, onSaved }: { content: Content; projectId: number; onSaved: () => void }) {
  const [text, setText] = useState(JSON.stringify(content.lead_magnet, null, 2));
  const { busy, run } = useAction();
  useEffect(() => setText(JSON.stringify(content.lead_magnet, null, 2)), [content.lead_magnet]);
  return (
    <div className="p-4">
      <div className="mb-3">
        <div className="text-[12px] font-medium text-accent uppercase">{content.lead_magnet.type}</div>
        <div className="text-[19px] font-semibold">{content.lead_magnet.title}</div>
        <div className="text-[14px] text-label-2">{content.lead_magnet.subtitle}</div>
        <ol className="mt-3 space-y-1 text-[14px]">
          {content.lead_magnet.sections?.map((s, i) => <li key={i}><span className="mr-2 text-label-3 tabular">{String(i + 1).padStart(2, "0")}</span>{s.heading}</li>)}
        </ol>
      </div>
      <details className="group">
        <summary className="cursor-pointer text-[13px] text-accent select-none">Modifica struttura</summary>
        <TextArea value={text} onChange={(e) => setText(e.target.value)} spellCheck={false} className="mt-2 min-h-[260px] font-mono text-[12px]" />
        <div className="mt-2 flex justify-end">
          <Button size="sm" variant="tinted" loading={busy === "lm"} onClick={() => run("lm", async () => {
            let lead_magnet: unknown;
            try { lead_magnet = JSON.parse(text); } catch { throw new Error("JSON non valido"); }
            await api(`/api/projects/${projectId}/content`, { method: "PATCH", json: { lead_magnet } });
            onSaved();
          }, "Guida aggiornata, PDF in rigenerazione")}>Salva e rigenera PDF</Button>
        </div>
      </details>
    </div>
  );
}
