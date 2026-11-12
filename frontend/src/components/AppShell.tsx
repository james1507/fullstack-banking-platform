import { useState } from 'react';
import {
  ArrowLeftRight,
  ArrowUpRight,
  ChevronDown,
  CircleHelp,
  CreditCard,
  LayoutDashboard,
  LogOut,
  ShieldCheck,
  Sparkles,
  UsersRound,
  FileText,
  CalendarClock,
  Bell,
} from 'lucide-react';
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../auth';
import { ErrorAlert } from './ui';

export function AppShell() {
  const { user, logout } = useAuth();
  const { pathname } = useLocation();
  const [error, setError] = useState<unknown>(null);
  const [leaving, setLeaving] = useState(false);
  const section =
    [
      ['/accounts', 'Accounts'],
      ['/transfers/new', 'New transfer'],
      ['/transfers', 'Transactions'],
      ['/beneficiaries', 'Recipients'],
      ['/statements', 'Statements'],
      ['/scheduled-transfers', 'Schedules'],
      ['/notifications', 'Inbox'],
      ['/ops', 'Account controls'],
      ['/audit', 'Audit trail'],
      ['/about', 'About'],
    ].find(([path]) => pathname === path || pathname.startsWith(`${path}/`))?.[1] || 'Overview';
  async function signOut() {
    setLeaving(true);
    try {
      await logout();
    } catch (e) {
      setError(e);
    } finally {
      setLeaving(false);
    }
  }
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link to="/" className="brand">
          <span className="brand-symbol">m</span> moneta<span className="brand-dot">.</span>
        </Link>
        <span className="nav-label">WORKSPACE</span>
        <nav className="main-nav" aria-label="Main navigation">
          <NavLink end to="/">
            <LayoutDashboard size={19} /> Overview
          </NavLink>
          {user?.role === 'CUSTOMER' && (
            <>
              <NavLink to="/accounts">
                <CreditCard size={19} /> My accounts
              </NavLink>
              <NavLink to="/transfers" end>
                <ArrowLeftRight size={19} /> Transactions
              </NavLink>
              <NavLink to="/transfers/new">
                <ArrowUpRight size={19} /> Send money
              </NavLink>
              <NavLink to="/beneficiaries">
                <UsersRound size={19} /> Recipients
              </NavLink>
              <NavLink to="/statements">
                <FileText size={19} /> Statements
              </NavLink>
              <NavLink to="/scheduled-transfers">
                <CalendarClock size={19} /> Schedules
              </NavLink>
              <NavLink to="/notifications">
                <Bell size={19} /> Inbox
              </NavLink>
            </>
          )}
          {user?.role === 'OPERATIONS' && (
            <NavLink to="/ops">
              <ShieldCheck size={19} /> Account controls
            </NavLink>
          )}
          {user?.role !== 'CUSTOMER' && (
            <NavLink to="/audit">
              <ShieldCheck size={19} /> Audit trail
            </NavLink>
          )}
        </nav>
        <div className="sidebar-bottom">
          <div className="sandbox-card">
            <span className="sandbox-icon">
              <Sparkles size={19} />
            </span>
            <h3>A safe place to explore.</h3>
            <p>
              Real banking experience.
              <br />
              Entirely fictional money.
            </p>
            <a
              href="https://www.postgresql.org/docs/current/explicit-locking.html"
              target="_blank"
              rel="noreferrer"
            >
              Built with care <ArrowUpRight size={14} />
            </a>
          </div>
          <div className="sidebar-security">
            <ShieldCheck size={16} /> Simulation environment
          </div>
          <button className="logout-button" disabled={leaving} onClick={() => void signOut()}>
            <LogOut size={18} /> {leaving ? 'Signing out…' : 'Sign out'}
          </button>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="breadcrumb">
            Workspace <span>/</span> <strong>{section}</strong>
          </div>
          <div className="topbar-right">
            <span className="demo-badge">
              <span /> Demo · Simulated money
            </span>
            <Link to="/about" className="icon-button help-button" aria-label="About this demo">
              <CircleHelp size={19} />
            </Link>
            <span className="topbar-divider" />
            <span className="avatar">{user?.display_name.charAt(0)}</span>
            <span className="user-name">
              {user?.display_name}
              <small>{user?.role === 'CUSTOMER' ? 'Personal workspace' : user?.role}</small>
            </span>
            <ChevronDown className="user-chevron" size={15} />
            <button
              className="icon-button mobile-signout"
              aria-label="Sign out"
              disabled={leaving}
              onClick={() => void signOut()}
            >
              <LogOut size={16} />
            </button>
          </div>
        </header>
        <main className="main-content">
          {error != null && <ErrorAlert error={error} />}
          <Outlet />
        </main>
        <footer className="app-footer">
          <span>Thoughtfully built. Safely simulated.</span>
          <span>
            <ShieldCheck size={13} /> No real money. No external banking services.
          </span>
        </footer>
      </div>
    </div>
  );
}
