"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, ChevronLeft, Clapperboard, MoreHorizontal, RefreshCw, Trash2 } from "lucide-react";
import { ClipsPanel } from "@/components/studio/clips-panel";
import { ContentPanel } from "@/components/studio/content-panel";
import { FeedbackPanel } from "@/components/studio/feedback-panel";
import { Player, type PlayerHandle } from "@/components/studio/player";
import { VersionsPanel } from "@/components/studio/versions-panel";
import { PostRow } from "@/components/posts-list";
import { PublishForm } from "@/components/publish-form";
import { JobBar, ProjectStatus } from "@/components/status";
import { Button, EmptyState, IconButton, PageHeader, Section, Segmented, Spinner, useAction } from "@/components/ui";
import { api, type Post, type ProjectDetail } from "@/lib/api";
import { useResource } from "@/lib/hooks";

type Tab = "feedback" | "clips" | "versions" | "content" | "publish";

export function Studio() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data: project, error, reload } = useResource<ProjectDetail>(`/api/projects/${id}`, {
    pollWhile: (p) => p.status === "processing" || p.jobs.some((j) => j.status === "queued" || j.status === "running"),
  });
  const posts = useResource<Post[]>("/api/posts");
  const [tab, setTab] = useState<Tab>("feedback");
  const [viewing, setViewing] = useState(0);
  const [at, setAt] = useState(0);
  const [focusKey, setFocusKey] = useState(0);
  const [menu, setMenu] = useState(false);
  const player = useRef<PlayerHandle>(null);
  const { busy, run } = useAction();

  // passa automaticamente all'ultima versione quando ne arriva una nuova
  const lastVersion = useRef(0);
  useEffect(() => {
    if (project && project.current_version !== lastVersion.current) {
      lastVersion.current = project.current_version;
      setViewing(project.current_version);
    }
  }, [project]);

  const onComment = useCallback((t: number) => {
    setAt(t);
    setTab("feedback");
    setFocusKey((k) => k + 1);
  }, []);

  if (error && !project) return <EmptyState icon={<Clapperboard />} title="Progetto non disponibile" text={error} />;
  if (!project) return <div className="flex justify-center py-24"><Spinner /></div>;

  const version = project.versions.find((v) => v.version === viewing) ?? project.versions[0];
  const activeJob = project.jobs.find((j) => j.status === "queued" || j.status === "running") ?? null;
  const failedJob = !activeJob && project.status === "error" ? project.jobs.find((j) => j.status === "failed") : null;
  const pendingCount = project.feedback.filter((f) => f.status === "pending" || f.status === "failed").length;
  const videoCount = project.assets.filter((a) => a.kind === "video").length;
  const projectPosts = posts.data?.filter((p) => p.project_id === project.id) ?? [];
  const src = version?.render_url ? `${version.render_url}?v=${version.version}-${version.render_status}` : null;

  const startEdit = () => run("process", async () => {
    await api(`/api/projects/${project.id}/process`, { method: "POST" });
    reload();
  }, "Montaggio avviato");

  return (
    <>
      <PageHeader
        back={<Link href="/" className="mb-1 inline-flex items-center text-[15px] text-accent hover:underline"><ChevronLeft className="-ml-1 size-5" />Progetti</Link>}
        title={project.name}
        subtitle={<span className="flex items-center gap-2"><ProjectStatus project={project} /><span>{videoCount} clip</span></span>}
        actions={
          <>
            {project.current_version === 0 ? (
              <Button onClick={startEdit} loading={busy === "process"} disabled={!videoCount || !!activeJob} icon={<Clapperboard className="size-4" />}>Monta il video</Button>
            ) : pendingCount > 0 ? (
              <Button disabled={!!activeJob} loading={busy === "apply"} onClick={() => run("apply", async () => { await api(`/api/projects/${project.id}/feedback/apply`, { method: "POST" }); reload(); }, "Revisione avviata")}>
                Applica {pendingCount} feedback
              </Button>
            ) : null}
            <div className="relative">
              <IconButton label="Altre azioni" onClick={() => setMenu(!menu)} className="bg-fill"><MoreHorizontal className="size-4" /></IconButton>
              {menu && (
                <div className="animate-fade material-thick absolute right-0 z-30 mt-2 w-56 overflow-hidden rounded-xl p-1 shadow-pop" onMouseLeave={() => setMenu(false)}>
                  <button disabled={!!activeJob || !videoCount} onClick={() => { setMenu(false); startEdit(); }} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-[14px] hover:bg-accent hover:text-white disabled:opacity-40">
                    <RefreshCw className="size-4" /> Rimonta da zero
                  </button>
                  <button
                    onClick={() => { setMenu(false); if (confirm("Eliminare definitivamente il progetto, le clip e i render?")) run("del", async () => { await api(`/api/projects/${project.id}`, { method: "DELETE" }); router.push("/"); }); }}
                    className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-[14px] text-red hover:bg-red hover:text-white"
                  >
                    <Trash2 className="size-4" /> Elimina progetto
                  </button>
                </div>
              )}
            </div>
          </>
        }
      />

      {activeJob && <div className="mb-6 rounded-2xl bg-surface p-4 shadow-card"><JobBar job={activeJob} /></div>}
      {failedJob && (
        <div className="mb-6 flex items-start gap-3 rounded-2xl bg-red/10 p-4 text-[14px]">
          <AlertTriangle className="mt-0.5 size-5 shrink-0 text-red" />
          <div className="min-w-0"><div className="font-medium text-red">L&apos;ultima elaborazione non è riuscita</div><p className="mt-0.5 break-words text-label-2">{failedJob.error}</p></div>
        </div>
      )}

      <div className="grid gap-8 lg:grid-cols-[minmax(320px,440px)_1fr]">
        <div className="lg:sticky lg:top-6 lg:self-start">
          <Player
            ref={player}
            src={src}
            timeline={version?.edl ?? null}
            feedback={project.feedback.filter((f) => f.version === version?.version)}
            rendering={version?.render_status === "rendering" || version?.render_status === "pending"}
            onComment={onComment}
          />
          {version && viewing !== project.current_version && (
            <p className="mt-3 text-center text-[13px] text-label-2">
              Stai guardando la v{viewing}. <button className="text-accent" onClick={() => setViewing(project.current_version)}>Torna all&apos;attuale</button>
            </p>
          )}
        </div>

        <div className="min-w-0">
          <Segmented
            className="mb-5 flex w-full overflow-x-auto"
            value={tab}
            onChange={setTab}
            options={[
              { value: "feedback", label: `Feedback${pendingCount ? ` · ${pendingCount}` : ""}` },
              { value: "clips", label: "Clip" },
              { value: "versions", label: "Versioni" },
              { value: "content", label: "Contenuti" },
              { value: "publish", label: "Pubblica" },
            ]}
          />
          {tab === "feedback" && (
            <FeedbackPanel project={project} at={at} focusKey={focusKey} onChanged={reload} onSeek={(t) => { player.current?.seek(t); setAt(t); }} />
          )}
          {tab === "clips" && <ClipsPanel project={project} onChanged={reload} />}
          {tab === "versions" && <VersionsPanel project={project} viewing={viewing} onView={setViewing} onChanged={reload} />}
          {tab === "content" && <ContentPanel project={project} onChanged={reload} />}
          {tab === "publish" && (
            project.versions.some((v) => v.version === project.current_version && v.render_status === "done") ? (
              <>
                <Section title={`Pubblica la v${project.current_version}`}>
                  <div className="p-4"><PublishForm projectId={project.id} version={project.current_version} onDone={posts.reload} /></div>
                </Section>
                {projectPosts.length > 0 && (
                  <Section title="Pubblicazioni di questo progetto">
                    {projectPosts.map((p) => <PostRow key={p.id} post={p} onChanged={posts.reload} />)}
                  </Section>
                )}
              </>
            ) : (
              <p className="rounded-xl bg-surface px-4 py-8 text-center text-[14px] text-label-2 shadow-card">Serve un render completato per pubblicare.</p>
            )
          )}
        </div>
      </div>
    </>
  );
}
