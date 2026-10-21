"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Brain, Check, FileText, Sparkles, X } from "lucide-react";
import { JobBar } from "@/components/status";
import { Button, cn, EmptyState, PageHeader, Pill, Section, Spinner, TextArea, useAction } from "@/components/ui";
import { api, type Feedback, type Job, type Proposal } from "@/lib/api";
import { lineDiff } from "@/lib/diff";
import { formatDate, formatTime, useResource } from "@/lib/hooks";

type Overview = { pending_feedback: (Feedback & { project_name: string })[]; proposals: Proposal[]; job: Job | null };

export default function LearningPage() {
  const { data, loading, reload } = useResource<Overview>("/api/learning", {
    pollWhile: (d) => d.job?.status === "queued" || d.job?.status === "running",
  });
  const { busy, run } = useAction();
  const running = data?.job && (data.job.status === "queued" || data.job.status === "running");
  const pendingProposals = data?.proposals.filter((p) => p.status === "pending") ?? [];

  return (
    <>
      <PageHeader
        title="Self-Learning"
        subtitle="Trasforma i feedback dati in revisione in regole di stile riutilizzate in tutti i montaggi futuri."
        actions={
          <Button icon={<Sparkles className="size-4" />} loading={busy === "run" || !!running} disabled={!data?.pending_feedback.length}
            onClick={() => run("run", async () => { await api("/api/learning/run", { method: "POST" }); reload(); })}>
            Avvia Self-Learning
          </Button>
        }
      />
      {loading ? <Spinner /> : (
        <div className="grid gap-8 xl:grid-cols-[1fr_420px]">
          <div className="min-w-0">
            {running && <div className="mb-6 rounded-2xl bg-surface p-4 shadow-card"><JobBar job={data!.job} /></div>}
            {data?.job?.status === "failed" && <p className="mb-6 rounded-2xl bg-red/10 p-4 text-[14px] text-red">{data.job.error}</p>}

            {pendingProposals.length ? pendingProposals.map((p) => <ProposalCard key={p.id} proposal={p} onDone={reload} />) : (
              <div className="mb-7 rounded-2xl bg-surface shadow-card">
                <EmptyState icon={<Brain />} title="Nessuna proposta da rivedere"
                  text="Avvia il Self-Learning: l'agente legge i feedback e propone modifiche alle skill. Niente viene scritto senza la tua approvazione." />
              </div>
            )}

            <SkillsEditor />
          </div>

          <div>
            <Section title={`Feedback da consolidare · ${data?.pending_feedback.length ?? 0}`}>
              {data?.pending_feedback.length ? data.pending_feedback.map((f) => (
                <Link key={f.id} href={`/projects/${f.project_id}`} className="block border-b border-separator px-4 py-3 last:border-0 hover:bg-fill/50">
                  <div className="mb-0.5 flex items-center gap-2 text-[12px] text-label-2">
                    <span className="truncate font-medium text-label">{f.project_name}</span>
                    <span className="font-mono tabular">{formatTime(f.timestamp, true)}</span>
                  </div>
                  <p className="text-[14px] leading-snug">{f.text}</p>
                </Link>
              )) : <p className="px-4 py-6 text-center text-[13px] text-label-2">Tutti i feedback sono già stati appresi.</p>}
            </Section>
            {data && data.proposals.some((p) => p.status !== "pending") && (
              <Section title="Storico">
                {data.proposals.filter((p) => p.status !== "pending").map((p) => (
                  <div key={p.id} className="flex items-center gap-3 border-b border-separator px-4 py-2.5 last:border-0">
                    <Pill color={p.status === "approved" ? "green" : "gray"}>{p.status === "approved" ? "Approvata" : "Scartata"}</Pill>
                    <span className="flex-1 truncate text-[13px]">{p.summary}</span>
                    <span className="text-[12px] text-label-2">{formatDate(p.created_at, { day: "numeric", month: "short" })}</span>
                  </div>
                ))}
              </Section>
            )}
          </div>
        </div>
      )}
    </>
  );
}

