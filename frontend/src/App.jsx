import { useState, useEffect } from 'react'
import { Routes, Route, Link, useNavigate, useLocation, Navigate } from 'react-router-dom'
import { initializeApp } from 'firebase/app'
import { getAuth, onAuthStateChanged, createUserWithEmailAndPassword, signInWithEmailAndPassword, signOut, sendEmailVerification, sendPasswordResetEmail } from 'firebase/auth'
import Chat from './components/Chat'
import ArchivesPanel from './components/ArchivesPanel'
import DocumentsPanel from './components/DocumentsPanel'
import AccountPage from './components/AccountPage'
import AdminPage from './components/AdminPage'
import HomePage from './pages/HomePage'
import AuthPage from './pages/AuthPage'
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
    const [archives, setArchives] = useState({});
    const [archivesLoading, setArchivesLoading] = useState(false);
    const [archivesError, setArchivesError] = useState('');
    const [selectedDocument, setSelectedDocument] = useState(null);
    const navigate = useNavigate();

    const fetchArchives = async () => {
        if (!auth.currentUser) return;
        setArchivesLoading(true);
        setArchivesError('');
        try {
            const token = await auth.currentUser.getIdToken();
            const response = await fetch(`${API_URL}/archives`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (!response.ok) {
                throw new Error('Failed to fetch archives.');
            }
            const data = await response.json();
            setArchives(data);
        } catch (err) {
            setArchivesError(err.message);
        } finally {
            setArchivesLoading(false);
        }
    };

    useEffect(() => {
        const unsubscribe = onAuthStateChanged(auth, async (currentUser) => {
            if (currentUser) {
                const idTokenResult = await currentUser.getIdTokenResult();
                currentUser.isAdmin = idTokenResult.claims.admin === true;
                setUser(currentUser);

                if (currentUser.emailVerified) {
                    setInfo('');
                    fetchArchives();
                }
            } else {
                setUser(null);
                setHistory([]);
                setArchives({});
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

    const handleSelectDocument = async (doc) => {
        try {
            const token = await auth.currentUser.getIdToken();
            const response = await fetch(`${API_URL}/document/${encodeURIComponent(doc.filename)}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!response.ok) {
                throw new Error('Failed to load document.');
            }
            const data = await response.json();
            const contextMessage = {
                role: 'context',
                content: data.content,
                display_text: `Loaded document: ${doc.filename}`
            };
            setHistory(prev => [...prev, contextMessage]);
            setSelectedDocument(doc.filename);
        } catch (err) {
            alert(err.message);
        }
    };

    const renderVerification = () => {
        return (
            <div className="auth-page">
                <div className="auth-container">
                    <h2>Please Verify Your Email</h2>
                    <p>You must verify your email address to continue. Please check your inbox for a verification link.</p>
                    <p>Logged in as: {user.email}</p>
                    <button onClick={handleResendVerification}>Resend Verification Email</button>
                    <button onClick={handleLogout}>Back to Login</button>
                    {error && <p className="error">{error}</p>}
                    {info && <p className="info-text">{info}</p>}
                </div>
            </div>
        );
    };

    const renderChatInterface = () => (
        <div className="App">
            <header className="App-header">
                <div className="logo-container">
                    <img src="/logo.png" alt="RomaLuma Logo" className="header-logo" />
                    <h1>RomaLuma</h1>
                </div>
                <div className="user-controls">
                    {user.displayName && <span>Welcome, {user.displayName}</span>}
                    {user.isAdmin && <Link to="/admin" className="account-button">Admin</Link>}
                    <Link to="/account" className="account-button">My Account</Link>
                    <button onClick={handleLogout}>Logout</button>
                </div>
            </header>

            <div className="main-content">
                <div className="left-panel">
                    <ArchivesPanel 
                        auth={auth}
                        archives={archives}
                        loading={archivesLoading}
                        error={archivesError}
                        onLoadArchive={handleLoadArchive}
                        onRefresh={fetchArchives}
                    />
                    <DocumentsPanel
                        onUploadSuccess={handleUploadSuccess}
                        onSelectDocument={handleSelectDocument}
                        selectedDocument={selectedDocument}
                        auth={auth}
                    />
                </div>
                <div className="chat-area">
                    <Chat 
                        auth={auth}
                        history={history} 
                        setHistory={setHistory} 
                        projectNames={Object.keys(archives)}
                        onSaveSuccess={fetchArchives}
                    />
                </div>
            </div>
        </div>
    );

    if (loading) {
        return <div>Loading...</div>; // Or a spinner component
    }

    if (user && !user.emailVerified) {
        return renderVerification();
    }

    return (
        <Routes>
            {/* Public-only routes */}
            <Route path="/" element={!user ? <HomePage /> : <Navigate to="/chat" />} />
            <Route path="/login" element={!user ? <AuthPage /> : <Navigate to="/chat" />} />
            <Route path="/register" element={!user ? <AuthPage /> : <Navigate to="/chat" />} />
            <Route path="/forgot-password" element={!user ? <AuthPage /> : <Navigate to="/chat" />} />

            {/* Protected routes */}
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
            <Route path="/admin" element={
                <ProtectedRoute user={user}>
                    <AdminPage auth={auth} />
                </ProtectedRoute>
            } />
        </Routes>
    );
}

export default App
