import React from 'react';
import { Link } from 'react-router-dom';
import './HomePage.css';
import './AboutPage.css';

const AboutNav = () => (
    <nav className="home-nav">
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
                        An AI writing tool with a purpose
                    </p>

                    <section className="about-section">
                        <h2>Why 100% of Profits Go to Charity</h2>
                        <p>
                            RomaLume was created by Sage Lewis, someone who has dedicated years to
                            helping people experiencing homelessness in Akron, Ohio. Every dollar
                            of profit from your subscription goes directly to <a href="https://houselessmovement.org" target="_blank" rel="noopener noreferrer">Houseless Movement</a>,
                            a 501(c)(3) nonprofit continuing this work.
                        </p>
                    </section>

                    <section className="about-section">
                        <h2>The Story Behind the Mission</h2>
                        <p>
                            This isn't a corporate giving program or a marketing angle. It's personal.
                        </p>
                        <p>
                            Sage has hosted a tent village on his property, giving people a safe place
                            to stay. He's run a day center where folks could come in from the cold,
                            get a meal, and find resources. He now operates a house providing stable
                            housing for three senior homeless men.
                        </p>
                        <p>
                            Today, he runs the <strong>Nomadic Spirit</strong> — a mobile community center
                            built from a camper. It travels to where people are, bringing hot dogs, coffee,
                            lemonade, and music. But more than anything, it brings connection.
                        </p>
                    </section>

                    <section className="about-section highlight">
                        <h2>It's About Connection</h2>
                        <p>
                            The Nomadic Spirit isn't a soup kitchen on wheels. It's about sharing a moment
                            with people who often feel invisible — left out of the larger community.
                            It's about sitting down, having a conversation, and reminding someone that
                            they matter.
                        </p>
                        <p>
                            When you subscribe to RomaLume, you're not just getting access to powerful
                            AI writing tools. You're directly funding this work.
                        </p>
                    </section>

                    <section className="about-section">
                        <h2>About Houseless Movement</h2>
                        <p>
                            <a href="https://houselessmovement.org" target="_blank" rel="noopener noreferrer">Houseless Movement</a> is
                            a 501(c)(3) nonprofit organization based in Akron, Ohio. It provides direct
                            support to people experiencing homelessness through outreach, housing assistance,
                            and community building.
                        </p>
                    </section>

                    <div className="about-cta">
                        <p>Ready to write better while making a difference?</p>
                        <Link to="/register" className="btn btn-primary btn-large">Get Started Free</Link>
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
