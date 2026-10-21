"use client";

import { UploadCloud } from "lucide-react";
import { useRef, useState } from "react";
import { cn } from "./ui";

export function DropZone({ accept, onFiles, title, hint, compact }: {
  accept: string; onFiles: (files: File[]) => void; title: string; hint?: string; compact?: boolean;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => input.current?.click()}
      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && input.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        if (e.dataTransfer.files.length) onFiles(Array.from(e.dataTransfer.files));
      }}
      className={cn(
        "flex cursor-pointer flex-col items-center justify-center rounded-xl border-[1.5px] border-dashed text-center transition",
        compact ? "gap-1 px-4 py-4" : "gap-2 px-6 py-8",
        over ? "border-accent bg-accent-tint" : "border-label-3/60 hover:border-accent/60 hover:bg-fill/50",
      )}
    >
      <UploadCloud className={cn("text-accent", compact ? "size-6" : "size-9")} strokeWidth={1.5} />
      <div className="text-[14px] font-medium">{title}</div>
      {hint && <div className="text-[12px] text-label-2">{hint}</div>}
      <input
        ref={input}
        type="file"
        multiple
        accept={accept}
        className="hidden"
        onChange={(e) => {
          if (e.target.files?.length) onFiles(Array.from(e.target.files));
          e.target.value = "";
        }}
      />
    </div>
  );
}
