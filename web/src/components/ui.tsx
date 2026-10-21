"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ButtonHTMLAttributes, type ReactNode } from "react";
import { CheckCircle2, Loader2, X, XCircle } from "lucide-react";

export function cn(...c: (string | false | null | undefined)[]) {
  return c.filter(Boolean).join(" ");
}

// --- Button ------------------------------------------------------------------------------------

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "filled" | "tinted" | "gray" | "plain" | "destructive";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
  icon?: ReactNode;
};

export function Button({ variant = "filled", size = "md", loading, icon, className, children, disabled, ...rest }: ButtonProps) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={cn(
        "inline-flex items-center justify-center gap-1.5 rounded-full font-medium whitespace-nowrap select-none",
        "transition-[background,transform,opacity] duration-150 ease-(--ease-apple) active:scale-[0.97] disabled:opacity-40 disabled:active:scale-100",
        size === "sm" && "h-7 px-3 text-[13px]",
        size === "md" && "h-9 px-4 text-[14px]",
        size === "lg" && "h-11 px-6 text-[15px]",
        variant === "filled" && "bg-accent text-white hover:bg-accent-hover",
        variant === "tinted" && "bg-accent-tint text-accent hover:brightness-95",
        variant === "gray" && "bg-fill text-label hover:bg-fill-2",
        variant === "plain" && "text-accent hover:bg-accent-tint px-2",
        variant === "destructive" && "bg-red/10 text-red hover:bg-red/15",
        className,
      )}
    >
      {loading ? <Loader2 className="size-4 animate-spin" /> : icon}
      {children}
    </button>
  );
}

export function IconButton({ label, className, children, ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return (
    <button
      {...rest}
      aria-label={label}
      title={label}
      className={cn("inline-flex size-8 items-center justify-center rounded-full text-label-2 transition hover:bg-fill hover:text-label active:scale-95 disabled:opacity-40", className)}
    >
      {children}
    </button>
  );
}

// --- Layout --------------------------------------------------------------------------------------

export function PageHeader({ title, subtitle, actions, back }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode; back?: ReactNode }) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {back}
        <h1 className="font-display text-[28px] leading-tight font-bold tracking-[-0.022em] md:text-[34px]">{title}</h1>
        {subtitle && <p className="mt-1 text-[15px] text-label-2">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn("rounded-2xl bg-surface shadow-card", className)}>{children}</div>;
}

/** Lista raggruppata "inset grouped" stile iOS/macOS. */
export function Section({ title, footer, children, action, className }: { title?: ReactNode; footer?: ReactNode; children: ReactNode; action?: ReactNode; className?: string }) {
  return (
    <section className={cn("mb-7", className)}>
      {(title || action) && (
        <div className="mb-1.5 flex items-end justify-between px-4">
          <h2 className="text-[13px] font-medium tracking-wide text-label-2 uppercase">{title}</h2>
          {action}
        </div>
      )}
      <div className="overflow-hidden rounded-xl bg-surface shadow-card">{children}</div>
      {footer && <p className="mt-1.5 px-4 text-[12px] leading-relaxed text-label-2">{footer}</p>}
    </section>
  );
}

export function Row({ children, className, onClick }: { children: ReactNode; className?: string; onClick?: () => void }) {
  const Comp = onClick ? "button" : "div";
  return (
    <Comp
      onClick={onClick}
      className={cn(
        "relative flex w-full items-center gap-3 px-4 py-3 text-left text-[15px]",
        "after:absolute after:right-0 after:bottom-0 after:left-4 after:h-px after:bg-separator last:after:hidden",
        onClick && "transition hover:bg-fill/60 active:bg-fill",
        className,
      )}
    >
      {children}
    </Comp>
  );
}

// --- Controlli -----------------------------------------------------------------------------------

