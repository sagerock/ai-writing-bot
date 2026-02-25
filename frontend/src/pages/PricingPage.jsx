import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, Link, useSearchParams } from 'react-router-dom';
import { API_URL } from '../apiConfig';
import './HomePage.css';

const PRICE = 10;

const PricingNav = () => (
    <nav className="home-nav nav-scrolled">
        <div className="nav-container">
            <Link to="/" className="nav-logo">
                <img src="/logo.png" alt="RomaLume" />
            </Link>
            <div className="nav-links">
                <Link to="/" className="nav-link">Home</Link>
                <Link to="/about" className="nav-link">About</Link>
                <Link to="/pricing" className="nav-link active">Pricing</Link>
                <Link to="/login" className="nav-link">Login</Link>
                <Link to="/register" className="nav-btn">Get Started</Link>
            </div>
        </div>
    </nav>
);

const PricingPage = ({ auth }) => {
    const [searchParams] = useSearchParams();
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [subscription, setSubscription] = useState(null);
    const navigate = useNavigate();
    const autoCheckoutTriggered = useRef(false);

    useEffect(() => {
        checkSubscription();
    }, [auth]);

    // Auto-trigger checkout when returning from signup with subscribe param
    useEffect(() => {
        const subscribe = searchParams.get('subscribe');
        if (subscribe && auth.currentUser && !autoCheckoutTriggered.current && !loading) {
            autoCheckoutTriggered.current = true;
            setTimeout(() => {
                handleSubscribe();
            }, 500);
        }
    }, [searchParams, auth.currentUser]);

    const checkSubscription = async () => {
        try {
            const token = await auth.currentUser?.getIdToken();
            if (!token) return;

            const response = await fetch(`${API_URL}/user/subscription`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (response.ok) {
                const data = await response.json();
                setSubscription(data);
            }
        } catch (err) {
            console.error('Error checking subscription:', err);
        }
    };

    const handleSubscribe = async () => {
        if (!auth.currentUser) {
            navigate('/register?subscribe=true');
            return;
        }

        setLoading(true);
        setError(null);

        try {
            const token = await auth.currentUser.getIdToken();
            const response = await fetch(`${API_URL}/stripe/create-checkout`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    amount_cents: PRICE * 100,
                    success_url: `${window.location.origin}/subscribe/success`,
                    cancel_url: `${window.location.origin}/pricing`
                })
            });

            if (response.ok) {
                const data = await response.json();
                window.location.href = data.checkout_url;
            } else {
                const err = await response.json();
                setError(err.error || 'Failed to start checkout');
            }
        } catch (err) {
            setError('Failed to start checkout. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    const handleOpenPortal = async () => {
        setLoading(true);
        setError(null);
        try {
            const token = await auth.currentUser.getIdToken();
            const response = await fetch(`${API_URL}/stripe/create-portal`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });

            if (response.ok) {
                const data = await response.json();
                window.location.href = data.portal_url;
            } else {
                const err = await response.json();
                setError(err.error || 'Failed to open billing portal');
            }
        } catch (err) {
            setError('Failed to open billing portal. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="pricing-page-wrapper">
            <PricingNav />
            <div className="pricing-page">
                <div className="pricing-container">
                <h1>Simple Pricing</h1>
                <p className="pricing-subtitle">
                    One plan. Everything included.
                </p>

                {subscription?.status === 'active' ? (
                    <div className="subscriber-section">
                        <div className="thank-you-card">
                            <h2>You're Subscribed</h2>
                            <p className="current-plan">
                                <strong>${subscription.amount_cents / 100}/month</strong>
                            </p>
                        </div>

                        {error && <div className="error-message">{error}</div>}

                        <div className="manage-subscription-link">
                            <button onClick={handleOpenPortal} className="link-button" disabled={loading}>
                                Manage payment method or cancel subscription
                            </button>
                        </div>
                    </div>
                ) : (
                    <>
                        <div className="pricing-card">
                            <div className="price-hero">
                                <span className="price-amount">${PRICE}</span>
                                <span className="price-period">/month</span>
                            </div>

                            <div className="features-list">
                                <ul>
                                    <li>Access to <Link to="/models" className="inline-link">17+ AI models</Link> (GPT-4o, Claude, Gemini)</li>
                                    <li>Smart auto-routing picks the best model</li>
                                    <li>Document search across all your uploads</li>
                                    <li>AI remembers your preferences</li>
                                </ul>
                            </div>

                            {error && <div className="error-message">{error}</div>}

                            <button
                                onClick={handleSubscribe}
                                disabled={loading}
                                className="btn-subscribe"
                            >
                                {loading ? 'Processing...' : 'Subscribe'}
                            </button>

                            <p className="cancel-note">Cancel anytime. No questions asked.</p>
                        </div>
                    </>
                )}
                </div>
            </div>
        </div>
    );
};

export default PricingPage;
