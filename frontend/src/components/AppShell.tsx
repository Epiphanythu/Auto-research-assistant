import { NavLink, useLocation } from "react-router-dom";
import {
  Beaker,
  FileSearch,
  Moon,
  ShieldCheck,
  Sun,
  Workflow,
  TrendingUp,
} from "lucide-react";
import { type PropsWithChildren, type ComponentType, type SVGProps, useEffect, useState } from "react";

/* ─── Types ─── */

interface NavItem {
  to: string;
  label: string;
  icon: ComponentType<SVGProps<SVGSVGElement>>;
}

/* ─── Theme Constants ─── */

const THEME_STORAGE_KEY = "theme";
type ThemeMode = "light" | "dark";

// readInitialTheme 从 localStorage 读取主题偏好，默认 light
function readInitialTheme(): ThemeMode {
  if (typeof window === "undefined") return "light";
  const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
  return stored === "dark" ? "dark" : "light";
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

  // 1. 主题状态：在挂载时同步 document.documentElement，并写入 localStorage
  const [theme, setTheme] = useState<ThemeMode>(() => readInitialTheme());
  useEffect(() => {
    const root = document.documentElement;
    if (theme === "dark") {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme]);
  const toggleTheme = () => setTheme((prev) => (prev === "dark" ? "light" : "dark"));

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
            {/* 主题切换按钮：与导航栏视觉风格保持一致 */}
            <button
              type="button"
              onClick={toggleTheme}
              aria-label={theme === "dark" ? "切换为浅色模式" : "切换为深色模式"}
              className="inline-flex h-8 w-8 items-center justify-center rounded-[var(--radius-pill)] transition-colors duration-150"
              style={{
                color: "var(--color-ink-secondary)",
                border: "1px solid var(--color-hairline)",
                background: "var(--color-canvas)",
              }}
            >
              {theme === "dark" ? (
                <Sun className="h-[15px] w-[15px]" strokeWidth={2} />
              ) : (
                <Moon className="h-[15px] w-[15px]" strokeWidth={2} />
              )}
            </button>
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
