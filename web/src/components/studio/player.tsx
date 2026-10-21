"use client";

import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from "react";
import { MessageSquarePlus, Pause, Play, Volume2, VolumeX } from "lucide-react";
import type { Feedback, Timeline } from "@/lib/api";
import { formatTime } from "@/lib/hooks";
import { cn } from "../ui";

const CLIP_COLORS = ["#0a84ff", "#bf5af2", "#ff9f0a", "#30d158", "#ff375f", "#40c8e0", "#ffd60a", "#ac8e68"];

export type PlayerHandle = { seek: (t: number) => void; pause: () => void; time: () => number };

type Props = {
  src: string | null;
  timeline: Timeline | null;
  feedback: Feedback[];
  rendering?: boolean;
  onComment: (time: number) => void;
};

export const Player = forwardRef<PlayerHandle, Props>(function Player({ src, timeline, feedback, rendering, onComment }, ref) {
  const video = useRef<HTMLVideoElement>(null);
  const track = useRef<HTMLDivElement>(null);
  const [time, setTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [muted, setMuted] = useState(false);

  const total = duration || (timeline ? timeline.clips.reduce((a, c) => a + c.out - c.in, 0) : 0);

  useImperativeHandle(ref, () => ({
    seek: (t) => { if (video.current) video.current.currentTime = t; setTime(t); },
    pause: () => video.current?.pause(),
    time: () => video.current?.currentTime ?? 0,
  }));

  const toggle = useCallback(() => {
    const v = video.current;
    if (!v) return;
    if (v.paused) v.play(); else v.pause();
  }, []);

  const comment = useCallback(() => {
    video.current?.pause();
    onComment(video.current?.currentTime ?? 0);
  }, [onComment]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName;
      if (["INPUT", "TEXTAREA", "SELECT"].includes(tag)) return;
      if (e.code === "Space") { e.preventDefault(); toggle(); }
      if (e.key === "c" || e.key === "C") { e.preventDefault(); comment(); }
      const v = video.current;
      if (v && e.key === "ArrowLeft") v.currentTime = Math.max(0, v.currentTime - (e.shiftKey ? 1 : 1 / 30));
      if (v && e.key === "ArrowRight") v.currentTime = Math.min(total, v.currentTime + (e.shiftKey ? 1 : 1 / 30));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [toggle, comment, total]);

  const seekFromPointer = (clientX: number) => {
    const rect = track.current?.getBoundingClientRect();
    if (!rect || !video.current || !total) return;
    const t = Math.min(Math.max((clientX - rect.left) / rect.width, 0), 1) * total;
    video.current.currentTime = t;
    setTime(t);
  };

  const sources = timeline ? Array.from(new Set(timeline.clips.map((c) => c.source))) : [];
  let offset = 0;

  return (
    <div className="flex flex-col gap-3">
      <div className="relative mx-auto aspect-[9/16] w-full max-w-[380px] overflow-hidden rounded-[22px] bg-black shadow-pop">
        {src ? (
          <video
            ref={video}
            key={src}
            src={src}
            playsInline
            muted={muted}
            className="size-full object-contain"
            onClick={toggle}
            onTimeUpdate={(e) => setTime(e.currentTarget.currentTime)}
            onLoadedMetadata={(e) => setDuration(e.currentTarget.duration)}
            onPlay={() => setPlaying(true)}
            onPause={() => setPlaying(false)}
          />
        ) : (
          <div className="flex size-full items-center justify-center px-10 text-center text-[14px] text-white/60">
            {rendering ? "Render in corso…" : "Il montaggio apparirà qui"}
          </div>
        )}
        {src && !playing && (
          <button aria-label="Riproduci" onClick={toggle} className="material absolute top-1/2 left-1/2 flex size-16 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full text-label shadow-pop transition active:scale-95">
            <Play className="ml-1 size-7 fill-current" />
          </button>
        )}
      </div>

      {/* controlli */}
      <div className="mx-auto w-full max-w-[560px] rounded-2xl bg-surface p-3 shadow-card">
        <div className="mb-2.5 flex items-center gap-2">
          <button aria-label={playing ? "Pausa" : "Riproduci"} onClick={toggle} disabled={!src} className="flex size-9 items-center justify-center rounded-full bg-fill transition hover:bg-fill-2 active:scale-95 disabled:opacity-40">
            {playing ? <Pause className="size-4 fill-current" /> : <Play className="ml-0.5 size-4 fill-current" />}
          </button>
          <div className="font-mono text-[13px] text-label-2 tabular">
            <span className="text-label">{formatTime(time, true)}</span> / {formatTime(total, true)}
          </div>
          <button aria-label={muted ? "Attiva audio" : "Disattiva audio"} onClick={() => setMuted(!muted)} className="ml-1 text-label-2 hover:text-label">
            {muted ? <VolumeX className="size-[18px]" /> : <Volume2 className="size-[18px]" />}
          </button>
          <button
            onClick={comment}
            disabled={!src}
            className="ml-auto inline-flex h-8 items-center gap-1.5 rounded-full bg-accent px-3.5 text-[13px] font-medium text-white transition hover:bg-accent-hover active:scale-[0.97] disabled:opacity-40"
          >
            <MessageSquarePlus className="size-4" /> Feedback qui <kbd className="ml-0.5 rounded bg-white/20 px-1 text-[11px]">C</kbd>
          </button>
        </div>

        <div
          ref={track}
          className="relative h-14 cursor-pointer touch-none select-none"
          onPointerDown={(e) => { e.currentTarget.setPointerCapture(e.pointerId); seekFromPointer(e.clientX); }}
          onPointerMove={(e) => e.buttons === 1 && seekFromPointer(e.clientX)}
        >
          {/* clip */}
          <div className="absolute inset-x-0 top-5 flex h-7 gap-[2px] overflow-hidden rounded-md">
            {timeline?.clips.map((c) => {
              const d = c.out - c.in;
              const color = CLIP_COLORS[sources.indexOf(c.source) % CLIP_COLORS.length];
              const el = (
                <div
                  key={c.id}
                  title={`${c.id} · ${formatTime(offset, true)} · ${d.toFixed(1)}s`}
                  className="h-full min-w-[3px] opacity-80"
                  style={{ flex: `${d} 0 0`, background: `linear-gradient(180deg, ${color}cc, ${color}88)` }}
                />
              );
              offset += d;
              return el;
            })}
          </div>
          {/* feedback */}
          {total > 0 && feedback.map((f) => (
            <div
              key={f.id}
              title={f.text}
              className={cn("absolute top-0 size-3 -translate-x-1/2 rounded-full ring-2 ring-surface", f.status === "applied" ? "bg-green" : f.status === "failed" ? "bg-red" : "bg-orange")}
              style={{ left: `${(f.timestamp / total) * 100}%` }}
            />
          ))}
          {/* testina */}
          {total > 0 && (
            <div className="pointer-events-none absolute top-3.5 bottom-0 w-[2px] -translate-x-1/2 rounded-full bg-label" style={{ left: `${(time / total) * 100}%` }}>
              <div className="absolute -top-1 left-1/2 size-2.5 -translate-x-1/2 rounded-full bg-label" />
            </div>
          )}
        </div>
        <div className="mt-1 flex justify-between text-[11px] text-label-3">
          <span>Spazio: play/pausa · ←/→: fotogramma · Shift: 1s</span>
          <span>{timeline?.clips.length ?? 0} tagli</span>
        </div>
      </div>
    </div>
  );
});
