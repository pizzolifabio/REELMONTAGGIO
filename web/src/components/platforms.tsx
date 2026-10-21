import type { Platform } from "@/lib/api";

export const PLATFORMS: { id: Platform; name: string; short: string; color: string }[] = [
  { id: "instagram", name: "Instagram Reels", short: "Instagram", color: "linear-gradient(135deg,#feda75,#fa7e1e 30%,#d62976 60%,#962fbf 80%,#4f5bd5)" },
  { id: "youtube", name: "YouTube Shorts", short: "YouTube", color: "#ff0000" },
  { id: "tiktok", name: "TikTok", short: "TikTok", color: "#111111" },
];

export function PlatformBadge({ platform, size = 22 }: { platform: Platform; size?: number }) {
  const p = PLATFORMS.find((x) => x.id === platform)!;
  const letter = { instagram: "IG", youtube: "YT", tiktok: "TT" }[platform];
  return (
    <span
      className="inline-flex shrink-0 items-center justify-center rounded-[28%] font-bold text-white"
      style={{ width: size, height: size, background: p.color, fontSize: size * 0.38 }}
      aria-label={p.name}
      title={p.name}
    >
      {letter}
    </span>
  );
}
