"use client";

import { useEffect, useState } from "react";
import { Send } from "lucide-react";
import type { AccountInfo, Content, Platform } from "@/lib/api";
import { api } from "@/lib/api";
import { useResource } from "@/lib/hooks";
import { PlatformBadge, PLATFORMS } from "./platforms";
import { Button, cn, Field, Input, Segmented, TextArea, useAction } from "./ui";

function localDefault() {
  const d = new Date(Date.now() + 60 * 60 * 1000);
  d.setMinutes(0, 0, 0);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:00`;
}

export function PublishForm({ projectId, version, onDone }: { projectId: number; version: number; onDone?: () => void }) {
  const accounts = useResource<AccountInfo[]>("/api/accounts");
  const content = useResource<Content | null>(`/api/projects/${projectId}/content`);
  const [platforms, setPlatforms] = useState<Platform[]>([]);
  const [when, setWhen] = useState<"now" | "later">("later");
  const [at, setAt] = useState(localDefault);
  const [title, setTitle] = useState("");
  const [caption, setCaption] = useState("");
  const [privacy, setPrivacy] = useState<"public" | "unlisted" | "private">("public");
  const { busy, run } = useAction();

  useEffect(() => {
    if (content.data) {
      setTitle(content.data.title);
      setCaption(`${content.data.caption}${content.data.hashtags ? `\n\n${content.data.hashtags}` : ""}`);
    }
  }, [content.data]);

  useEffect(() => {
    if (accounts.data) setPlatforms(accounts.data.filter((a) => a.connected).map((a) => a.platform));
  }, [accounts.data]);

  const connected = new Set(accounts.data?.filter((a) => a.connected).map((a) => a.platform));

  const submit = () => run("post", async () => {
    await api("/api/posts", { method: "POST", json: {
      project_id: projectId, version, platforms, title, caption, privacy,
      scheduled_at: when === "now" ? null : new Date(at).toISOString(),
    } });
    onDone?.();
  }, when === "now" ? "Pubblicazione avviata" : "Post programmato");

  return (
    <div className="space-y-4">
      <div className="grid gap-2 sm:grid-cols-3">
        {PLATFORMS.map((p) => {
          const on = platforms.includes(p.id);
          const ok = connected.has(p.id);
          return (
            <button
              key={p.id}
              disabled={!ok}
              onClick={() => setPlatforms(on ? platforms.filter((x) => x !== p.id) : [...platforms, p.id])}
              className={cn(
                "flex items-center gap-2.5 rounded-xl px-3 py-2.5 text-left ring-1 transition disabled:opacity-45",
                on ? "bg-accent-tint ring-accent" : "bg-surface ring-separator hover:bg-fill/50",
              )}
            >
              <PlatformBadge platform={p.id} size={26} />
              <div className="min-w-0">
                <div className="text-[14px] font-medium">{p.short}</div>
                <div className="text-[11px] text-label-2">{ok ? "Collegato" : "Non collegato"}</div>
              </div>
            </button>
          );
        })}
      </div>
      {connected.size === 0 && accounts.data && (
        <p className="text-[13px] text-label-2">Collega almeno un account in <a href="/settings" className="text-accent">Impostazioni</a>.</p>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <Segmented value={when} onChange={setWhen} options={[{ value: "later", label: "Programma" }, { value: "now", label: "Subito" }]} />
        {when === "later" && <Input type="datetime-local" value={at} onChange={(e) => setAt(e.target.value)} className="w-auto" />}
      </div>

      <Field label="Titolo (YouTube)"><Input value={title} onChange={(e) => setTitle(e.target.value)} /></Field>
      <Field label="Caption"><TextArea value={caption} onChange={(e) => setCaption(e.target.value)} className="min-h-[120px]" /></Field>
      <Field label="Visibilità" hint="TikTok pubblica come privato finché la tua app non supera la verifica di TikTok.">
        <Segmented value={privacy} onChange={setPrivacy} options={[{ value: "public", label: "Pubblico" }, { value: "unlisted", label: "Non in elenco" }, { value: "private", label: "Privato" }]} />
      </Field>
      <div className="flex justify-end">
        <Button icon={<Send className="size-4" />} onClick={submit} loading={busy === "post"} disabled={!platforms.length}>
          {when === "now" ? "Pubblica ora" : "Programma"}
        </Button>
      </div>
    </div>
  );
}
