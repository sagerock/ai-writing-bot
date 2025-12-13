import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { API_URL } from '../apiConfig';

const ModelsPage = () => {
    const [models, setModels] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [pricingNote, setPricingNote] = useState('');
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
            setPricingNote(data.pricing_note);
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

    // Group models by category
    const groupedModels = filteredModels.reduce((acc, model) => {
        const key = model.category;
        if (!acc[key]) acc[key] = [];
        acc[key].push(model);
        return acc;
    }, {});

    const formatPrice = (price) => {
        if (price < 0.10) return `$${price.toFixed(3)}`;
        if (price < 1) return `$${price.toFixed(2)}`;
        return `$${price.toFixed(2)}`;
    };

    const formatContext = (tokens) => {
        if (tokens >= 1000000) return `${(tokens / 1000000).toFixed(0)}M`;
        return `${(tokens / 1000).toFixed(0)}K`;
    };

    if (loading) {
        return (
            <div className="models-page">
                <div className="models-container">
                    <div className="loading-spinner">Loading models...</div>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="models-page">
                <div className="models-container">
                    <div className="error-message">Error: {error}</div>
                </div>
            </div>
        );
    }

    return (
        <div className="models-page">
            <nav className="models-nav">
                <Link to="/">&larr; Back to Home</Link>
            </nav>

            <div className="models-container">
                <header className="models-header">
                    <h1>AI Models & Pricing</h1>
                    <p className="models-subtitle">
                        Access to {models.length}+ AI models from leading providers
                    </p>
                </header>

                <div className="auto-routing-banner">
                    <h3>Smart Auto-Routing</h3>
                    <p>{autoRoutingInfo}</p>
                </div>

                <div className="provider-filter">
                    {providers.map(provider => (
                        <button
                            key={provider}
                            className={`filter-btn ${selectedProvider === provider ? 'active' : ''}`}
                            onClick={() => setSelectedProvider(provider)}
                        >
                            {provider === 'all' ? 'All Providers' : provider}
                        </button>
                    ))}
                </div>

                {Object.entries(groupedModels).map(([category, categoryModels]) => (
                    <div key={category} className="models-category">
                        <h2 className="category-title">{category}</h2>
                        <div className="models-grid">
                            {categoryModels.map(model => (
                                <div key={model.id} className="model-card">
                                    <div className="model-card-header">
                                        <h3>{model.name}</h3>
                                        {model.badge && (
                                            <span className={`model-badge badge-${model.badge.toLowerCase()}`}>
                                                {model.badge}
                                            </span>
                                        )}
                                    </div>
                                    <p className="model-provider">{model.provider}</p>
                                    <p className="model-description">{model.description}</p>

                                    <div className="model-pricing">
                                        <div className="price-row">
                                            <span className="price-label">Input</span>
                                            <span className="price-value">{formatPrice(model.input_price)}/M tokens</span>
                                        </div>
                                        <div className="price-row">
                                            <span className="price-label">Output</span>
                                            <span className="price-value">{formatPrice(model.output_price)}/M tokens</span>
                                        </div>
                                    </div>

                                    <div className="model-context">
                                        <span className="context-icon">📄</span>
                                        <span>{formatContext(model.context_window)} context</span>
                                    </div>

                                    <div className="model-best-for">
                                        <span className="best-for-label">Best for:</span>
                                        <div className="best-for-tags">
                                            {model.best_for.map((use, i) => (
                                                <span key={i} className="use-tag">{use}</span>
                                            ))}
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                ))}

                <div className="pricing-notes">
                    <h3>Pricing Notes</h3>
                    <ul>
                        <li>{pricingNote}</li>
                        <li>Your subscription covers all model usage - no per-message charges.</li>
                        <li>We track costs transparently so you can see exactly what's being spent on AI.</li>
                    </ul>
                </div>

                <div className="cta-section">
                    <h2>Ready to Get Started?</h2>
                    <p>Subscribe to get unlimited access to all models.</p>
                    <Link to="/pricing" className="btn-primary">View Subscription Plans</Link>
                </div>
            </div>
        </div>
    );
};

export default ModelsPage;