function ProposalCard({ proposal, onDone }: { proposal: Proposal; onDone: () => void }) {
  const [selected, setSelected] = useState<string[]>(proposal.changes.map((c) => c.path));
  const { busy, run } = useAction();
  return (
    <div className="mb-7 overflow-hidden rounded-2xl bg-surface shadow-card">
      <div className="border-b border-separator p-5">
        <div className="mb-1 flex items-center gap-2 text-[12px] font-medium text-purple uppercase"><Sparkles className="size-3.5" /> Proposta di apprendimento</div>
        <p className="text-[17px] leading-snug font-semibold">{proposal.summary}</p>
        <p className="mt-1 text-[13px] text-label-2">Da {proposal.feedback_ids.length} feedback · {formatDate(proposal.created_at)}</p>
      </div>
      {proposal.changes.map((c) => {
        const on = selected.includes(c.path);
        return (
          <div key={c.path} className="border-b border-separator last:border-0">
            <label className="flex cursor-pointer items-center gap-3 px-5 py-3">
              <input type="checkbox" checked={on} onChange={() => setSelected(on ? selected.filter((p) => p !== c.path) : [...selected, c.path])} className="size-4 accent-[var(--accent)]" />
              <FileText className="size-4 text-label-2" />
              <span className="font-mono text-[13px]">skills/{c.path}</span>
              {!c.before && <Pill color="green">nuovo</Pill>}
              <span className="ml-auto truncate text-[12px] text-label-2">{c.reason}</span>
            </label>
            <div className={cn("mx-5 mb-4 max-h-80 overflow-auto rounded-lg bg-fill/40 py-2 font-mono text-[12px] leading-[1.6]", !on && "opacity-40")}>
              {lineDiff(c.before, c.after).map((l, i) => (
                <div key={i} className={cn("px-3 whitespace-pre-wrap", l.type === "add" && "bg-green/15 text-green", l.type === "del" && "bg-red/12 text-red line-through decoration-red/40")}>
                  <span className="mr-2 inline-block w-3 select-none opacity-60">{l.type === "add" ? "+" : l.type === "del" ? "−" : " "}</span>{l.text || " "}
                </div>
              ))}
            </div>
          </div>
        );
      })}
      <div className="flex justify-end gap-2 bg-fill/30 px-5 py-3">
        <Button variant="gray" icon={<X className="size-4" />} loading={busy === "rej"} onClick={() => run("rej", async () => { await api(`/api/learning/proposals/${proposal.id}/reject`, { method: "POST" }); onDone(); })}>Scarta</Button>
        <Button icon={<Check className="size-4" />} disabled={!selected.length} loading={busy === "ok"}
          onClick={() => run("ok", async () => { await api(`/api/learning/proposals/${proposal.id}/approve`, { method: "POST", json: { paths: selected } }); onDone(); }, "Skill aggiornate: verranno usate dai prossimi montaggi")}>
          Approva {selected.length < proposal.changes.length ? `${selected.length} di ${proposal.changes.length}` : ""}
        </Button>
      </div>
    </div>
  );
}

function SkillsEditor() {
  const { data, reload } = useResource<{ path: string; content: string }[]>("/api/skills");
  const [active, setActive] = useState<string | null>(null);
  const [text, setText] = useState("");
  const { busy, run } = useAction();
  const file = data?.find((f) => f.path === active) ?? data?.[0];

  useEffect(() => {
    if (file) setText(file.content);
  }, [file]);

  if (!data) return null;
  return (
    <Section title="Skill attuali" footer="Sono file Markdown nella cartella skills/: l'agente li legge a ogni montaggio. Prima di ogni modifica ne viene salvata una copia in data/skills_history.">
      <div className="flex gap-1 overflow-x-auto border-b border-separator px-3 py-2">
        {data.map((f) => (
          <button key={f.path} onClick={() => setActive(f.path)} className={cn("rounded-full px-3 py-1 font-mono text-[12px] whitespace-nowrap", file?.path === f.path ? "bg-accent text-white" : "hover:bg-fill")}>
            {f.path}
          </button>
        ))}
      </div>
      {file && (
        <div className="p-4">
          <TextArea value={text} onChange={(e) => setText(e.target.value)} spellCheck={false} className="min-h-[260px] font-mono text-[13px]" />
          <div className="mt-2 flex justify-end">
            <Button size="sm" variant="tinted" disabled={text === file.content} loading={busy === "save"}
              onClick={() => run("save", async () => { await api(`/api/skills/${file.path}`, { method: "PUT", json: { content: text } }); reload(); }, "Skill salvata")}>
              Salva
            </Button>
          </div>
        </div>
      )}
    </Section>
  );
}
