import { Link } from 'react-router-dom';

export default function WorkspaceHeader({
  user,
  isSubscriber,
  darkMode,
  onToggleDarkMode,
  onLogout,
}) {
  return (
    <header className="App-header project-app-header">
      <Link to="/chat" className="project-brand" aria-label="RomaLume quick chat">
        <img src="/logo.png" alt="" className="header-logo" />
        <span>RomaLume</span>
      </Link>
      <nav className="project-primary-nav" aria-label="Workspace navigation">
        <Link to="/projects">Projects</Link>
        <Link to="/chat">Quick chat</Link>
      </nav>
      <div className="user-controls">
        <button
          className="theme-toggle-btn"
          onClick={onToggleDarkMode}
          title={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
        >
          {darkMode ? '☀️' : '🌙'}
        </button>
        {!isSubscriber && <Link to="/pricing" className="upgrade-button">Upgrade</Link>}
        {user?.isAdmin && <Link to="/admin" className="account-button">⚙️</Link>}
        <Link to="/account" className="account-button">👤</Link>
        <button onClick={onLogout}>Logout</button>
      </div>
    </header>
  );
}
