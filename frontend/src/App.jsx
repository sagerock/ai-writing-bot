import { useState, useEffect } from 'react'
import { Routes, Route, Link, useNavigate, useLocation, Navigate } from 'react-router-dom'
import { initializeApp } from 'firebase/app'
import { getAuth, onAuthStateChanged, createUserWithEmailAndPassword, signInWithEmailAndPassword, signOut, sendEmailVerification, sendPasswordResetEmail } from 'firebase/auth'
import Chat from './components/Chat'
import ProjectsPanel from './components/ProjectsPanel'
import AccountPage from './components/AccountPage'
import MemoriesPage from './components/MemoriesPage'
import AdminPage from './components/AdminPage'
import AdminUsersPage from './components/AdminUsersPage'
import HomePage from './pages/HomePage'
import AuthPage from './pages/AuthPage'
import ModelDocsPage from './pages/ModelDocsPage'
import ModelsPage from './pages/ModelsPage'
import PricingPage from './pages/PricingPage'
import SubscriptionSuccess from './pages/SubscriptionSuccess'
import { API_URL } from './apiConfig'
import './App.css'

// IMPORTANT: Replace with your app's Firebase project configuration
const firebaseConfig = {
    apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
    authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
    projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
    storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
    messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
    appId: import.meta.env.VITE_FIREBASE_APP_ID,
    measurementId: import.meta.env.VITE_FIREBASE_MEASUREMENT_ID
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
const auth = getAuth(app);

function ProtectedRoute({ user, children }) {
    const location = useLocation();

    if (!user) {
        // Redirect them to the /login page, but save the current location they were
        // trying to go to. This allows us to send them back there after they log in.
        return <Navigate to="/login" state={{ from: location }} replace />;
    }

    return children;
}

function App() {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);
    const [info, setInfo] = useState('');
    const [error, setError] = useState('');
    const [history, setHistory] = useState([]);
    const [projects, setProjects] = useState({});
    const [projectsLoading, setProjectsLoading] = useState(false);
    const [projectsError, setProjectsError] = useState('');
    const [mobileProjectsDrawerOpen, setMobileProjectsDrawerOpen] = useState(false);
    const [userSettings, setUserSettings] = useState({
        simplifiedMode: true,
        defaultModel: 'auto',
        defaultTemperature: 0.7,
        alwaysAskMode: false
    });
    const navigate = useNavigate();
    const location = useLocation();

    const isMobile = window.innerWidth <= 768;

    useEffect(() => {
        const path = location.pathname;
        let title = "RomaLume - ";
        if (path === '/') {
            title += "Your intelligent assistant for research, writing, and discovery.";
        } else if (path === '/chat') {
            title += "Chat";
        } else if (path === '/account') {
            title += "My Account";
        } else if (path === '/admin') {
            title += "Admin Panel";
        } else if (path === '/login' || path === '/signup') {
            title += "Login & Signup";
        }
        document.title = title;
    }, [location]);

    const fetchProjects = async () => {
        if (!auth.currentUser) return;
        setProjectsLoading(true);
        setProjectsError('');
        try {
            const token = await auth.currentUser.getIdToken();
            const response = await fetch(`${API_URL}/projects`, {
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
                setUserSettings({
                    simplifiedMode: data.simplified_mode ?? true,
                    defaultModel: data.default_model ?? 'auto',
                    defaultTemperature: data.default_temperature ?? 0.7,
                    alwaysAskMode: data.always_ask_mode ?? false
                });
            }
        } catch (err) {
            console.error('Failed to fetch user settings:', err);
        }
    };

    useEffect(() => {
        const unsubscribe = onAuthStateChanged(auth, async (currentUser) => {
            if (currentUser) {
                const idTokenResult = await currentUser.getIdTokenResult();
                currentUser.isAdmin = idTokenResult.claims.admin === true;
                setUser(currentUser);
                fetchProjects();
                fetchUserSettings();
            } else {
                setUser(null);
                setHistory([]);
                setProjects({});
                setUserSettings({
                    simplifiedMode: true,
                    defaultModel: 'auto',
                    defaultTemperature: 0.7,
                    alwaysAskMode: false
                });
            }
            setLoading(false);
        });
        return () => unsubscribe();
    }, []);

    const handleResendVerification = async () => {
        setError('');
        setInfo('');
        if (user) {
            try {
                await sendEmailVerification(user);
                setInfo('A new verification email has been sent.');
            } catch (error) {
                setError('Failed to resend verification email. Please try again later.');
            }
        }
    };

    const handleLogout = async () => {
        try {
            await signOut(auth);
            navigate('/'); // Navigate to home after logout
        } catch (error) {
            setError('Failed to log out.');
        }
    };

    const handleLoadArchive = async (archiveId) => {
        if (!window.confirm("Are you sure you want to load this archive? It will replace your current chat.")) {
            return;
        }
        setError('');
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
        } catch (err) {
            setError(err.message);
            alert('Failed to load archive.');
        }
    };

    const handleUploadSuccess = (contextMessage) => {
        setHistory(prev => [...prev, contextMessage]);
    };

    const handleSelectDocument = (contextMessage) => {
        // This function now just receives the prepared context message from ProjectsPanel
        setHistory(prev => [...prev, contextMessage]);
    };

    const renderChatInterface = () => {
        if (!user) {
            return null;
        }

        return (
            <div className="App">
                <header className="App-header">
                    <div className="logo-container">
                        <img src="/logo.png" alt="RomaLume Logo" className="header-logo" />
                        {isMobile && !userSettings.simplifiedMode && (
                            <button className="hamburger" onClick={() => setMobileProjectsDrawerOpen(true)}>
                                &#9776;
                            </button>
                        )}
                    </div>
                    <div className="user-controls">
                        {user.displayName && <span>Welcome, {user.displayName}</span>}
                        {user.isAdmin && <Link to="/admin" className="account-button" title="Admin">⚙️</Link>}
                        <Link to="/account" className="account-button" title="My Account">👤</Link>
                        <button onClick={handleLogout}>Logout</button>
                    </div>
                </header>

                <div className="main-content">
                    {/* Desktop left panel - hidden in simplified mode */}
                    {!isMobile && !userSettings.simplifiedMode && (
                        <div className="left-panel">
                            <ProjectsPanel
                                auth={auth}
                                onLoadArchive={handleLoadArchive}
                                onSelectDocument={handleSelectDocument}
                                onUploadSuccess={handleUploadSuccess}
                            />
                        </div>
                    )}
                    {/* Mobile drawer for projects - hidden in simplified mode */}
                    {isMobile && mobileProjectsDrawerOpen && !userSettings.simplifiedMode && (
                        <>
                            <div className="mobile-drawer-backdrop" onClick={() => setMobileProjectsDrawerOpen(false)} />
                            <div className="mobile-drawer">
                                <ProjectsPanel
                                    auth={auth}
                                    onLoadArchive={handleLoadArchive}
                                    onSelectDocument={handleSelectDocument}
                                    onUploadSuccess={handleUploadSuccess}
                                />
                                <button className="close-drawer" onClick={() => setMobileProjectsDrawerOpen(false)}>×</button>
                            </div>
                        </>
                    )}
                    <div className={`chat-area ${userSettings.simplifiedMode ? 'simplified' : ''}`}>
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
        return <div>Loading...</div>; // Or a spinner component
    }

    return (
        <Routes>
            {/* Public-only routes */}
            <Route path="/" element={!user ? <HomePage /> : <Navigate to="/chat" />} />
            <Route path="/login" element={!user ? <AuthPage /> : <Navigate to="/chat" />} />
            <Route path="/register" element={!user ? <AuthPage /> : <Navigate to="/chat" />} />
            <Route path="/forgot-password" element={!user ? <AuthPage /> : <Navigate to="/chat" />} />
            <Route path="/model-docs" element={<ModelDocsPage />} />
            <Route path="/models" element={<ModelsPage />} />
            <Route path="/pricing" element={<PricingPage auth={auth} />} />

            {/* Protected routes */}
            <Route path="/subscribe/success" element={
                <ProtectedRoute user={user}>
                    <SubscriptionSuccess />
                </ProtectedRoute>
            } />
            <Route path="/chat" element={
                <ProtectedRoute user={user}>
                    {renderChatInterface()}
                </ProtectedRoute>
            } />
            <Route path="/account" element={
                <ProtectedRoute user={user}>
                    <AccountPage auth={auth} />
                </ProtectedRoute>
            } />
            <Route path="/account/memories" element={
                <ProtectedRoute user={user}>
                    <MemoriesPage auth={auth} />
                </ProtectedRoute>
            } />
            <Route path="/admin" element={
                <ProtectedRoute user={user}>
                    <AdminPage auth={auth} />
                </ProtectedRoute>
            } />
            <Route path="/admin/users" element={
                <ProtectedRoute user={user}>
                    <AdminUsersPage auth={auth} />
                </ProtectedRoute>
            } />
        </Routes>
    );
}

export default App
