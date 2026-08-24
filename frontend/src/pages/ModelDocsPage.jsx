import React from 'react';
import { Link } from 'react-router-dom';

const ModelDocsPage = () => {
    const providers = [
        {
            name: 'Google Gemini',
            description: 'Multimodal AI models with strong reasoning and coding capabilities.',
            links: [
                { label: 'Models Overview', url: 'https://ai.google.dev/gemini-api/docs/models' },
                { label: 'Pricing', url: 'https://ai.google.dev/gemini-api/docs/pricing' }
            ],
            models: ['Gemini 3.7 Flash', 'Gemini 3.5 Flash-Lite', 'Gemini 3.1 Pro Preview']
        },
        {
            name: 'Anthropic Claude',
            description: 'Thoughtful AI assistants known for nuanced writing and careful reasoning.',
            links: [
                { label: 'Models Overview', url: 'https://platform.claude.com/docs/en/about-claude/models/overview' },
                { label: 'Pricing', url: 'https://platform.claude.com/docs/en/about-claude/pricing' }
            ],
            models: ['Claude Fable 5', 'Claude Opus 5', 'Claude Sonnet 5', 'Claude Haiku 4.5'],
        },
        {
            name: 'OpenAI GPT',
            description: 'Versatile language models with strong general-purpose capabilities.',
            links: [
                { label: 'Models Overview', url: 'https://developers.openai.com/api/docs/models' },
                { label: 'Latest Model Guide', url: 'https://developers.openai.com/api/docs/guides/latest-model' }
            ],
            models: ['GPT-5.6 Sol', 'GPT-5.6 Terra', 'GPT-5.6 Luna']
        },
        {
            name: 'Perplexity Sonar',
            description: 'Search-grounded AI for current information and source-backed research.',
            links: [
                { label: 'Models Overview', url: 'https://docs.perplexity.ai/docs/sonar/models' },
                { label: 'Pricing', url: 'https://docs.perplexity.ai/docs/getting-started/pricing' }
            ],
            models: ['Sonar Pro']
        }
    ];

    return (
        <div className="model-docs-page">
            <header className="model-docs-header">
                <Link to="/chat" className="back-link">&larr; Back to Chat</Link>
                <h1>AI Model Documentation</h1>
                <p>Learn more about the AI models available in RomaLume</p>
            </header>

            <div className="model-docs-content">
                <section className="auto-routing-info">
                    <h2>Smart Auto-Routing</h2>
                    <p>
                        When you select <strong>Auto (Smart Routing)</strong>, RomaLume automatically
                        analyzes your message and selects the best model for your task. Simple questions
                        use fast, economical models while complex coding or creative tasks use more
                        powerful models.
                    </p>
                </section>

                <div className="providers-grid">
                    {providers.map((provider, index) => (
                        <div key={index} className="provider-card">
                            <h2>{provider.name}</h2>
                            <p className="provider-description">{provider.description}</p>

                            <div className="provider-models">
                                <h4>Available Models:</h4>
                                <ul>
                                    {provider.models.map((model, i) => (
                                        <li key={i}>{model}</li>
                                    ))}
                                </ul>
                            </div>

                            <div className="provider-links">
                                <h4>Documentation:</h4>
                                {provider.links.map((link, i) => (
                                    <a
                                        key={i}
                                        href={link.url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="doc-link"
                                    >
                                        {link.label} &rarr;
                                    </a>
                                ))}
                            </div>
                        </div>
                    ))}
                </div>

                <section className="pricing-note">
                    <h2>Pricing</h2>
                    <p>
                        RomaLume uses a credit-based system. Different models consume credits at
                        different rates based on their capabilities. More powerful models use more
                        credits per message, while faster models are more economical.
                    </p>
                    <p>
                        Using <strong>Auto</strong> mode helps optimize your credit usage by selecting
                        the most appropriate model for each task.
                    </p>
                </section>
            </div>
        </div>
    );
};

export default ModelDocsPage;
