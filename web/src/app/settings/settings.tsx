"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { CheckCircle2, Copy, KeyRound, XCircle } from "lucide-react";
import { PlatformBadge, PLATFORMS } from "@/components/platforms";
import { jobLabel } from "@/components/status";
import { Button, Field, Input, PageHeader, Pill, Row, Section, Sheet, Spinner, useAction, useToast } from "@/components/ui";
import { api, type AccountInfo, type SystemInfo } from "@/lib/api";
import { formatDate, useResource } from "@/lib/hooks";

export function Settings() {
  const params = useSearchParams();
  const router = useRouter();
  const toast = useToast();
  const accounts = useResource<AccountInfo[]>("/api/accounts");
  const system = useResource<SystemInfo>("/api/system");
  const [tokenSheet, setTokenSheet] = useState(false);
  const { busy, run } = useAction();

  useEffect(() => {
    const ok = params.get("connected");
    const err = params.get("error");
    if (ok) toast("ok", `Account ${ok} collegato`);
    if (err) toast("error", err);
    if (ok || err) router.replace("/settings");
  }, [params, router, toast]);

  const connect = (platform: string) => run(platform, async () => {
    const { url } = await api<{ url: string }>(`/api/accounts/${platform}/connect`);
    window.location.href = url;
  });

  const copy = (t: string) => { navigator.clipboard.writeText(t); toast("ok", "Copiato"); };
  const s = system.data;

  return (
    <>
      <PageHeader title="Impostazioni" subtitle="Account social, stato del sistema e configurazione dei webhook." />
      <div className="grid gap-x-8 lg:grid-cols-2">
        <div>
          <Section title="Account" footer="Le credenziali delle app (Meta, Google, TikTok) vanno inserite nel file .env. I token restano solo su questo Mac.">
            {accounts.data ? PLATFORMS.map((p) => {
              const a = accounts.data!.find((x) => x.platform === p.id)!;
              return (
                <Row key={p.id}>
                  <PlatformBadge platform={p.id} size={32} />
                  <div className="min-w-0 flex-1">
                    <div className="text-[15px] font-medium">{p.name}</div>
                    <div className="truncate text-[12px] text-label-2">
                      {a.connected ? `@${a.username} · collegato ${formatDate(a.connected_at!, { day: "numeric", month: "short" })}` : a.app_configured ? "Non collegato" : "App non configurata in .env"}
                    </div>
                  </div>
                  {a.connected ? (
                    <Button size="sm" variant="destructive" onClick={() => confirm(`Scollegare ${p.short}?`) && run("x", async () => { await api(`/api/accounts/${p.id}`, { method: "DELETE" }); accounts.reload(); })}>Scollega</Button>
                  ) : (
                    <div className="flex gap-1.5">
                      {p.id === "instagram" && <Button size="sm" variant="gray" icon={<KeyRound className="size-3.5" />} onClick={() => setTokenSheet(true)}>Token</Button>}
                      <Button size="sm" variant="tinted" disabled={!a.app_configured} loading={busy === p.id} onClick={() => connect(p.id)}>Collega</Button>
                    </div>
                  )}
                </Row>
              );
            }) : <div className="p-6"><Spinner /></div>}
          </Section>

          <Section title="Webhook Instagram" footer="Nella dashboard Meta → Instagram → Webhooks: imposta questo URL e il verify token, poi iscriviti ai campi comments e messages.">
            {s?.webhook_url ? (
              <>
                <CopyRow label="Callback URL" value={s.webhook_url} onCopy={copy} />
                <CopyRow label="Verify token" value={s.verify_token} onCopy={copy} />
              </>
            ) : (
              <Row><XCircle className="size-5 text-orange" /><span className="text-[14px] text-label-2">Imposta PUBLIC_BASE_URL in .env (tunnel Cloudflare: vedi README).</span></Row>
            )}
          </Section>

          {s && (
            <Section title="URI di reindirizzamento OAuth" footer="Registrali nelle impostazioni di ciascuna app sviluppatore.">
              {PLATFORMS.map((p) => s.oauth_redirects[p.id] ? <CopyRow key={p.id} label={p.short} value={s.oauth_redirects[p.id]!} onCopy={copy} /> : (
                <Row key={p.id}><span className="w-24 text-[13px] text-label-2">{p.short}</span><span className="text-[13px] text-orange">Serve PUBLIC_BASE_URL</span></Row>
              ))}
            </Section>
          )}
        </div>

        <div>
          <Section title="Stato del sistema">
            {s ? (
              <>
                <Check ok={s.ffmpeg} label="FFmpeg" />
                <Check ok={s.ffmpeg_captions} label="Sottotitoli animati (libass)" hint={!s.ffmpeg_captions ? "brew install ffmpeg-full" : undefined} />
                <Check ok={s.agent_available} label={`Agente: ${s.agent_provider}`} hint={s.agent_provider === "claude-cli" ? "Usa la tua sessione di Claude Code (claude -p)" : undefined} />
                <Check ok label={`Trascrizione: Whisper ${s.whisper_model}`} hint="Il modello si scarica al primo utilizzo" />
                <Check ok={s.chrome} label="Google Chrome (PDF dei lead magnet)" />
                <Check ok={!!s.public_base_url} label="Tunnel pubblico" hint={s.public_base_url ?? "Necessario per DM, pubblicazione Instagram e link alle risorse"} />
              </>
            ) : <div className="p-6"><Spinner /></div>}
          </Section>

          <Section title="Attività recenti">
            {s?.jobs.length ? s.jobs.map((j) => (
              <Row key={j.id}>
                <Pill color={j.status === "done" ? "green" : j.status === "failed" ? "red" : "blue"}>{jobLabel(j.kind)}</Pill>
                <span className="min-w-0 flex-1 truncate text-[13px] text-label-2">{j.error || j.message || j.status}</span>
                <span className="text-[12px] text-label-3 tabular">{formatDate(j.created_at)}</span>
              </Row>
            )) : <p className="px-4 py-5 text-center text-[13px] text-label-2">Nessuna attività.</p>}
          </Section>
        </div>
      </div>

      <InstagramTokenSheet open={tokenSheet} onClose={() => setTokenSheet(false)} onDone={() => { setTokenSheet(false); accounts.reload(); }} />
    </>
  );
}

