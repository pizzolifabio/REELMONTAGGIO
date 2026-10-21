"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";

/** Carica una risorsa e la ricarica a intervalli finché `pollWhile` restituisce true. */
export function useResource<T>(path: string | null, opts: { pollWhile?: (data: T) => boolean; interval?: number } = {}) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const optsRef = useRef(opts);
  optsRef.current = opts;

  const reload = useCallback(async () => {
    if (!path) return;
    try {
      const d = await api<T>(path);
      setData(d);
      setError(null);
      return d;
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [path]);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    let cancelled = false;
    const tick = async () => {
      const d = await reload();
      if (cancelled) return;
      const should = d && optsRef.current.pollWhile?.(d);
      timer = setTimeout(tick, should ? optsRef.current.interval ?? 1500 : 8000);
    };
    tick();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [reload]);

  return { data, error, loading, reload, setData };
}

export function formatTime(t: number, precise = false): string {
  if (!Number.isFinite(t)) t = 0;
  const m = Math.floor(t / 60);
  const s = t - m * 60;
  return precise ? `${String(m).padStart(2, "0")}:${s.toFixed(1).padStart(4, "0")}` : `${m}:${String(Math.floor(s)).padStart(2, "0")}`;
}

export function formatDate(iso: string, opts: Intl.DateTimeFormatOptions = { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) {
  return new Date(iso.endsWith("Z") || iso.includes("+") ? iso : `${iso}Z`).toLocaleString("it-IT", opts);
}
