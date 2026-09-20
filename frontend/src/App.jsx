import { lazy, Suspense, useState, useEffect } from 'react'
import { Routes, Route, useNavigate, useLocation, Navigate } from 'react-router-dom'
import { auth, onAuthStateChanged, signOut } from './auth/authClient'
import Chat from './components/Chat'
import RecentChats from './components/RecentChats'
import WorkspaceHeader from './components/WorkspaceHeader'
import HomePage from './pages/HomePage'
import AuthPage from './pages/AuthPage'
import { API_URL } from './apiConfig'
import './App.css'

const AccountPage = lazy(() => import('./components/AccountPage'));
const AdminPage = lazy(() => import('./components/AdminPage'));
const AdminUsersPage = lazy(() => import('./components/AdminUsersPage'));
const ModelDocsPage = lazy(() => import('./pages/ModelDocsPage'));
const ModelsPage = lazy(() => import('./pages/ModelsPage'));
const AboutPage = lazy(() => import('./pages/AboutPage'));
const AuthActionPage = lazy(() => import('./pages/AuthActionPage'));
const ProjectsHome = lazy(() => import('./pages/ProjectsHome'));
const ProjectWorkspace = lazy(() => import('./pages/ProjectWorkspace'));

// Auth is Supabase; see src/auth/authClient.js.

function ProtectedRoute({ user, children }) {
    const location = useLocation();

    if (!user) {
        // Redirect them to the /login page, but save the current location they were
        // trying to go to. This allows us to send them back there after they log in.
        return <Navigate to="/login" state={{ from: location }} replace />;
    }

    return children;
}

function AdminRoute({ user, children }) {
    if (!user) {
        return <Navigate to="/login" replace />;
    }
    if (!user.isAdmin) {
        return <Navigate to="/chat" replace />;
    }
    return children;
}

function AuthRedirect() {
    return <Navigate to="/chat" replace />;
}