function Check({ ok, label, hint }: { ok: boolean; label: string; hint?: string }) {
  return (
    <Row>
      {ok ? <CheckCircle2 className="size-5 shrink-0 text-green" /> : <XCircle className="size-5 shrink-0 text-orange" />}
      <div className="min-w-0">
        <div className="text-[14px]">{label}</div>
        {hint && <div className="truncate text-[12px] text-label-2">{hint}</div>}
      </div>
    </Row>
  );
}

function CopyRow({ label, value, onCopy }: { label: string; value: string; onCopy: (v: string) => void }) {
  return (
    <Row>
      <span className="w-24 shrink-0 text-[13px] text-label-2">{label}</span>
      <code className="min-w-0 flex-1 truncate font-mono text-[12px]">{value}</code>
      <button aria-label={`Copia ${label}`} onClick={() => onCopy(value)} className="text-accent"><Copy className="size-4" /></button>
    </Row>
  );
}

function InstagramTokenSheet({ open, onClose, onDone }: { open: boolean; onClose: () => void; onDone: () => void }) {
  const [token, setToken] = useState("");
  const { busy, run } = useAction();
  return (
    <Sheet open={open} onClose={onClose} title="Collega Instagram con un token"
      footer={<><Button variant="gray" onClick={onClose}>Annulla</Button><Button loading={busy === "t"} disabled={!token.trim()} onClick={() => run("t", async () => {
        await api("/api/accounts/instagram/token", { method: "POST", json: { access_token: token } });
        setToken("");
        onDone();
      }, "Instagram collegato")}>Collega</Button></>}>
      <p className="mb-4 text-[14px] leading-relaxed text-label-2">
        Metodo più rapido per uso personale: nella dashboard della tua app Meta apri <b>Instagram → API setup with Instagram login</b>, aggiungi il tuo account e genera un token di accesso.
      </p>
      <Field label="Access token"><Input value={token} onChange={(e) => setToken(e.target.value)} placeholder="IGAA…" autoComplete="off" /></Field>
    </Sheet>
  );
}
