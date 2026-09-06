import { NavLink } from "react-router-dom";
import {
  Activity,
  BedDouble,
  Bike,
  CalendarDays,
  Flag,
  Gauge,
  HeartPulse,
  Home,
  LineChart,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  Settings,
  Sparkles,
  UserRound,
  Watch,
  Waves,
  X,
} from "lucide-react";

const NAV = [
  {
    label: "Home",
    items: [{ to: "/dashboard", label: "Dashboard", icon: Home }],
  },
  {
    label: "Coach",
    items: [{ to: "/coach", label: "AI Coach", icon: Sparkles }],
  },
  {
    label: "Health & Recovery",
    items: [
      { to: "/health/recovery", label: "Recovery", icon: HeartPulse },
      { to: "/health/sleep", label: "Sleep", icon: Moon },
      { to: "/health/hrv", label: "HRV", icon: Waves },
      { to: "/health/stress", label: "Stress", icon: Gauge },
      { to: "/health/rhr", label: "Resting HR", icon: Activity },
      { to: "/health/daily", label: "Daily Health", icon: BedDouble },
    ],
  },
  {
    label: "Training",
    items: [
      { to: "/training/load", label: "Training Load", icon: LineChart },
      { to: "/training/volume", label: "Volume & ACWR", icon: Bike },
      { to: "/training/fitness", label: "Fitness", icon: Watch },
      { to: "/training/schedule", label: "Schedule", icon: CalendarDays },
      { to: "/training/season", label: "Season", icon: Flag },
    ],
  },
  {
    label: "Activities",
    items: [{ to: "/activities", label: "All activities", icon: Activity }],
  },
  {
    label: "Account",
    items: [
      { to: "/settings", label: "Settings", icon: Settings },
      { to: "/profile", label: "Profile", icon: UserRound },
    ],
  },
];

function NavItem({ to, label, icon: Icon, onNavigate, collapsed }) {
  return (
    <NavLink
      to={to}
      onClick={onNavigate}
      title={label}
      className={({ isActive }) =>
        `flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition ${
          collapsed ? "justify-center" : ""
        } ${
          isActive
            ? "bg-sage/20 font-semibold text-white"
            : "text-slate-300 hover:bg-white/5 hover:text-white"
        }`
      }
    >
      <Icon className="h-4 w-4 shrink-0 opacity-80" />
      {!collapsed && <span>{label}</span>}
    </NavLink>
  );
}

export default function Sidebar({
  open,
  onClose,
  collapsed = false,
  onToggleCollapse,
}) {
  return (
    <>
      <div
        className={`fixed inset-0 z-40 bg-black/40 transition lg:hidden ${
          open ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
        onClick={onClose}
      />
      <aside
        className={`fixed inset-y-0 left-0 z-50 flex h-screen w-72 shrink-0 flex-col border-r border-white/5 bg-[var(--aal-sidebar)] text-white transition-transform lg:static lg:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        } ${collapsed ? "lg:w-20" : "lg:w-72"}`}
      >
        <div
          className={`flex px-3 py-5 ${
            collapsed ? "flex-col items-center gap-3" : "items-center gap-2"
          }`}
        >
          <div
            className={`flex min-w-0 items-center gap-3 px-1 ${
              collapsed ? "justify-center" : "flex-1"
            }`}
          >
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-sage/20 text-sage-muted">
              <Activity className="h-5 w-5" />
            </div>
            {!collapsed && (
              <div className="min-w-0">
                <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-sage-muted">
                  Advance Athlete Lab
                </p>
                <p className="truncate text-sm font-semibold text-white">
                  Performance Hub
                </p>
              </div>
            )}
          </div>
          {onToggleCollapse ? (
            <button
              type="button"
              onClick={onToggleCollapse}
              className="hidden shrink-0 rounded-lg p-2 text-slate-400 hover:bg-white/5 hover:text-white lg:inline-flex"
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            >
              {collapsed ? (
                <PanelLeftOpen className="h-4 w-4" />
              ) : (
                <PanelLeftClose className="h-4 w-4" />
              )}
            </button>
          ) : null}
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-2 text-slate-400 hover:bg-white/5 lg:hidden"
            aria-label="Close sidebar"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <nav className="flex-1 space-y-6 overflow-y-auto px-3 pb-6">
          {NAV.map((group) => (
            <div key={group.label}>
              {!collapsed && (
                <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                  {group.label}
                </p>
              )}
              <div className="space-y-0.5">
                {group.items.map((item) => (
                  <NavItem
                    key={item.to}
                    {...item}
                    collapsed={collapsed}
                    onNavigate={onClose}
                  />
                ))}
              </div>
            </div>
          ))}
        </nav>
      </aside>
    </>
  );
}
