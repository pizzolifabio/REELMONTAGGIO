"use client";

import { ExternalLink, RotateCcw, Trash2, XCircle } from "lucide-react";
import type { Post } from "@/lib/api";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/hooks";
import { PlatformBadge } from "./platforms";
import { IconButton, Pill, useAction } from "./ui";

const STATUS: Record<Post["status"], { label: string; color: string }> = {
  scheduled: { label: "Programmato", color: "blue" },
  publishing: { label: "In pubblicazione", color: "orange" },
  published: { label: "Pubblicato", color: "green" },
  failed: { label: "Errore", color: "red" },
  cancelled: { label: "Annullato", color: "gray" },
};

export function PostRow({ post, onChanged, showProject }: { post: Post; onChanged: () => void; showProject?: boolean }) {
  const { run } = useAction();
  const s = STATUS[post.status];
  return (
    <div className="flex items-start gap-3 border-b border-separator px-4 py-3 last:border-0">
      <PlatformBadge platform={post.platform} size={30} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[14px] font-medium tabular">{formatDate(post.scheduled_at, { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}</span>
          <Pill color={s.color}>{s.label}</Pill>
          {showProject && <span className="truncate text-[13px] text-label-2">{post.project_name} · v{post.version}</span>}
        </div>
        <p className="mt-0.5 line-clamp-2 text-[13px] text-label-2">{post.title || post.caption}</p>
        {post.error && <p className={`mt-1 text-[12px] ${post.status === "failed" ? "text-red" : "text-orange"}`}>{post.error}</p>}
      </div>
      <div className="flex shrink-0">
        {post.result_url && <a href={post.result_url} target="_blank" className="inline-flex size-8 items-center justify-center rounded-full text-accent hover:bg-accent-tint" title="Apri"><ExternalLink className="size-4" /></a>}
        {post.status === "scheduled" && (
          <IconButton label="Annulla" onClick={() => run("c", async () => { await api(`/api/posts/${post.id}/cancel`, { method: "POST" }); onChanged(); })}><XCircle className="size-4" /></IconButton>
        )}
        {(post.status === "failed" || post.status === "cancelled") && (
          <IconButton label="Riprova ora" onClick={() => run("r", async () => { await api(`/api/posts/${post.id}/retry`, { method: "POST" }); onChanged(); }, "Pubblicazione avviata")}><RotateCcw className="size-4" /></IconButton>
        )}
        {post.status !== "publishing" && (
          <IconButton label="Elimina" className="hover:text-red" onClick={() => confirm("Eliminare questo post dal calendario?") && run("d", async () => { await api(`/api/posts/${post.id}`, { method: "DELETE" }); onChanged(); })}><Trash2 className="size-4" /></IconButton>
        )}
      </div>
    </div>
  );
}
