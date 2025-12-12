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
                <h3>Your Impact</h3>
                <p className="loading-text">Loading billing data...</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="billing-dashboard">
                <h3>Your Impact</h3>
                <p className="error-text">{error}</p>
                <button onClick={fetchBillingData}>Retry</button>
            </div>
        );
    }

    if (!billingData) {
        return null;
    }

    const { subscription, current_month, all_time, usage_warning } = billingData;

    return (
        <div className="billing-dashboard">
            <h3>Your Impact</h3>

            {/* Subscription Status */}
            {subscription.status === 'none' ? (
                <div className="subscription-cta">
                    <p>Subscribe to support Houseless Movement while using AI</p>
                    <a href="/pricing" className="btn-primary">View Plans</a>
                </div>
            ) : (
                <>
                    {/* Current Month Breakdown */}
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
                                <span className="cost-label">AI Provider Costs</span>
                                <span className="cost-value">{current_month.ai_cost_display}</span>
                            </div>
                            <div className="cost-item charity-cost">
                                <span className="cost-label">To Houseless Movement</span>
                                <span className="cost-value highlight">{current_month.charity_display}</span>
                            </div>
                        </div>

                        {usage_warning && (
                            <div className="usage-warning">
                                <p>Your AI usage is approaching your subscription amount.</p>
                                <p>Consider increasing your contribution to help more!</p>
                            </div>
                        )}
                    </div>

                    {/* All-Time Impact */}
                    <div className="billing-section all-time">
                        <h4>Your All-Time Impact</h4>
                        <div className="impact-stats">
                            <div className="impact-stat">
                                <span className="stat-value">{all_time.ai_cost_display}</span>
                                <span className="stat-label">Total AI Costs</span>
                            </div>
                            <div className="impact-stat highlight">
                                <span className="stat-value">{all_time.charity_display}</span>
                                <span className="stat-label">Donated to Charity</span>
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

            {/* About the Charity */}
            <div className="charity-info">
                <h4>About Houseless Movement</h4>
                <p>
                    100% of subscription profits go to Houseless Movement,
                    helping homeless individuals in Akron, Ohio find shelter and support.
                </p>
                <a href="https://houselessmovement.org" target="_blank" rel="noopener noreferrer">
                    Learn More
                </a>
            </div>
        </div>
    );
};

export default BillingDashboard;
