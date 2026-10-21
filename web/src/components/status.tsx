import type { Job, ProjectSummary } from "@/lib/api";
import { Pill, Progress } from "./ui";

const JOB_LABEL: Record<string, string> = {
  process_project: "Montaggio", apply_feedback: "Revisione", render: "Render", generate_content: "Contenuti",
  self_learning: "Self-Learning", publish: "Pubblicazione", export_pdf: "PDF",
};

export function ProjectStatus({ project }: { project: Pick<ProjectSummary, "status" | "current_version"> }) {
  if (project.status === "processing") return <Pill color="blue">In lavorazione</Pill>;
  if (project.status === "error") return <Pill color="red">Errore</Pill>;
  if (project.status === "ready") return <Pill color="green">Versione {project.current_version}</Pill>;
  return <Pill>Bozza</Pill>;
}

export function JobBar({ job }: { job: Job | null }) {
  if (!job || job.status === "done") return null;
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-[12px] text-label-2">
        <span>{job.status === "queued" ? "In coda" : job.message || JOB_LABEL[job.kind]}</span>
        <span className="tabular">{Math.round(job.progress * 100)}%</span>
      </div>
      <Progress value={job.progress} />
    </div>
  );
}

export function jobLabel(kind: string) {
  return JOB_LABEL[kind] ?? kind;
}
