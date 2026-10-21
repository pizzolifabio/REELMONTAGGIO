"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { CalendarDays, Clapperboard, Images, MessageCircleHeart, Settings, Sparkles } from "lucide-react";
import { Suspense, type ReactNode } from "react";
import { cn } from "./ui";

const NAV = [
  { href: "/", label: "Progetti", icon: Clapperboard },
  { href: "/schedule", label: "Calendario", icon: CalendarDays },
  { href: "/automations", label: "Automazioni DM", icon: MessageCircleHeart },
  { href: "/learning", label: "Self-Learning", icon: Sparkles },
  { href: "/library", label: "Libreria", icon: Images },
  { href: "/settings", label: "Impostazioni", icon: Settings },
];

function isActive(pathname: string, href: string) {
  return href === "/" ? pathname === "/" || pathname.startsWith("/projects") : pathname.startsWith(href);
}

export function Shell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-dvh">
      <aside className="material sticky top-0 hidden h-dvh w-[232px] shrink-0 flex-col border-r border-separator px-3 pt-5 pb-4 md:flex">
        <div className="mb-6 flex items-center gap-2.5 px-2">
          <div className="flex size-8 items-center justify-center rounded-[9px] bg-gradient-to-br from-[#ff375f] via-[#bf5af2] to-[#0a84ff] text-white shadow-[0_2px_6px_rgba(0,0,0,0.18)]">
            <Clapperboard className="size-[18px]" strokeWidth={2.2} />
          </div>
          <div>
            <div className="text-[15px] leading-tight font-semibold">Reel Studio</div>
            <div className="text-[11px] text-label-2">Montaggio e distribuzione</div>
          </div>
        </div>
        <Suspense fallback={<SideNav pathname="" />}>
          <WithPathname render={(p) => <SideNav pathname={p} />} />
        </Suspense>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <main className="mx-auto w-full max-w-[1280px] flex-1 px-4 pt-6 pb-28 md:px-8 md:pt-9 md:pb-12">{children}</main>
      </div>

      {/* tab bar su schermi piccoli */}
      <Suspense fallback={<TabBar pathname="" />}>
        <WithPathname render={(p) => <TabBar pathname={p} />} />
      </Suspense>
    </div>
  );
}

function WithPathname({ render }: { render: (pathname: string) => ReactNode }) {
  return <>{render(usePathname())}</>;
}

function SideNav({ pathname }: { pathname: string }) {
  return (
  <nav className="flex flex-col gap-0.5">
    {NAV.map(({ href, label, icon: Icon }) => {
      const active = isActive(pathname, href);
      return (
        <Link
          key={href}
          href={href}
          className={cn(
            "flex items-center gap-2.5 rounded-lg px-2.5 py-[7px] text-[14px] transition",
            active ? "bg-accent text-white" : "text-label hover:bg-fill",
          )}
        >
          <Icon className={cn("size-[18px]", active ? "text-white" : "text-accent")} strokeWidth={1.9} />
          {label}
        </Link>
      );
    })}
  </nav>
  );
}

function TabBar({ pathname }: { pathname: string }) {
  return (
  <nav className="material-thick fixed inset-x-0 bottom-0 z-40 flex justify-around border-t border-separator pt-1.5 pb-[max(env(safe-area-inset-bottom),8px)] md:hidden">
    {NAV.map(({ href, label, icon: Icon }) => {
      const active = isActive(pathname, href);
      return (
        <Link key={href} href={href} className={cn("flex flex-col items-center gap-0.5 px-1 text-[10px]", active ? "text-accent" : "text-label-2")}>
          <Icon className="size-6" strokeWidth={1.7} />
          {label.split(" ")[0]}
        </Link>
      );
    })}
  </nav>
  );
}
