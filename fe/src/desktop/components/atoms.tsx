import type { ReactNode } from "react";
import type { FeaturedAxis, Site } from "../../shared/types";

/**
 * Visual atoms ported verbatim from fe/index.legacy.html lines 311-425.
 *
 * Includes the small helpers (tagHue, prettyTag, buildFeaturedNames) that
 * the consuming components share — kept here rather than in shared/ since
 * they are presentation concerns (palette, label prettification) used only
 * by desktop chip rendering.
 */

// Stable hash → palette for dynamic tags so same tag gets same color
// across renders.  Origin: fe/index.legacy.html:329-334.
const PALETTE = ["#5b6c8a", "#7c5e9a", "#3f7a6a", "#9a6e3a", "#8a5b6c", "#6a8a5b"];
export function tagHue(name: string): string {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) | 0;
  return PALETTE[Math.abs(h) % PALETTE.length] as string;
}

// "테마:대형견과함께" → "🎯 대형견과함께".  Origin: legacy.html:336-340.
export function prettyTag(name: string): string {
  if (typeof name !== "string") return name;
  if (name.startsWith("테마:")) return "🎯 " + name.slice(3);
  return name;
}

/**
 * Collection/facility chip rows skip names already shown as 대표축 chips.
 * Backend returns Korean labels; this mirror is what the dynamic-chip
 * filter uses to avoid duplicating axis chips in the long-tail rows.
 *
 * Origin: fe/index.legacy.html:321-326.
 */
export function buildFeaturedNames(axes: FeaturedAxis[] | null | undefined): Set<string> {
  return new Set((axes || []).map((a) => a.ko));
}

/** 원본: fe/index.legacy.html:342-351. */
export function PinDots({ row, axes }: { row: Site; axes: FeaturedAxis[] }) {
  const list = axes || [];
  return (
    <div className="flex gap-1">
      {list.map((a) =>
        row[`has_${a.id}`] ? (
          <span key={a.id} title={a.ko} className={`pin-pin ${a.id}`} />
        ) : null,
      )}
    </div>
  );
}

/** 원본: fe/index.legacy.html:353-367. */
export function DynamicChip({
  name,
  active,
  onClick,
  count,
}: {
  name: string;
  active: boolean;
  onClick: () => void;
  count?: number;
}) {
  const color = tagHue(name);
  const label = prettyTag(name);
  const baseStyle: React.CSSProperties = {
    background: `${color}14`,
    color,
    borderColor: `${color}33`,
    boxShadow: active ? `inset 0 0 0 1.5px ${color}` : undefined,
  };
  return (
    <button
      onClick={onClick}
      className="chip"
      style={baseStyle}
      title={count != null ? `${count}곳` : ""}
    >
      {active ? "● " : ""}
      {label}
      {count != null ? <span className="opacity-60 ml-1 num">{count}</span> : null}
    </button>
  );
}

/** 원본: fe/index.legacy.html:369-378. */
export function EtaBadge({
  minutes,
  within,
  error,
}: {
  minutes?: number;
  within?: boolean;
  error?: string;
}) {
  if (minutes == null && !error) return null;
  if (error)
    return (
      <span className="chip" title={error} style={{ opacity: 0.55 }}>
        🚗 ?
      </span>
    );
  const mins = minutes as number;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  const label = h > 0 ? `${h}시 ${m}분` : `${m}분`;
  const cls = within === false ? "chip" : "chip warm";
  const style: React.CSSProperties | undefined =
    within === false ? { opacity: 0.55, textDecoration: "line-through" } : undefined;
  return (
    <span className={cls} style={style}>
      🚗 {label}
    </span>
  );
}

/** 원본: fe/index.legacy.html:380-383. */
export function Chip({ children, tone }: { children: ReactNode; tone?: "warm" | "bark" | "" }) {
  const cls = tone === "warm" ? "chip warm" : tone === "bark" ? "chip bark" : "chip";
  return <span className={cls}>{children}</span>;
}

/** 원본: fe/index.legacy.html:385-393. */
export function Stat({ label, value, sub }: { label: string; value: string; sub?: string | null }) {
  return (
    <div className="flex flex-col">
      <span className="text-[10px] uppercase tracking-[0.18em] text-stone-500 font-medium">
        {label}
      </span>
      <span className="display num text-2xl font-semibold leading-tight">{value}</span>
      {sub && <span className="text-[11px] text-stone-500 mt-0.5">{sub}</span>}
    </div>
  );
}
