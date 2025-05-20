'use client';

import { useState, useEffect } from 'react';
import { Menu, X, LayoutDashboard } from 'lucide-react';
import Link from 'next/link';

export default function Header() {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isScrolled, setIsScrolled] = useState(false);
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 0);
    };
    
    window.addEventListener('scroll', handleScroll);
    
    // Check if user is logged in
    const checkAuthStatus = async () => {
      try {
        const response = await fetch('/api/auth/check', {
          method: 'GET',
          credentials: 'include',
        });
        
        const data = await response.json();
        setIsLoggedIn(data.authenticated);
      } catch (error) {
        console.error('Error checking auth status:', error);
        setIsLoggedIn(false);
      }
    };
    
    checkAuthStatus();
    
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const navigationLinks = [
    { name: 'Features', href: '#features' },
    { name: 'How it Works', href: '#how-it-works' },
    { name: 'Success Stories', href: '#success-stories' },
    { name: 'Contact Us', href:'#'}
  ];

  const handleMenuClick = () => {
    setIsMenuOpen(!isMenuOpen);
  };

  const handleLinkClick = () => {
    setIsMenuOpen(false);
  };

  return (
    <header className={`fixed w-full z-50 transition-all duration-300 ${
      isScrolled ? 'bg-white/80 backdrop-blur-lg' : 'bg-transparent'
    } border-b border-gray-200`}>
      <div className="max-w-7xl mx-auto px-4 py-4">
        {/* Desktop Navigation */}
        <div className="flex items-center justify-between">
          <Link href="/" className="text-2xl font-bold bg-gradient-to-r from-purple-600 to-blue-500 bg-clip-text text-transparent">
            FutureForceAI
          </Link>

          <nav className="hidden md:flex items-center space-x-8">
            {navigationLinks.map((link) => (
              <a
                key={link.name}
                href={link.href}
                className="text-gray-700 hover:text-purple-600 transition-colors"
                onClick={handleLinkClick}
              >
                {link.name}
              </a>
            ))}
            
            {isLoggedIn ? (
              <div className="flex items-center space-x-4">
                <Link
                  href="/dashboard"
                  className="flex items-center space-x-2 text-gray-700 hover:text-purple-600 transition-colors"
                >
                  <LayoutDashboard size={20} />
                  <span>Dashboard</span>
                </Link>
              </div>
            ) : (
              <Link
                href="/login"
                className="bg-gradient-to-r from-purple-600 to-blue-500 text-white px-6 py-2 rounded-full hover:shadow-lg transition-all"
              >
                Login
              </Link>
            )}
          </nav>

          {/* Mobile Menu Button */}
          <button
            className="md:hidden text-gray-700 hover:text-purple-600 transition-colors"
            onClick={handleMenuClick}
            aria-label="Toggle menu"
          >
            {isMenuOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
        </div>

        {/* Mobile Navigation */}
        {isMenuOpen && (
          <div className="md:hidden">
            <nav className="mt-4 bg-white rounded-lg shadow-lg overflow-hidden">
              {navigationLinks.map((link) => (
                <a
                  key={link.name}
                  href={link.href}
                  className="block px-4 py-3 text-gray-700 hover:bg-purple-50 hover:text-purple-600 transition-colors border-b border-gray-100"
                  onClick={handleLinkClick}
                >
                  {link.name}
                </a>
              ))}
              
              {isLoggedIn ? (
                <Link
                  href="/dashboard"
                  className="flex items-center space-x-2 px-4 py-3 text-gray-700 hover:bg-purple-50 hover:text-purple-600 transition-colors border-b border-gray-100"
                  onClick={handleLinkClick}
                >
                  <LayoutDashboard size={20} />
                  <span>Dashboard</span>
                </Link>
              ) : (
                <Link
                  href="/login"
                  className="block px-4 py-3 bg-gradient-to-r from-purple-600 to-blue-500 text-white hover:shadow-inner transition-all"
                  onClick={handleLinkClick}
                >
                  Login
                </Link>
              )}
            </nav>
          </div>
        )}
      </div>
    </header>
  );
}