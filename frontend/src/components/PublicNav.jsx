import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';

const PublicNav = ({ activePage = 'home', navRef, alwaysScrolled = true, extraLinks = [] }) => {
  const [menuOpen, setMenuOpen] = useState(false);

  const closeMenu = () => setMenuOpen(false);

  useEffect(() => {
    if (!menuOpen) return;
    const handleEsc = (e) => { if (e.key === 'Escape') closeMenu(); };
    document.addEventListener('keydown', handleEsc);
    return () => document.removeEventListener('keydown', handleEsc);
  }, [menuOpen]);

  useEffect(() => {
    if (menuOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => { document.body.style.overflow = ''; };
  }, [menuOpen]);

  return (
    <nav className={`home-nav ${alwaysScrolled ? 'nav-scrolled' : ''}`} ref={navRef}>
      <div className="nav-container">
        <Link to="/" className="nav-logo">
          <img src="/logo.png" alt="RomaLume" />
        </Link>

        <div className={`nav-links ${menuOpen ? 'nav-open' : ''}`}>
          {extraLinks.map((link, i) => (
            <a key={i} href={link.href} onClick={closeMenu}>{link.label}</a>
          ))}
          {activePage !== 'home' && (
            <Link to="/" className="nav-link" onClick={closeMenu}>Home</Link>
          )}
          <Link to="/about" className={`nav-link${activePage === 'about' ? ' active' : ''}`} onClick={closeMenu}>About</Link>
          <Link to="/models" className={`nav-link${activePage === 'models' ? ' active' : ''}`} onClick={closeMenu}>Models</Link>
          <Link to="/pricing" className={`nav-link${activePage === 'pricing' ? ' active' : ''}`} onClick={closeMenu}>Pricing</Link>
          <Link to="/login" className="nav-link" onClick={closeMenu}>Login</Link>
          <Link to="/register" className="nav-btn nav-btn-menu" onClick={closeMenu}>Get Started</Link>
        </div>

        <div className="nav-mobile-actions">
          <Link to="/register" className="nav-btn nav-btn-cta">Get Started</Link>
          <button
            className={`nav-hamburger${menuOpen ? ' nav-hamburger-open' : ''}`}
            onClick={() => setMenuOpen(!menuOpen)}
            aria-label="Toggle menu"
          >
            <span></span>
            <span></span>
            <span></span>
          </button>
        </div>
      </div>
      {menuOpen && <div className="nav-backdrop" onClick={closeMenu} />}
    </nav>
  );
};

export default PublicNav;
