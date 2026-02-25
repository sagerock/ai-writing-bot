import React, { useState } from 'react';
import { useLocation, Link, useNavigate, useSearchParams } from 'react-router-dom';
import { getAuth, createUserWithEmailAndPassword, signInWithEmailAndPassword, sendPasswordResetEmail } from 'firebase/auth';
import { API_URL } from '../apiConfig';
import PublicNav from '../components/PublicNav';
import './HomePage.css';

// This component will handle Login, Registration, and Forgot Password
const AuthPage = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [info, setInfo] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const auth = getAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const subscribeAmount = searchParams.get('subscribe');

  // Determine which form to show based on the URL path
  const isRegister = location.pathname === '/register';
  const isForgotPassword = location.pathname === '/forgot-password';

  const handleRegister = async (e) => {
    e.preventDefault();
    setError('');
    setInfo('');
    setIsLoading(true);

    try {
      // Check rate limit before attempting signup
      const rateLimitResponse = await fetch(`${API_URL}/signup/check-rate-limit`);
      const rateLimitData = await rateLimitResponse.json();

      if (!rateLimitData.allowed) {
        setError(rateLimitData.reason);
        setIsLoading(false);
        return;
      }

      // Proceed with signup
      const userCredential = await createUserWithEmailAndPassword(auth, email, password);

      // Record successful signup for rate limiting and send to email marketing
      await fetch(`${API_URL}/signup/record`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email })
      });

      // If user came from pricing page, redirect back to complete subscription
      if (subscribeAmount) {
        navigate(`/pricing?amount=${subscribeAmount}`);
      }
      // Otherwise, the onAuthStateChanged listener in App.jsx will handle navigation to /chat
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    setInfo('');
    setIsLoading(true);
    try {
      await signInWithEmailAndPassword(auth, email, password);
      // If user came from pricing page, redirect back to complete subscription
      if (subscribeAmount) {
        navigate(`/pricing?amount=${subscribeAmount}`);
      }
      // Otherwise, the onAuthStateChanged listener in App.jsx will handle navigation
    } catch (err) {
      setError('Failed to log in. Please check your credentials.');
    } finally {
      setIsLoading(false);
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
    setIsLoading(true);
    try {
      await sendPasswordResetEmail(auth, email);
      navigate('/login', { state: { info: 'Password reset email sent. Please check your inbox.' } });
    } catch (err) {
      setError('Failed to send password reset email. Please check the email address.');
    } finally {
      setIsLoading(false);
    }
  };

  // Use the 'info' message passed in state from navigation, if any
  React.useEffect(() => {
    if (location.state?.info) {
        setInfo(location.state.info);
    }
  }, [location.state]);

  const renderForm = () => {
    if (isForgotPassword) {
      return (
        <form onSubmit={handleForgotPassword}>
          <h2>Reset Password</h2>
          <p>Enter your email address to receive a password reset link.</p>
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" required autoFocus />
          <button type="submit" disabled={isLoading}>
            {isLoading ? <span className="spinner small"></span> : 'Send Reset Link'}
          </button>
          <div className="auth-links">
            <Link to="/login">Back to Login</Link>
          </div>
        </form>
      );
    }

    if (isRegister) {
      return (
        <form onSubmit={handleRegister}>
          <h2>Create an Account</h2>
          {subscribeAmount && (
            <p className="subscribe-context">
              Sign up to complete your ${subscribeAmount}/month subscription
            </p>
          )}
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" required />
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Password" required />
          <button type="submit" disabled={isLoading}>
            {isLoading ? <span className="spinner small"></span> : (subscribeAmount ? 'Continue to Checkout' : 'Register')}
          </button>
          <div className="auth-links">
            <span>Already have an account? </span>
            <Link to={subscribeAmount ? `/login?subscribe=${subscribeAmount}` : '/login'}>Login</Link>
          </div>
        </form>
      );
    }

    return (
      <form onSubmit={handleLogin}>
        <h2>Login</h2>
        {subscribeAmount && (
          <p className="subscribe-context">
            Log in to complete your ${subscribeAmount}/month subscription
          </p>
        )}
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" required />
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Password" required />
        <button type="submit" disabled={isLoading}>
          {isLoading ? <span className="spinner small"></span> : (subscribeAmount ? 'Continue to Checkout' : 'Login')}
        </button>
        <div className="auth-links">
          <div>No account? <Link to={subscribeAmount ? `/register?subscribe=${subscribeAmount}` : '/register'}>Create one</Link></div>
          <div><Link to="/forgot-password">Forgot Password?</Link></div>
        </div>
      </form>
    );
  };

  return (
    <div className="auth-page-wrapper">
      <PublicNav activePage="auth" />
      <div className="auth-page">
        <div className="auth-container">
          <img src="/logo.png" alt="RomaLume Logo" className="auth-logo" />
          {renderForm()}
          {error && <p className="error">{error}</p>}
          {info && <p className="success">{info}</p>}
        </div>
      </div>
    </div>
  );
};

export default AuthPage;