function App() {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);
    const [history, setHistory] = useState([]);
    const [projects, setProjects] = useState({});
    const [, setProjectsLoading] = useState(false);
    const [, setProjectsError] = useState('');
    const [sidebarOpen, setSidebarOpen] = useState(false);
    const [isSubscriber, setIsSubscriber] = useState(false);
    const [userSettings, setUserSettings] = useState({
        simplifiedMode: true,
        defaultModel: 'auto',
        defaultTemperature: 0.7,
        alwaysAskMode: false,
        darkMode: true
    });
    const navigate = useNavigate();
    const location = useLocation();

    const isMobile = window.innerWidth <= 768;

    useEffect(() => {
        const path = location.pathname;
        const brand = user?.school?.brand_name || 'RomaLume';
        const base = `${brand} - AI Writing Assistant`;
        let title = base;
        if (path === '/chat') {
            title = `${brand} - Chat`;
        } else if (path === '/projects') {
            title = `${brand} - Projects`;
        } else if (path.startsWith('/projects/')) {
            title = `${brand} - Project Workspace`;
        } else if (path === '/account') {
            title = `${brand} - My Account`;
        } else if (path === '/admin') {
            title = `${brand} - Admin Panel`;
        } else if (path === '/admin/users') {
            title = `${brand} - Admin Users`;
        } else if (path === '/login' || path === '/register') {
            title = `${brand} - Login`;
        } else if (path === '/about') {
            title = `${brand} - About`;
        } else if (path === '/models') {
            title = `${brand} - Models`;
        }
        document.title = title;
    }, [location, user]);

    // Sync dark mode with DOM and localStorage
    useEffect(() => {
        if (userSettings.darkMode) {
            document.documentElement.classList.add('dark');
        } else {
            document.documentElement.classList.remove('dark');
        }
        localStorage.setItem('romalume-dark-mode', String(userSettings.darkMode));
    }, [userSettings.darkMode]);

    const fetchProjects = async () => {
        if (!auth.currentUser) return;
        setProjectsLoading(true);
        setProjectsError('');
        try {
            const token = await auth.currentUser.getIdToken();
            const response = await fetch(`${API_URL}/legacy-projects`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (!response.ok) {
                throw new Error('Failed to fetch projects.');
            }
            const data = await response.json();
            setProjects(data);
        } catch (err) {
            setProjectsError(err.message);
        } finally {
            setProjectsLoading(false);
        }
    };

    const fetchUserSettings = async () => {
        if (!auth.currentUser) return;
        try {
            const token = await auth.currentUser.getIdToken();
            const response = await fetch(`${API_URL}/user/chat-settings`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (response.ok) {
                const data = await response.json();
                const darkMode = data.dark_mode ?? true;
                setUserSettings({
                    simplifiedMode: data.simplified_mode ?? true,
                    defaultModel: data.default_model ?? 'auto',
                    defaultTemperature: data.default_temperature ?? 0.7,
                    alwaysAskMode: data.always_ask_mode ?? false,
                    darkMode
                });
                localStorage.setItem('romalume-dark-mode', String(darkMode));
            }
        } catch (err) {
            console.error('Failed to fetch user settings:', err);
        }
    };

    const checkSubscription = async () => {
        if (!auth.currentUser) return;
        try {
            const token = await auth.currentUser.getIdToken();
            const response = await fetch(`${API_URL}/user/subscription`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (response.ok) {
                const data = await response.json();
                setIsSubscriber(data.status === 'active');
            }
        } catch (err) {
            console.error('Error checking subscription:', err);
        }
    };

    useEffect(() => {
        let settled = false;

        const unsubscribe = onAuthStateChanged(auth, async (currentUser) => {
            settled = true;
            if (currentUser) {
                try {
                    const token = await currentUser.getIdToken();
                    const controller = new AbortController();
                    const timer = setTimeout(() => controller.abort(), 5000);
                    const res = await fetch(`${API_URL}/user/me`, {
                        headers: { Authorization: `Bearer ${token}` },
                        signal: controller.signal,
                    });
                    clearTimeout(timer);
                    if (res.ok) {
                        const me = await res.json();
                        currentUser.isAdmin = me.is_admin === true;
                        currentUser.school = me.school || null;
                        currentUser.displayName = me.display_name || currentUser.displayName;
                    } else {
                        currentUser.isAdmin = false;
                    }
                } catch (err) {
                    console.error('Error loading account:', err);
                    currentUser.isAdmin = false;
                }
                setUser(currentUser);
                fetchProjects();
                fetchUserSettings();
                checkSubscription();
            } else {
                setUser(null);
                setHistory([]);
                setProjects({});
                setIsSubscriber(false);
                setUserSettings({
                    simplifiedMode: true,
                    defaultModel: 'auto',
                    defaultTemperature: 0.7,
                    alwaysAskMode: false,
                    darkMode: true
                });
                localStorage.removeItem('romalume-dark-mode');
            }
            setLoading(false);
        });

        // Fallback: if auth never fires within 5s, stop loading
        const timeout = setTimeout(() => {
            if (!settled) {
                console.warn('Auth initialization timed out — continuing as logged out');
                setLoading(false);
            }
        }, 5000);

        return () => {
            unsubscribe();
            clearTimeout(timeout);
        };
    }, []);

    const handleLogout = async () => {
        try {
            await signOut(auth);
            navigate('/'); // Navigate to home after logout
        } catch (err) {
            console.error('Failed to log out:', err);
        }
    };

    const handleLoadArchive = async (archiveId) => {
        if (!window.confirm("Are you sure you want to load this archive? It will replace your current chat.")) {
            return false;
        }
        try {
            const token = await auth.currentUser.getIdToken();
            const response = await fetch(`${API_URL}/archive/${archiveId}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!response.ok) {
                throw new Error('Failed to load archive.');
            }
            const data = await response.json();
            if (data.messages) {
                setHistory(data.messages);
            }
            return true;
        } catch (err) {
            console.error(err);
            alert('Failed to load archive.');
            return false;
        }
    };

    const handleOpenQuickChat = async (archiveId) => {
        const loaded = await handleLoadArchive(archiveId);
        if (loaded) navigate('/chat');
    };

    const handleSelectDocument = (contextMessage) => {
        // This function now just receives the prepared context message from ProjectsPanel
        setHistory(prev => [...prev, contextMessage]);
    };

    const handleToggleDarkMode = () => {
        const newValue = !userSettings.darkMode;
        setUserSettings(prev => ({ ...prev, darkMode: newValue }));
        localStorage.setItem('romalume-dark-mode', String(newValue));
        // Fire-and-forget API save
        if (auth.currentUser) {
            auth.currentUser.getIdToken().then(token => {
                fetch(`${API_URL}/user/chat-settings`, {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        simplified_mode: userSettings.simplifiedMode,
                        default_model: userSettings.defaultModel,
                        default_temperature: userSettings.defaultTemperature,
                        always_ask_mode: userSettings.alwaysAskMode,
                        dark_mode: newValue
                    })
                }).catch(() => {});
            });
        }
    };

    const renderChatInterface = () => {
        if (!user) {
            return null;
        }

        return (
            <div className={`App quick-chat-shell ${userSettings.darkMode ? 'dark' : ''}`}>
                <WorkspaceHeader
                    user={user}
                    isSubscriber={isSubscriber}
                    darkMode={userSettings.darkMode}
                    onToggleDarkMode={handleToggleDarkMode}
                    onLogout={handleLogout}
                    sidebarOpen={sidebarOpen}
                    onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
                />

                <div className="main-content">
                    {/* Collapsible sidebar - works on both desktop and mobile */}
                    <div className={`left-panel ${sidebarOpen ? 'open' : 'closed'}`}>
                        <RecentChats
                            auth={auth}
                            onLoadChat={handleLoadArchive}
                            onLoadDocument={handleSelectDocument}
                        />
                    </div>
                    {/* Backdrop for mobile when sidebar is open */}
                    {isMobile && sidebarOpen && (
                        <div className="sidebar-backdrop" onClick={() => setSidebarOpen(false)} />
                    )}
                    <div className="chat-area">
                        <Chat
                            auth={auth}
                            history={history}
                            setHistory={setHistory}
                            projectNames={Object.keys(projects)}
                            onSaveSuccess={fetchProjects}
                            simplifiedMode={userSettings.simplifiedMode}
                            defaultModel={userSettings.defaultModel}
                            defaultTemperature={userSettings.defaultTemperature}
                        />
                    </div>
                </div>
            </div>
        );
    };

    if (loading) {
        return (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', background: '#0f0d0a' }}>
                <div style={{ textAlign: 'center', color: '#b5ada0', fontFamily: 'DM Sans, sans-serif' }}>
                    <img src="/logo.png" alt="RomaLume" style={{ height: 48, marginBottom: 16, opacity: 0.8 }} />
                    <div style={{ fontSize: '0.9rem' }}>Loading...</div>
                </div>
            </div>
        );
    }

    return (
        <Suspense fallback={<div className="loading-screen">Loading…</div>}>
        <Routes>
            {/* Public-only routes */}
            <Route path="/" element={!user ? <HomePage /> : <Navigate to="/chat" />} />
            <Route path="/login" element={!user ? <AuthPage /> : <AuthRedirect />} />
            <Route path="/register" element={!user ? <AuthPage /> : <AuthRedirect />} />
            <Route path="/forgot-password" element={!user ? <AuthPage /> : <Navigate to="/chat" />} />
            <Route path="/model-docs" element={<ModelDocsPage />} />
            <Route path="/models" element={<ModelsPage />} />
            <Route path="/about" element={<AboutPage />} />
            <Route path="/auth/action" element={<AuthActionPage />} />

            {/* Protected routes */}
            <Route path="/chat" element={
                <ProtectedRoute user={user}>
                    {renderChatInterface()}
                </ProtectedRoute>
            } />
            <Route path="/projects" element={
                <ProtectedRoute user={user}>
                    <ProjectsHome
                        auth={auth}
                        user={user}
                        isSubscriber={isSubscriber}
                        darkMode={userSettings.darkMode}
                        onToggleDarkMode={handleToggleDarkMode}
                        onLogout={handleLogout}
                        onOpenQuickChat={handleOpenQuickChat}
                    />
                </ProtectedRoute>
            } />
            <Route path="/projects/:projectId" element={
                <ProtectedRoute user={user}>
                    <ProjectWorkspace
                        auth={auth}
                        user={user}
                        isSubscriber={isSubscriber}
                        darkMode={userSettings.darkMode}
                        onToggleDarkMode={handleToggleDarkMode}
                        onLogout={handleLogout}
                    />
                </ProtectedRoute>
            } />
            <Route path="/account" element={
                <ProtectedRoute user={user}>
                    <AccountPage auth={auth} />
                </ProtectedRoute>
            } />
            <Route path="/admin" element={
                <AdminRoute user={user}>
                    <AdminPage auth={auth} />
                </AdminRoute>
            } />
            <Route path="/admin/users" element={
                <AdminRoute user={user}>
                    <AdminUsersPage auth={auth} />
                </AdminRoute>
            } />
        </Routes>
        </Suspense>
    );
}

export default App
