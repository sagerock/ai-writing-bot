import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { API_URL } from '../apiConfig';

const PricingPage = ({ auth }) => {
    const [amount, setAmount] = useState(20);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [subscription, setSubscription] = useState(null);
    const navigate = useNavigate();

    useEffect(() => {
        checkSubscription();
    }, [auth]);

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
            navigate('/login');
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
                    amount_cents: amount * 100,
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

    // Estimate based on average usage
    const estimatedAiCost = Math.min(amount * 0.4, 15); // ~40% to AI on average, max $15
    const estimatedCharity = amount - estimatedAiCost;

    return (
        <div className="pricing-page">
            <div className="pricing-container">
                <h1>Simple, Transparent Pricing</h1>
                <p className="pricing-subtitle">
                    100% of profits go to <strong>Houseless Movement</strong>
                </p>

                {subscription?.status === 'active' ? (
                    <div className="already-subscribed">
                        <h2>You're Already Subscribed!</h2>
                        <p>Current plan: {subscription.amount_cents / 100}/month</p>
                        <button onClick={() => navigate('/account')} className="btn-primary">
                            Manage Subscription
                        </button>
                    </div>
                ) : (
                    <>
                        <div className="pricing-card">
                            <div className="amount-selector">
                                <label>Choose Your Monthly Contribution</label>
                                <div className="slider-container">
                                    <input
                                        type="range"
                                        min="20"
                                        max="100"
                                        step="5"
                                        value={amount}
                                        onChange={(e) => setAmount(parseInt(e.target.value))}
                                        className="amount-slider"
                                    />
                                    <div className="amount-display">${amount}/month</div>
                                </div>
                                <div className="amount-labels">
                                    <span>$20</span>
                                    <span>$100</span>
                                </div>
                            </div>

                            <div className="pricing-breakdown">
                                <h3>Where Your Money Goes</h3>
                                <div className="breakdown-bar">
                                    <div
                                        className="bar-ai"
                                        style={{ width: `${(estimatedAiCost / amount) * 100}%` }}
                                    >
                                        AI Costs
                                    </div>
                                    <div
                                        className="bar-charity"
                                        style={{ width: `${(estimatedCharity / amount) * 100}%` }}
                                    >
                                        Charity
                                    </div>
                                </div>
                                <div className="breakdown-details">
                                    <div className="detail-item">
                                        <span className="detail-label">Estimated AI Costs</span>
                                        <span className="detail-value">~${estimatedAiCost.toFixed(0)}</span>
                                    </div>
                                    <div className="detail-item highlight">
                                        <span className="detail-label">To Houseless Movement</span>
                                        <span className="detail-value">~${estimatedCharity.toFixed(0)}</span>
                                    </div>
                                </div>
                                <p className="breakdown-note">
                                    * Actual split depends on your usage. Light users = more to charity!
                                </p>
                            </div>

                            <div className="features-list">
                                <h3>What You Get</h3>
                                <ul>
                                    <li>Access to <Link to="/models" className="inline-link">17+ AI models</Link> (GPT-5, Claude, Gemini)</li>
                                    <li>Smart auto-routing picks the best model</li>
                                    <li>Document search across all your uploads</li>
                                    <li>AI remembers your preferences</li>
                                    <li>Transparent cost breakdown</li>
                                </ul>
                            </div>

                            {error && <div className="error-message">{error}</div>}

                            <button
                                onClick={handleSubscribe}
                                disabled={loading}
                                className="btn-subscribe"
                            >
                                {loading ? 'Processing...' : `Subscribe for $${amount}/month`}
                            </button>

                            <p className="cancel-note">Cancel anytime. No questions asked.</p>

                            <div className="tax-info">
                                <p className="tax-note">
                                    <strong>Note:</strong> Your subscription is not tax-deductible.
                                </p>
                                <details className="tax-explanation">
                                    <summary>Why not?</summary>
                                    <p>
                                        IRS rules require that charitable donations be gifts with no expectation
                                        of receiving something in return. Since your subscription gives you access
                                        to our AI service, it's considered a purchase rather than a donation—even
                                        though we donate the profits to charity.
                                    </p>
                                    <p>
                                        Think of it like buying cookies from a school fundraiser: you're supporting
                                        a good cause, but you're also getting cookies, so it's not tax-deductible.
                                    </p>
                                    <p>
                                        <strong>Your impact is still 100% real!</strong> The money still goes to
                                        help homeless individuals in Akron—it just can't be written off on your taxes.
                                    </p>
                                </details>
                            </div>
                        </div>

                        <div className="charity-section">
                            <h2>About Houseless Movement</h2>
                            <p>
                                Houseless Movement is a 501(c)(3) charity helping homeless individuals
                                in Akron, Ohio find shelter, support, and dignity.
                            </p>
                            <p>
                                Every subscription directly funds housing, supplies,
                                and advocacy for those who need it most.
                            </p>
                            <a
                                href="https://houselessmovement.org"
                                target="_blank"
                                rel="noopener noreferrer"
                                className="learn-more-link"
                            >
                                Learn More About Our Impact
                            </a>
                        </div>
                    </>
                )}
            </div>
        </div>
    );
};

export default PricingPage;
