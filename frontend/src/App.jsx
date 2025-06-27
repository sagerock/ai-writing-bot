import { useState, useEffect } from 'react'
import { Routes, Route, Link, useNavigate } from 'react-router-dom'
import { initializeApp } from 'firebase/app'
import { getAuth, onAuthStateChanged, createUserWithEmailAndPassword, signInWithEmailAndPassword, signOut, sendEmailVerification, sendPasswordResetEmail } from 'firebase/auth'
import Chat from './components/Chat'
import ArchivesPanel from './components/ArchivesPanel'
import DocumentsPanel from './components/DocumentsPanel'
import AccountPage from './components/AccountPage'
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

function App() {
    const [user, setUser] = useState(null);
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [info, setInfo] = useState('');
    const [history, setHistory] = useState([]);
    const [archives, setArchives] = useState({});
    const [archivesLoading, setArchivesLoading] = useState(false);
    const [archivesError, setArchivesError] = useState('');
    const [selectedDocument, setSelectedDocument] = useState(null);
    const [showAccountPanel, setShowAccountPanel] = useState(false);
    const [authView, setAuthView] = useState('login'); // 'login', 'forgotPassword'
    const navigate = useNavigate();

    const fetchArchives = async () => {
        if (!auth.currentUser) return;
        setArchivesLoading(true);
        setArchivesError('');
        try {
            const token = await auth.currentUser.getIdToken();
            const response = await fetch('http://127.0.0.1:8000/archives', {
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
        const unsubscribe = onAuthStateChanged(auth, (currentUser) => {
            if (currentUser && !currentUser.emailVerified) {
                setUser(currentUser);
            } else if (currentUser) {
                setUser(currentUser);
                setInfo('');
                fetchArchives();
            } else {
                setUser(null);
                setHistory([]);
                setArchives({});
            }
        });
        return () => unsubscribe();
    }, []);

    const handleRegister = async (e) => {
        e.preventDefault();
        setError('');
        setInfo('');
        try {
            const userCredential = await createUserWithEmailAndPassword(auth, email, password);
            await sendEmailVerification(userCredential.user);
            await signOut(auth); // Sign out to force login after verification
            setAuthView('login');
            setInfo('Verification email sent! Please check your inbox and click the link to activate your account.');
        } catch (err) {
            setError(err.message);
        }
    };

    const handleLogin = async (e) => {
        e.preventDefault();
        setError('');
        setInfo('');
        try {
            await signInWithEmailAndPassword(auth, email, password);
        } catch (err) {
            setError('Failed to log in. Please check your credentials.');
        }
    };

    const handleForgotPassword = async (e) => {
        e.preventDefault();
        setError('');
        setInfo('');
        if (!email) {
            setError('Please enter your email address.');
            return;
        }
        try {
            await sendPasswordResetEmail(auth, email);
            setInfo('Password reset email sent. Please check your inbox.');
            setAuthView('login'); // Switch back to login view
        } catch (err) {
            setError('Failed to send password reset email. Please check the email address.');
            console.error(err);
        }
    };

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
            navigate('/'); // Navigate to login/home after logout
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
            const response = await fetch(`http://127.0.0.1:8000/archive/${archiveId}`, {
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
            const response = await fetch(`http://127.0.0.1:8000/document/${encodeURIComponent(doc.filename)}`, {
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

    const renderAuth = () => {
        return (
            <div className="auth-container">
                <h2>Login or Register</h2>
                <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="Email"
                />
                <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Password"
                />
                <button onClick={handleLogin}>Login</button>
                <button onClick={handleRegister}>Register</button>
                {error && <p className="error">{error}</p>}
                {info && <p className="success">{info}</p>}
                <a href="#" className="forgot-password-link" onClick={() => setAuthView('forgotPassword')}>Forgot Password?</a>
            </div>
        );
    };

    const renderForgotPassword = () => {
        return (
            <div className="auth-container">
                <h2>Reset Password</h2>
                <p>Enter your email address to receive a password reset link.</p>
                <form onSubmit={handleForgotPassword}>
                    <input
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="Email"
                        autoFocus
                    />
                    <button type="submit">Send Reset Link</button>
                </form>
                {error && <p className="error">{error}</p>}
                {info && <p className="success">{info}</p>}
                <a href="#" className="forgot-password-link" onClick={() => setAuthView('login')}>Back to Login</a>
            </div>
        );
    }

    const renderVerification = () => {
        return (
            <div className="auth-container">
                <h2>Please Verify Your Email</h2>
                <p>You must verify your email address to continue. Please check your inbox for a verification link.</p>
                <p>Logged in as: {user.email}</p>
                <button onClick={handleResendVerification}>Resend Verification Email</button>
                <button onClick={handleLogout}>Back to Login</button>
                {error && <p className="error">{error}</p>}
                {info && <p className="info-text">{info}</p>}
            </div>
        );
    };

    const renderChatInterface = () => (
        <div className="App">
            <header className="App-header">
                <h1>Multi-bot Chat</h1>
                <div className="user-controls">
                    {user.displayName && <span>Welcome, {user.displayName}</span>}
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

    if (!user) {
        if (authView === 'forgotPassword') {
            return renderForgotPassword();
        }
        return renderAuth();
    }

    if (!user.emailVerified) {
        return renderVerification();
    }

    return (
        <Routes>
            <Route path="/" element={renderChatInterface()} />
            <Route path="/account" element={<AccountPage auth={auth} />} />
        </Routes>
    );
}

export default App
