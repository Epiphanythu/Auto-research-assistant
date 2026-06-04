import { NavLink, useLocation } from "react-router-dom";
import {
  Beaker,
  FileSearch,
  ShieldCheck,
  Workflow,
  TrendingUp,
} from "lucide-react";
import { type PropsWithChildren, type ComponentType, type SVGProps } from "react";

/* ─── Types ─── */

interface NavItem {
  to: string;
  label: string;
  icon: ComponentType<SVGProps<SVGSVGElement>>;
}

/* ─── Navigation Config ─── */

const navigationItems: NavItem[] = [
  { to: "/", label: "工作台", icon: Workflow },
  { to: "/review", label: "结构化综述", icon: FileSearch },
  { to: "/evidence", label: "证据与核验", icon: ShieldCheck },
  { to: "/trends", label: "趋势分析", icon: TrendingUp },
];

/* ─── Active link style helper ─── */

function navLinkClass({ isActive }: { isActive: boolean }): string {
  const base =
    "inline-flex items-center gap-2 px-4 py-2 text-[var(--font-caption)] font-[var(--weight-caption)] tracking-[var(--tracking-caption)] rounded-[var(--radius-pill)] transition-all duration-150";
  if (isActive) {
    return `${base} bg-[var(--color-primary)] text-white shadow-sm`;
  }
  return `${base} text-[var(--color-ink-secondary)] hover:text-[var(--color-ink)] hover:bg-[var(--color-canvas-soft)]`;
}

/* ─── Component ─── */

export function AppShell({ children }: PropsWithChildren) {
  const location = useLocation();

  return (
    <div className="min-h-screen bg-[var(--color-canvas-soft)]">
      {/* ── Gradient mesh decorative strip at the very top ── */}
      <div
        className="stripe-mesh pointer-events-none fixed inset-x-0 top-0 h-[320px] -z-10 opacity-50"
        aria-hidden="true"
      />

      {/* ── Top navigation bar ── */}
      <header
        className="fixed inset-x-0 top-0 z-50"
        style={{ height: "var(--nav-height)" }}
      >
        <div className="mx-auto flex h-full max-w-[1280px] items-center justify-between px-6">
          {/* Logo */}
          <NavLink
            to="/"
            className="flex items-center gap-2.5 transition-opacity hover:opacity-80"
          >
            <div
              className="flex h-9 w-9 items-center justify-center rounded-[var(--radius-md)]"
              style={{ background: "var(--color-primary)" }}
            >
              <Beaker className="h-4.5 w-4.5 text-white" strokeWidth={2} />
            </div>
            <span
              className="text-[18px] font-[var(--weight-display)] tracking-[-0.4px]"
              style={{ color: "var(--color-ink)" }}
            >
              科研助手
            </span>
          </NavLink>

          {/* Navigation links */}
          <nav className="flex items-center gap-1">
            {navigationItems.map((item) => {
              const Icon = item.icon;
              const isActive =
                item.to === "/"
                  ? location.pathname === "/"
                  : location.pathname.startsWith(item.to);

              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={navLinkClass({ isActive })}
                >
                  <Icon className="h-[15px] w-[15px]" strokeWidth={2} />
                  <span>{item.label}</span>
                </NavLink>
              );
            })}
          </nav>

          {/* Right-side placeholder (user avatar / settings) */}
          <div className="flex items-center gap-3">
            <div
              className="h-8 w-8 rounded-[var(--radius-pill)]"
              style={{
                background:
                  "linear-gradient(135deg, var(--color-primary-subdued), var(--color-primary))",
              }}
            />
          </div>
        </div>

        {/* Bottom hairline */}
        <div
          className="absolute inset-x-0 bottom-0 h-px"
          style={{ background: "var(--color-hairline)" }}
        />
      </header>

      {/* ── Main content ── */}
      <main
        className="mx-auto max-w-[1280px] px-6"
        style={{ paddingTop: "calc(var(--nav-height) + 24px)" }}
      >
        {children}
      </main>
    </div>
  );
}
