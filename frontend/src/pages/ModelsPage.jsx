import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { API_URL } from '../apiConfig';
import PublicNav from '../components/PublicNav';
import './HomePage.css';
import './ModelsPage.css';

const ModelsPage = () => {
    const [models, setModels] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [autoRoutingInfo, setAutoRoutingInfo] = useState('');
    const [selectedProvider, setSelectedProvider] = useState('all');

    useEffect(() => {
        fetchModels();
    }, []);

    const fetchModels = async () => {
        try {
            const response = await fetch(`${API_URL}/models`);
            if (!response.ok) throw new Error('Failed to fetch models');
            const data = await response.json();
            setModels(data.models);
            setAutoRoutingInfo(data.auto_routing_info);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const providers = ['all', ...new Set(models.map(m => m.provider))];
    const filteredModels = selectedProvider === 'all'
        ? models
        : models.filter(m => m.provider === selectedProvider);

    // Group models by provider
    const groupedModels = filteredModels.reduce((acc, model) => {
        const key = model.provider;
        if (!acc[key]) acc[key] = [];
        acc[key].push(model);
        return acc;
    }, {});

    const formatContext = (tokens) => {
        if (tokens >= 1000000) return `${(tokens / 1000000).toFixed(0)}M`;
        return `${(tokens / 1000).toFixed(0)}K`;
    };

    const badgeClass = (badge) => {
        const b = badge.toLowerCase();
        if (b === 'latest') return 'models-badge-latest';
        if (b === 'premium') return 'models-badge-premium';
        if (b === 'preview') return 'models-badge-preview';
        return 'models-badge-web';
    };

    if (loading) {
        return (
            <div className="models-page-wrapper">
                <PublicNav activePage="models" />
                <div className="models-page-content">
                    <div className="models-loading">Loading models...</div>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="models-page-wrapper">
                <PublicNav activePage="models" />
                <div className="models-page-content">
                    <div className="models-error">Unable to load models. Please try again later.</div>
                </div>
            </div>
        );
    }

    return (
        <div className="models-page-wrapper">
            <PublicNav activePage="models" />
            <div className="models-page-content">
                <div className="models-container">
                    <h1>AI Models</h1>
                    <p className="models-subtitle">
                        {models.length}+ models from leading providers — all included in your subscription
                    </p>

                    {autoRoutingInfo && (
                        <div className="models-auto-routing">
                            <h3>Smart Auto-Routing</h3>
                            <p>{autoRoutingInfo}</p>
                        </div>
                    )}

                    <div className="models-provider-filter">
                        {providers.map(provider => (
                            <button
                                key={provider}
                                className={`models-filter-btn ${selectedProvider === provider ? 'active' : ''}`}
                                onClick={() => setSelectedProvider(provider)}
                            >
                                {provider === 'all' ? 'All Providers' : provider}
                            </button>
                        ))}
                    </div>

                    {Object.entries(groupedModels).map(([provider, providerModels]) => (
                        <div key={provider} className="models-provider-group">
                            <h2 className="models-provider-title">{provider}</h2>
                            <div className="models-grid">
                                {providerModels.map(model => (
                                    <div key={model.id} className="models-card">
                                        <div className="models-card-header">
                                            <h3>{model.name}</h3>
                                            {model.badge && (
                                                <span className={`models-badge ${badgeClass(model.badge)}`}>
                                                    {model.badge}
                                                </span>
                                            )}
                                        </div>
                                        <p className="models-card-description">{model.description}</p>
                                        <div className="models-card-context">
                                            <span>{formatContext(model.context_window)} context window</span>
                                        </div>
                                        <div className="models-card-best-for">
                                            <span className="models-best-for-label">Best for</span>
                                            <div className="models-best-for-tags">
                                                {model.best_for.map((use, i) => (
                                                    <span key={i} className="models-use-tag">{use}</span>
                                                ))}
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    ))}

                    <div className="models-cta">
                        <h2>All models. One price.</h2>
                        <p>Every model included with your $10/month subscription.</p>
                        <Link to="/pricing" className="btn btn-primary">View Pricing</Link>
                        <Link to="/register" className="btn btn-secondary">Get Started</Link>
                    </div>
                </div>
            </div>

            <footer className="home-footer">
                <p>&copy; {new Date().getFullYear()} RomaLume. All rights reserved.</p>
            </footer>
        </div>
    );
};

export default ModelsPage;
