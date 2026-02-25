import React, { useState, useEffect } from 'react';
import { API_URL } from '../apiConfig';

const BillingDashboard = ({ auth }) => {
    const [billingData, setBillingData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [portalLoading, setPortalLoading] = useState(false);

    useEffect(() => {
        fetchBillingData();
    }, [auth]);

    const fetchBillingData = async () => {
        try {
            const token = await auth.currentUser?.getIdToken();
            if (!token) return;

            const response = await fetch(`${API_URL}/user/billing`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (response.ok) {
                const data = await response.json();
                setBillingData(data);
            } else {
                setError('Failed to load billing data');
            }
        } catch (err) {
            console.error('Error fetching billing:', err);
            setError('Failed to load billing data');
        } finally {
            setLoading(false);
        }
    };

    const handleManageSubscription = async () => {
        setPortalLoading(true);
        try {
            const token = await auth.currentUser?.getIdToken();
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
                setError(err.error || 'Failed to open portal');
            }
        } catch (err) {
            setError('Failed to open subscription portal');
        } finally {
            setPortalLoading(false);
        }
    };

    if (loading) {
        return (
            <div className="billing-dashboard">
                <h3>Subscription</h3>
                <p className="loading-text">Loading billing data...</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="billing-dashboard">
                <h3>Subscription</h3>
                <p className="error-text">{error}</p>
                <button onClick={fetchBillingData}>Retry</button>
            </div>
        );
    }

    if (!billingData) {
        return null;
    }

    const { subscription, free_tier, current_month, all_time, usage_warning } = billingData;

    return (
        <div className="billing-dashboard">
            <h3>Subscription</h3>

            {/* Subscription Status */}
            {subscription.status === 'none' ? (
                <div className="free-tier-section">
                    {/* Free Messages Display */}
                    <div className="free-messages-display">
                        <div className="free-messages-count">
                            <span className="count-number">{free_tier?.messages_remaining ?? 100}</span>
                            <span className="count-label">free messages remaining</span>
                        </div>
                        <div className="free-messages-bar">
                            <div
                                className="free-messages-progress"
                                style={{ width: `${((free_tier?.messages_remaining ?? 100) / 100) * 100}%` }}
                            />
                        </div>
                        <p className="free-messages-note">
                            {free_tier?.messages_used || 0} of 100 free messages used
                        </p>
                    </div>

                    {/* Subscribe CTA */}
                    <div className="subscription-cta">
                        <h4>Love RomaLume?</h4>
                        <p>Subscribe for unlimited access to 17+ AI models for $10/month.</p>
                        <a href="/pricing" className="btn-primary">Subscribe for $10/month</a>
                    </div>
                </div>
            ) : (
                <>
                    {/* Current Month Usage */}
                    <div className="billing-section">
                        <h4>This Month ({current_month.month})</h4>

                        {/* Progress bar */}
                        <div className="usage-progress">
                            <div
                                className={`usage-bar ${usage_warning ? 'warning' : ''}`}
                                style={{ width: `${Math.min(current_month.usage_percent, 100)}%` }}
                            />
                        </div>
                        <p className="usage-percent">{current_month.usage_percent}% of {subscription.amount_display} used</p>

                        <div className="cost-breakdown">
                            <div className="cost-item ai-cost">
                                <span className="cost-label">AI Usage</span>
                                <span className="cost-value">{current_month.ai_cost_display}</span>
                            </div>
                        </div>

                        {usage_warning && (
                            <div className="usage-warning">
                                <p>Your AI usage is approaching your subscription amount.</p>
                            </div>
                        )}
                    </div>

                    {/* All-Time Stats */}
                    <div className="billing-section all-time">
                        <h4>All-Time Usage</h4>
                        <div className="impact-stats">
                            <div className="impact-stat">
                                <span className="stat-value">{all_time.ai_cost_display}</span>
                                <span className="stat-label">Total AI Usage</span>
                            </div>
                            <div className="impact-stat">
                                <span className="stat-value">{all_time.requests.toLocaleString()}</span>
                                <span className="stat-label">AI Requests</span>
                            </div>
                        </div>
                    </div>

                    {/* Manage Subscription */}
                    <div className="billing-actions">
                        <button
                            onClick={handleManageSubscription}
                            disabled={portalLoading}
                            className="btn-secondary"
                        >
                            {portalLoading ? 'Loading...' : 'Manage Subscription'}
                        </button>
                    </div>
                </>
            )}
        </div>
    );
};

export default BillingDashboard;
