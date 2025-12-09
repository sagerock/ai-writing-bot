import React from 'react';
import { Link } from 'react-router-dom';
import './HomePage.css';

const HomePage = () => {
  return (
    <div className="home-page">
      <header className="home-header">
        <img src="/logo.png" alt="RomaLume Logo" className="home-logo" />
        <h1>Write Better. Faster.</h1>
        <p className="tagline">One tool. Multiple AI models. Unlimited possibilities.</p>
        <p className="sub-tagline">Access GPT-5, Claude, Gemini, and more — all in one place.</p>
        <div className="cta-buttons">
          <Link to="/register" className="btn btn-primary btn-large">Start Free — 100 Credits</Link>
          <Link to="/login" className="btn btn-secondary">Login</Link>
        </div>
        <p className="no-card">No credit card required</p>
      </header>

      {/* Use Cases Section */}
      <section className="use-cases-section">
        <h2>Built for Professionals Who Write</h2>
        <div className="use-cases-grid">
          <div className="use-case-card">
            <span className="use-case-icon">📣</span>
            <h3>Marketing</h3>
            <p>Draft compelling ad copy, email campaigns, social posts, and landing page content that converts.</p>
          </div>
          <div className="use-case-card">
            <span className="use-case-icon">💼</span>
            <h3>Business</h3>
            <p>Create polished proposals, executive summaries, reports, and client communications.</p>
          </div>
          <div className="use-case-card">
            <span className="use-case-icon">✍️</span>
            <h3>Content Creation</h3>
            <p>Write blog posts, articles, newsletters, and thought leadership pieces with ease.</p>
          </div>
          <div className="use-case-card">
            <span className="use-case-icon">📚</span>
            <h3>Research & Learning</h3>
            <p>Summarize documents, research topics, prepare for meetings, and accelerate your learning.</p>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <main className="features-section">
        <h2>Why RomaLume?</h2>
        <div className="features-grid">
          <div className="feature-card">
            <h3>Multiple AI Models</h3>
            <p>Switch between GPT-5, Claude, Gemini, and Perplexity to find the perfect voice for your task. Each model has unique strengths.</p>
          </div>
          <div className="feature-card">
            <h3>Real-Time Web Search</h3>
            <p>Get current information, not outdated training data. Our web search integration brings live results into your conversations.</p>
          </div>
          <div className="feature-card">
            <h3>Document Context</h3>
            <p>Upload PDFs, text files, and markdown documents. Ask questions about your content or use it as context for writing.</p>
          </div>
          <div className="feature-card">
            <h3>Save & Organize</h3>
            <p>Archive your best conversations by project. Return to them anytime to continue where you left off.</p>
          </div>
        </div>
      </main>

      {/* Powered By Section */}
      <section className="powered-by-section">
        <h2>Powered By Leading AI</h2>
        <div className="ai-logos">
          <div className="ai-logo-item">
            <span className="ai-name">OpenAI</span>
            <span className="ai-model">GPT-5</span>
          </div>
          <div className="ai-logo-item">
            <span className="ai-name">Anthropic</span>
            <span className="ai-model">Claude</span>
          </div>
          <div className="ai-logo-item">
            <span className="ai-name">Google</span>
            <span className="ai-model">Gemini</span>
          </div>
          <div className="ai-logo-item">
            <span className="ai-name">Perplexity</span>
            <span className="ai-model">Sonar</span>
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="final-cta-section">
        <h2>Ready to Write Better?</h2>
        <p>Get started with 100 free credits. No credit card required.</p>
        <Link to="/register" className="btn btn-primary btn-large">Get Started Free</Link>
      </section>

      <footer className="home-footer">
        <p>© {new Date().getFullYear()} RomaLume. All rights reserved.</p>
      </footer>
    </div>
  );
};

export default HomePage;
