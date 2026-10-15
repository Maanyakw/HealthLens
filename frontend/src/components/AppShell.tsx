import Link from "next/link";
import type { ReactNode } from "react";
import { Icon, Logo } from "@/components/ui";
import ThemeSwitcher from "@/components/ThemeSwitcher";

export default function AppShell({
  active,
  children,
}: {
  active: "overview" | "assess";
  children: ReactNode;
}) {
  return (
    <div className="app">
      <aside className="side">
        <Logo tagline />
        <nav className="side-nav" aria-label="Main">
          <Link
            href="/dashboard"
            className={`side-link${active === "overview" ? " is-on" : ""}`}
            aria-current={active === "overview" ? "page" : undefined}
          >
            <Icon name="grid" size={20} />
            Overview
          </Link>
          <Link
            href="/assess"
            className={`side-link${active === "assess" ? " is-on" : ""}`}
            aria-current={active === "assess" ? "page" : undefined}
          >
            <Icon name="spark" size={20} />
            New assessment
          </Link>
        </nav>
        <div className="side-foot">
          <ThemeSwitcher />
        </div>
      </aside>

      <div className="app-main">
        <header className="topbar">
          <div className="topbar-logo">
            <Logo />
          </div>
          <div className="topbar-right">
            <span className="topbar-theme">
              <ThemeSwitcher />
            </span>
          </div>
        </header>
        {children}
      </div>
    </div>
  );
}
