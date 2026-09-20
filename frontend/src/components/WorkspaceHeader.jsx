import { Link } from 'react-router-dom';
import './WorkspaceHeader.css';

export default function WorkspaceHeader({
  user,
  darkMode,
  onToggleDarkMode,
  onLogout,
  sidebarOpen,
  onToggleSidebar,
}) {
  return (
    <header className="App-header project-app-header">
      <div className="project-brand-cluster">
        <Link to="/chat" className="project-brand" aria-label={`${user?.school?.brand_name || 'RomaLume'} quick chat`}>
          <span>{user?.school?.brand_name || 'RomaLume'}</span>
        </Link>
        {onToggleSidebar && (
          <button
            className={`sidebar-toggle project-sidebar-toggle ${sidebarOpen ? 'active' : ''}`}
            onClick={onToggleSidebar}
            title={sidebarOpen ? 'Hide recent chats' : 'Show recent chats'}
            aria-label={sidebarOpen ? 'Hide recent chats' : 'Show recent chats'}
            aria-expanded={sidebarOpen}
          >
            📁
          </button>
        )}
      </div>
      <nav className="project-primary-nav" aria-label="Workspace navigation">
        <Link to="/projects">Projects</Link>
        <Link to="/chat">Quick Chat</Link>
      </nav>
      <div className="user-controls">
        <button
          className="theme-toggle-btn"
          onClick={onToggleDarkMode}
          title={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
        >
          {darkMode ? '☀️' : '🌙'}
        </button>
        {user?.isAdmin && <Link to="/admin" className="account-button">⚙️</Link>}
        <Link to="/account" className="account-button">👤</Link>
        <button onClick={onLogout}>Logout</button>
      </div>
    </header>
  );
}
