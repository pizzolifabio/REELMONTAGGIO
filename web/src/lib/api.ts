export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}

async function parseError(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) return data.detail.map((d: { msg: string }) => d.msg).join(", ");
    return JSON.stringify(data);
  } catch {
    return `Errore ${res.status}`;
  }
}

export async function api<T = unknown>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, ...rest } = init;
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...rest,
      headers: json !== undefined ? { "Content-Type": "application/json", ...rest.headers } : rest.headers,
      body: json !== undefined ? JSON.stringify(json) : rest.body,
      cache: "no-store",
    });
  } catch {
    throw new ApiError("Backend non raggiungibile: avvialo con scripts/dev.sh", 0);
  }
  if (!res.ok) throw new ApiError(await parseError(res), res.status);
  return res.status === 204 ? (undefined as T) : res.json();
}

/** Upload multipart con avanzamento (fetch non espone il progresso di upload). */
export function upload<T = unknown>(path: string, files: File[], onProgress?: (p: number) => void, fields: Record<string, string> = {}): Promise<T> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    Object.entries(fields).forEach(([k, v]) => form.append(k, v));
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_URL}${path}`);
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress?.(e.loaded / e.total);
    xhr.onload = () => {
      let data: unknown = null;
      try { data = JSON.parse(xhr.responseText); } catch {}
      if (xhr.status >= 200 && xhr.status < 300) resolve(data as T);
      else reject(new ApiError((data as { detail?: string })?.detail ?? `Errore ${xhr.status}`, xhr.status));
    };
    xhr.onerror = () => reject(new ApiError("Upload non riuscito", 0));
    xhr.send(form);
  });
}

// --- Tipi ------------------------------------------------------------------------------------------

export type Job = {
  id: number; kind: string; project_id: number | null; status: "queued" | "running" | "done" | "failed";
  progress: number; message: string; error: string; created_at: string; finished_at: string | null;
};

export type Asset = {
  id: number; project_id: number | null; kind: "video" | "image" | "music"; label: string; filename: string;
  duration: number; width: number; height: number; has_audio: boolean; transcribed: boolean; position: number;
  url: string | null; thumb_url: string | null;
  transcript: { segments: { s: number; e: number; text: string }[]; words: { w: string; s: number; e: number }[] } | null;
};

export type Clip = { id: string; source: number; in: number; out: number; zoom?: { from?: number; to?: number }; transition_in?: string; note?: string };
export type Overlay = { id: string; kind: "image" | "text"; start: number; end: number; text?: string; asset?: number };
export type Timeline = {
  canvas: { width: number; height: number; fps: number };
  clips: Clip[];
  captions: Record<string, unknown>;
  overlays: Overlay[];
  music: { asset: number | null; volume: number };
  audio: Record<string, unknown>;
};

export type Version = {
  version: number; note: string; edl: Timeline; render_status: "pending" | "rendering" | "done" | "error";
  render_error: string; render_url: string | null; created_at: string;
};

export type Feedback = {
  id: number; project_id: number; version: number; timestamp: number; text: string; asset_id: number | null;
  status: "pending" | "applying" | "applied" | "failed"; applied_in_version: number | null; consolidated: boolean;
  created_at: string;
};

export type ProjectSummary = {
  id: number; name: string; status: "draft" | "processing" | "ready" | "error"; status_message: string;
  current_version: number; created_at: string; clip_count: number; thumb_url: string | null;
  render_url: string | null; job: Job | null;
};

export type ProjectDetail = ProjectSummary & {
  script: string; brief: string; music_asset_id: number | null; assets: Asset[]; versions: Version[];
  feedback: Feedback[]; has_content: boolean; jobs: Job[];
};

export type LeadMagnet = {
  type?: string; title?: string; subtitle?: string; intro?: string; closing?: string;
  sections?: { heading: string; body?: string; items?: string[] }[];
};

export type Content = {
  id: number; project_id: number; title: string; caption: string; hashtags: string; keyword: string;
  dm_message: string; lead_magnet: LeadMagnet; slug: string; pdf_url: string | null; public_url: string | null;
  resource_url: string; link: string | null;
};

export type Post = {
  id: number; project_id: number; project_name: string; version: number; platform: Platform;
  scheduled_at: string; title: string; caption: string; privacy: string;
  status: "scheduled" | "publishing" | "published" | "failed" | "cancelled";
  external_id: string; result_url: string; error: string; render_url: string | null;
};

export type Platform = "instagram" | "youtube" | "tiktok";

export type Automation = {
  id: number; name: string; project_id: number | null; project_name: string | null; ig_media_id: string;
  keyword: string; opening_message: string; button_label: string; dm_message: string; resource_url: string;
  require_follow: boolean; follow_message: string; public_reply: string; active: boolean; link: string;
  stats: Record<string, number>; total: number;
};

export type Lead = {
  id: number; automation_id: number; igsid: string; username: string; comment_text: string;
  status: "contacted" | "awaiting_follow" | "sent" | "error"; error: string; created_at: string; updated_at: string;
};

export type SkillChange = { path: string; reason: string; before: string; after: string };
export type Proposal = { id: number; summary: string; changes: SkillChange[]; feedback_ids: number[]; status: string; created_at: string };

export type AccountInfo = {
  platform: Platform; connected: boolean; username: string | null; expires_at: string | null;
  connected_at: string | null; app_configured: boolean;
};

export type SystemInfo = {
  ffmpeg: boolean; ffmpeg_captions: boolean; agent_provider: string; agent_available: boolean;
  whisper_model: string; chrome: boolean; public_base_url: string | null; webhook_url: string | null;
  verify_token: string; oauth_redirects: Record<Platform, string | null>; jobs: Job[];
};
