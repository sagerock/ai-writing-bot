import React from 'react';
import { Link } from 'react-router-dom';
import './HomePage.css';
import './AboutPage.css';

const AboutNav = () => (
    <nav className="home-nav nav-scrolled">
        <div className="nav-container">
            <Link to="/" className="nav-logo">
                <img src="/logo.png" alt="RomaLume" />
            </Link>
            <div className="nav-links">
                <Link to="/" className="nav-link">Home</Link>
                <Link to="/about" className="nav-link active">About</Link>
                <Link to="/pricing" className="nav-link">Pricing</Link>
                <Link to="/login" className="nav-link">Login</Link>
                <Link to="/register" className="nav-btn">Get Started</Link>
            </div>
        </div>
    </nav>
);

const AboutPage = () => {
    return (
        <div className="about-page-wrapper">
            <AboutNav />
            <div className="about-page">
                <div className="about-container">
                    <h1>About RomaLume</h1>
                    <p className="about-subtitle">
                        The right model for the right job
                    </p>

                    <section className="about-section highlight">
                        <h2>AI Won't Replace You</h2>
                        <p>
                            Let's get this out of the way: AI is not coming for your job. It's a tool — like
                            a calculator, a search engine, or a really fast research assistant. The people who
                            thrive will be the ones who learn to use it well.
                        </p>
                        <p>
                            RomaLume helps you do exactly that. It gives you access to the best AI models
                            available and helps you use the right one for what you're actually trying to do.
                            The result? You get better output, faster — and you stay in the driver's seat.
                        </p>
                    </section>

                    <section className="about-section">
                        <h2>Why Multiple Models Matter</h2>
                        <p>
                            There's no single AI that's the best at everything. Each model has strengths,
                            and picking the right one makes a real difference in the quality of what you get back.
                            That's why RomaLume gives you access to 17+ models — and can automatically route
                            your request to the one that fits best.
                        </p>
                    </section>

                    <section className="about-section">
                        <h2>What Each Model Does Best</h2>
                        <p>
                            <strong>OpenAI (GPT)</strong> — The most well-known name in AI. Strong across the board — writing,
                            coding, analysis, and general knowledge. Great when you need a fast, reliable answer
                            to just about anything.
                        </p>
                        <p>
                            <strong>Claude (Anthropic)</strong> — Thoughtful and thorough. Particularly strong at
                            long-form writing, nuanced creative work, detailed code generation, and following
                            complex instructions with care.
                        </p>
                        <p>
                            <strong>Gemini (Google)</strong> — Built for scale. Handles massive documents with ease,
                            integrates well with search and data tools, and shines at multi-step research tasks.
                        </p>
                        <p>
                            <strong>Command R+ (Cohere)</strong> — The document specialist. Optimized for
                            answering questions grounded in your uploaded files, with citations you
                            can trace back to the source.
                        </p>
                    </section>

                    <section className="about-section">
                        <h2>Better Results, Not More Complexity</h2>
                        <p>
                            You don't need to understand the technical differences between models.
                            RomaLume's auto-routing reads your request and picks the best model for you.
                            Or, if you prefer, you can choose a specific model yourself.
                        </p>
                        <p>
                            Either way, the goal is simple: help you get better results from AI
                            so you can be better at the things you already do.
                        </p>
                    </section>

                    <div className="about-cta">
                        <p>Ready to put AI to work for you?</p>
                        <Link to="/register" className="btn btn-primary btn-large">Get Started</Link>
                        <Link to="/pricing" className="btn btn-secondary">View Pricing</Link>
                    </div>
                </div>
            </div>

            <footer className="home-footer">
                <p>&copy; {new Date().getFullYear()} RomaLume. All rights reserved.</p>
            </footer>
        </div>
    );
};

export default AboutPage;
