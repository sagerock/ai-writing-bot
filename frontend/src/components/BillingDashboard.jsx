import React, { useState, useEffect, useCallback } from 'react';
import { API_URL } from '../apiConfig';

const BillingDashboard = ({ auth }) => {
    const [billingData, setBillingData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [portalLoading, setPortalLoading] = useState(false);

    const fetchBillingData = useCallback(async () => {
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
    }, [auth]);

    useEffect(() => {
        fetchBillingData();
    }, [fetchBillingData]);

    const handleManageSubscription = async () => {
        setPortalLoading(true);
        try {
            const token = await auth.currentUser?.getIdToken();
            const response = await fetch(`${API_URL}/stripe/create-portal`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    return_url: `${window.location.origin}/account`
                })
            });

            if (response.ok) {
                const data = await response.json();
                window.location.href = data.portal_url;
            } else {
                const err = await response.json();
                setError(err.error || 'Failed to open portal');
            }
        } catch {
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

    const { subscription } = billingData;

    return (
        <div className="billing-dashboard">
            <h3>Subscription</h3>

            {/* Subscription Status */}
            {subscription.status === 'none' ? (
                <div className="subscription-cta">
                    <p>Subscribe for unlimited access to 17+ AI models.</p>
                    <a href="/pricing" className="btn-primary">Subscribe for $20/month</a>
                </div>
            ) : (
                <div className="billing-actions">
                    <p className="subscription-status">Active — {subscription.amount_display}/month</p>
                    <button
                        onClick={handleManageSubscription}
                        disabled={portalLoading}
                        className="btn-secondary"
                    >
                        {portalLoading ? 'Loading...' : 'Manage Subscription'}
                    </button>
                </div>
            )}
        </div>
    );
};

export default BillingDashboard;
