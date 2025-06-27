import React from 'react';
import { Link } from 'react-router-dom';
import './HomePage.css';

const HomePage = () => {
  return (
    <div className="home-page">
      <header className="home-header">
        <img src="/logo.png" alt="RomaLume Logo" className="home-logo" />
        <h1>Welcome to RomaLume</h1>
        <p>Your intelligent assistant for research, writing, and discovery.</p>
        <div className="cta-buttons">
          <Link to="/login" className="btn btn-primary">Login</Link>
          <Link to="/register" className="btn btn-secondary">Get Started</Link>
        </div>
      </header>

      <main className="features-section">
        <h2>Why Use This Tool?</h2>
        <div className="features-grid">
          <div className="feature-card">
            <h3>🤖 Multi-Bot Support</h3>
            <p>Seamlessly switch between top-tier language models from OpenAI, Anthropic, Google, and Cohere to find the perfect voice for your task.</p>
          </div>
          <div className="feature-card">
            <h3>🌐 Real-Time Web Search</h3>
            <p>Break free from outdated knowledge. Augment your queries with live, up-to-the-minute web search results for the most accurate answers.</p>
          </div>
          <div className="feature-card">
            <h3>📄 Document Analysis</h3>
            <p>Upload your documents (.pdf, .txt, .md) to provide deep context, summarize key points, or ask specific questions about the content.</p>
          </div>
          <div className="feature-card">
            <h3>🗂️ Persistent Archives</h3>
            <p>Never lose a valuable conversation. Save your chats, organize them by project, and reload them anytime to pick up where you left off.</p>
          </div>
        </div>
      </main>

      <footer className="home-footer">
        <p>© {new Date().getFullYear()} RomaLume. All rights reserved.</p>
      </footer>
    </div>
  );
};

export default HomePage; 