export function Segmented<T extends string>({ value, onChange, options, className }: {
  value: T; onChange: (v: T) => void; options: { value: T; label: ReactNode }[]; className?: string;
}) {
  return (
    <div role="tablist" className={cn("inline-flex rounded-[9px] bg-fill p-0.5", className)}>
      {options.map((o) => (
        <button
          key={o.value}
          role="tab"
          aria-selected={value === o.value}
          onClick={() => onChange(o.value)}
          className={cn(
            "flex-1 rounded-[7px] px-3 py-1 text-[13px] font-medium whitespace-nowrap transition-all duration-200",
            value === o.value ? "bg-elevated text-label shadow-[0_1px_3px_rgba(0,0,0,0.12),0_0_0_0.5px_rgba(0,0,0,0.04)]" : "text-label-2 hover:text-label",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Toggle({ checked, onChange, label, disabled }: { checked: boolean; onChange: (v: boolean) => void; label?: string; disabled?: boolean }) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn("relative h-[31px] w-[51px] shrink-0 rounded-full transition-colors duration-200 disabled:opacity-40", checked ? "bg-green" : "bg-fill-2")}
    >
      <span className={cn("absolute top-[2px] left-[2px] size-[27px] rounded-full bg-white shadow-[0_3px_8px_rgba(0,0,0,0.15),0_3px_1px_rgba(0,0,0,0.06)] transition-transform duration-200 ease-(--ease-spring)", checked && "translate-x-5")} />
    </button>
  );
}

const fieldBase = "w-full rounded-[10px] bg-fill px-3 py-2 text-[15px] text-label placeholder:text-label-3 outline-none transition focus:bg-surface focus:ring-[3px] focus:ring-accent/35";

export function Field({ label, hint, children }: { label?: ReactNode; hint?: ReactNode; children: ReactNode }) {
  return (
    <label className="block">
      {label && <span className="mb-1.5 block text-[13px] font-medium text-label-2">{label}</span>}
      {children}
      {hint && <span className="mt-1 block text-[12px] text-label-2">{hint}</span>}
    </label>
  );
}

export function Input(props: React.ComponentProps<"input">) {
  return <input {...props} className={cn(fieldBase, "h-9", props.className)} />;
}

export function TextArea(props: React.ComponentProps<"textarea">) {
  return <textarea {...props} className={cn(fieldBase, "min-h-[88px] resize-y leading-relaxed", props.className)} />;
}

export function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={cn(fieldBase, "h-9 appearance-none bg-[url('data:image/svg+xml;utf8,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%2212%22 height=%2212%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%23888%22 stroke-width=%222.5%22><path d=%22m7 15 5 5 5-5M7 9l5-5 5 5%22/></svg>')] bg-[right_10px_center] bg-no-repeat pr-8", props.className)} />;
}

// --- Stato ---------------------------------------------------------------------------------------

const PILL_COLORS: Record<string, string> = {
  green: "bg-green/15 text-green", orange: "bg-orange/15 text-orange", red: "bg-red/15 text-red",
  blue: "bg-accent-tint text-accent", gray: "bg-fill text-label-2", purple: "bg-purple/15 text-purple",
};

export function Pill({ color = "gray", children, className }: { color?: keyof typeof PILL_COLORS | string; children: ReactNode; className?: string }) {
  return <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[12px] font-medium whitespace-nowrap", PILL_COLORS[color], className)}>{children}</span>;
}

export function Progress({ value, className }: { value: number; className?: string }) {
  return (
    <div className={cn("h-1 overflow-hidden rounded-full bg-fill", className)}>
      <div className="h-full rounded-full bg-accent transition-[width] duration-500 ease-(--ease-apple)" style={{ width: `${Math.max(2, value * 100)}%` }} />
    </div>
  );
}

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn("size-5 animate-spin text-label-3", className)} />;
}

export function EmptyState({ icon, title, text, action }: { icon: ReactNode; title: string; text?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-16 text-center">
      <div className="mb-4 text-label-3 [&_svg]:size-12 [&_svg]:stroke-[1.25]">{icon}</div>
      <h3 className="text-[17px] font-semibold">{title}</h3>
      {text && <p className="mt-1 max-w-sm text-[14px] leading-relaxed text-label-2">{text}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

// --- Sheet (finestra modale) ---------------------------------------------------------------------

export function Sheet({ open, onClose, title, children, footer, wide }: {
  open: boolean; onClose: () => void; title: ReactNode; children: ReactNode; footer?: ReactNode; wide?: boolean;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="animate-fade fixed inset-0 z-50 flex items-end justify-center bg-black/30 backdrop-blur-[2px] sm:items-center sm:p-6" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div role="dialog" aria-modal className={cn("animate-sheet flex max-h-[92vh] w-full flex-col overflow-hidden rounded-t-2xl bg-grouped shadow-pop sm:rounded-2xl", wide ? "sm:max-w-3xl" : "sm:max-w-lg")}>
        <div className="material-thick flex items-center justify-between border-b border-separator px-5 py-3.5">
          <h2 className="text-[17px] font-semibold">{title}</h2>
          <IconButton label="Chiudi" onClick={onClose} className="-mr-2 bg-fill"><X className="size-4" /></IconButton>
        </div>
        <div className="overflow-y-auto px-5 py-5">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-separator px-5 py-3.5">{footer}</div>}
      </div>
    </div>
  );
}

// --- Toast ---------------------------------------------------------------------------------------

type Toast = { id: number; kind: "ok" | "error"; text: string };
const ToastCtx = createContext<(kind: Toast["kind"], text: string) => void>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const push = useCallback((kind: Toast["kind"], text: string) => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, kind, text }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), kind === "error" ? 7000 : 3500);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="pointer-events-none fixed top-4 left-1/2 z-[60] flex w-full max-w-md -translate-x-1/2 flex-col items-center gap-2 px-4">
        {toasts.map((t) => (
          <div key={t.id} role="status" className="animate-toast material-thick pointer-events-auto flex items-start gap-2.5 rounded-2xl px-4 py-3 text-[14px] shadow-pop">
            {t.kind === "ok" ? <CheckCircle2 className="mt-px size-[18px] shrink-0 text-green" /> : <XCircle className="mt-px size-[18px] shrink-0 text-red" />}
            <span className="leading-snug">{t.text}</span>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

export function useToast() {
  return useContext(ToastCtx);
}

/** Esegue un'azione asincrona mostrando l'errore in un toast. */
export function useAction() {
  const toast = useToast();
  const [busy, setBusy] = useState<string | null>(null);
  const run = useCallback(async <T,>(key: string, fn: () => Promise<T>, okText?: string): Promise<T | undefined> => {
    setBusy(key);
    try {
      const r = await fn();
      if (okText) toast("ok", okText);
      return r;
    } catch (e) {
      toast("error", (e as Error).message);
    } finally {
      setBusy(null);
    }
  }, [toast]);
  return { busy, run };
}
