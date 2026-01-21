import { useState, useEffect } from 'react';
import { useSearchParams, useNavigate, Link } from 'react-router-dom';
import { getAuth, verifyPasswordResetCode, confirmPasswordReset, applyActionCode } from 'firebase/auth';
import './HomePage.css';

function AuthActionPage() {
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    const auth = getAuth();

    const mode = searchParams.get('mode');
    const oobCode = searchParams.get('oobCode');

    const [status, setStatus] = useState('loading'); // loading, input, success, error
    const [email, setEmail] = useState('');
    const [newPassword, setNewPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [error, setError] = useState('');
    const [isLoading, setIsLoading] = useState(false);

    useEffect(() => {
        if (!mode || !oobCode) {
            setStatus('error');
            setError('Invalid action link. Please request a new one.');
            return;
        }

        if (mode === 'resetPassword') {
            // Verify the password reset code is valid
            verifyPasswordResetCode(auth, oobCode)
                .then((email) => {
                    setEmail(email);
                    setStatus('input');
                })
                .catch((err) => {
                    setStatus('error');
                    setError('This password reset link has expired or already been used. Please request a new one.');
                });
        } else if (mode === 'verifyEmail') {
            // Handle email verification
            applyActionCode(auth, oobCode)
                .then(() => {
                    setStatus('success');
                })
                .catch((err) => {
                    setStatus('error');
                    setError('This verification link has expired or already been used.');
                });
        } else {
            setStatus('error');
            setError('Unknown action type.');
        }
    }, [mode, oobCode, auth]);

    const handlePasswordReset = async (e) => {
        e.preventDefault();
        setError('');

        if (newPassword.length < 6) {
            setError('Password must be at least 6 characters.');
            return;
        }

        if (newPassword !== confirmPassword) {
            setError('Passwords do not match.');
            return;
        }

        setIsLoading(true);
        try {
            await confirmPasswordReset(auth, oobCode, newPassword);
            setStatus('success');
        } catch (err) {
            setError('Failed to reset password. The link may have expired. Please request a new one.');
        } finally {
            setIsLoading(false);
        }
    };

    const renderContent = () => {
        if (status === 'loading') {
            return (
                <div className="auth-container">
                    <div className="auth-card">
                        <div className="spinner"></div>
                        <p>Verifying...</p>
                    </div>
                </div>
            );
        }

        if (status === 'error') {
            return (
                <div className="auth-container">
                    <div className="auth-card">
                        <h2>Something went wrong</h2>
                        <p className="error-message">{error}</p>
                        <Link to="/forgot-password" className="auth-button" style={{ display: 'inline-block', textAlign: 'center', textDecoration: 'none', marginTop: '1rem' }}>
                            Request New Link
                        </Link>
                    </div>
                </div>
            );
        }

        if (mode === 'verifyEmail' && status === 'success') {
            return (
                <div className="auth-container">
                    <div className="auth-card">
                        <h2>Email Verified!</h2>
                        <p>Your email has been successfully verified.</p>
                        <Link to="/login" className="auth-button" style={{ display: 'inline-block', textAlign: 'center', textDecoration: 'none', marginTop: '1rem' }}>
                            Go to Login
                        </Link>
                    </div>
                </div>
            );
        }

        if (mode === 'resetPassword' && status === 'input') {
            return (
                <div className="auth-container">
                    <div className="auth-card">
                        <h2>Reset Password</h2>
                        <p>Enter a new password for <strong>{email}</strong></p>
                        {error && <p className="error-message">{error}</p>}
                        <form onSubmit={handlePasswordReset}>
                            <input
                                type="password"
                                placeholder="New password"
                                value={newPassword}
                                onChange={(e) => setNewPassword(e.target.value)}
                                required
                                minLength={6}
                            />
                            <input
                                type="password"
                                placeholder="Confirm new password"
                                value={confirmPassword}
                                onChange={(e) => setConfirmPassword(e.target.value)}
                                required
                                minLength={6}
                            />
                            <button type="submit" className="auth-button" disabled={isLoading}>
                                {isLoading ? <span className="spinner small"></span> : 'Reset Password'}
                            </button>
                        </form>
                    </div>
                </div>
            );
        }

        if (mode === 'resetPassword' && status === 'success') {
            return (
                <div className="auth-container">
                    <div className="auth-card">
                        <h2>Password Changed!</h2>
                        <p>Your password has been successfully reset.</p>
                        <Link to="/login" className="auth-button" style={{ display: 'inline-block', textAlign: 'center', textDecoration: 'none', marginTop: '1rem' }}>
                            Sign In
                        </Link>
                    </div>
                </div>
            );
        }

        return null;
    };

    return (
        <div className="auth-page">
            <header className="auth-header">
                <Link to="/">
                    <img src="/logo.png" alt="RomaLume" className="auth-logo" />
                </Link>
            </header>
            {renderContent()}
        </div>
    );
}

export default AuthActionPage;
