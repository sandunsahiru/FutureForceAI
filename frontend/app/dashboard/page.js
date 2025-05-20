// frontend/app/dashboard/page.js
"use client";
import { useState, useEffect, useRef } from 'react';
import { FileSearch, Bot, Briefcase, Search, Brain, ChevronRight, ChevronLeft, User, LogOut, Home } from 'lucide-react';
import InterviewPrep from './tools/InterviewPrep';
import JobDescription from './tools/JobDescription';
import ResumeAnalyzer from './tools/ResumeAnalyzer';
import JobSearch from './tools/JobSearch';
import CareerGuidance from './tools/CareerGuidance';
import Link from 'next/link';
import Image from 'next/image';

export default function Dashboard() {
  const [activeTool, setActiveTool] = useState(null);
  const [userData, setUserData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isSidebarOpen, setSidebarOpen] = useState(true);
  const [isDropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef(null);

  useEffect(() => {
    // Fetch authenticated user data
    const fetchUserData = async () => {
      try {
        // First verify authentication
        const authResponse = await fetch('/api/auth/check', {
          method: 'GET',
          credentials: 'include',
        });
        
        if (!authResponse.ok) {
          // Redirect to login if not authenticated
          window.location.href = '/login';
          return;
        }
        
        // Fetch user profile data
        const profileResponse = await fetch('/api/users/profile', {
          method: 'GET',
          credentials: 'include',
        });
        
        if (!profileResponse.ok) {
          throw new Error('Failed to fetch user profile');
        }
        
        const userData = await profileResponse.json();
        console.log('User data:', userData); // Debug log
        setUserData(userData);
      } catch (err) {
        console.error('Error fetching user data:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    
    fetchUserData();
  }, []);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setDropdownOpen(false);
      }
    }

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  // Handle logout directly without using Link component
  const handleLogout = async () => {
    try {
      // Direct browser navigation to logout endpoint
      window.location.href = '/api/logout';
    } catch (error) {
      console.error('Error during logout:', error);
    }
  };

  const tools = [
    {
      id: 'interview',
      name: 'Interview Prep Bot',
      icon: <Bot className="w-6 h-6" />,
      description: 'Practice interviews with AI and get real-time feedback',
      color: 'purple'
    },
    {
      id: 'resume',
      name: 'ATS Resume Analyzer',
      icon: <FileSearch className="w-6 h-6" />,
      description: 'Optimize your resume to pass ATS systems',
      color: 'blue'
    },
    {
      id: 'job-description',
      name: 'Job Description Research',
      icon: <Search className="w-6 h-6" />,
      description: 'Analyze job requirements and qualifications',
      color: 'green'
    },
    {
      id: 'job-search',
      name: 'Smart Job Search',
      icon: <Briefcase className="w-6 h-6" />,
      description: 'Find relevant jobs matched to your skills',
      color: 'orange'
    },
    {
      id: 'career-guidance',
      name: 'Career Guidance Assistant',
      icon: <Brain className="w-6 h-6" />,
      description: 'Get personalized career advice and insights',
      color: 'pink'
    }
  ];

  // Render the appropriate tool based on selection
  const renderActiveTool = () => {
    switch (activeTool) {
      case 'interview':
        return <InterviewPrep />;
      case 'job-description':
        return <JobDescription />;
      case 'resume':
        return <ResumeAnalyzer />;
      case 'job-search':
        return <JobSearch />;
      case 'career-guidance':
        return <CareerGuidance />;
      default:
        return null;
    }
  };

  const getColorClasses = (color) => {
    const colors = {
      purple: 'bg-purple-50 text-purple-700 border-purple-200 hover:border-purple-400 hover:bg-purple-100',
      blue: 'bg-blue-50 text-blue-700 border-blue-200 hover:border-blue-400 hover:bg-blue-100',
      green: 'bg-green-50 text-green-700 border-green-200 hover:border-green-400 hover:bg-green-100',
      orange: 'bg-orange-50 text-orange-700 border-orange-200 hover:border-orange-400 hover:bg-orange-100',
      pink: 'bg-pink-50 text-pink-700 border-pink-200 hover:border-pink-400 hover:bg-pink-100'
    };
    return colors[color] || colors.purple;
  };

  const getIconColorClasses = (color) => {
    const colors = {
      purple: 'bg-purple-100 text-purple-600',
      blue: 'bg-blue-100 text-blue-600',
      green: 'bg-green-100 text-green-600',
      orange: 'bg-orange-100 text-orange-600',
      pink: 'bg-pink-100 text-pink-600'
    };
    return colors[color] || colors.purple;
  };

  // Get username from user data
  const getUsername = () => {
    if (!userData) return 'User';
    
    // Use fullName from the User model
    if (userData.fullName) {
      // Get first name from full name
      return userData.fullName.split(' ')[0];
    }
    
    // Fallback to email if name is not available
    if (userData.email) {
      return userData.email.split('@')[0];
    }
    
    return 'User';
  };

  // Show loading state while fetching user data
  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-purple-500 mx-auto"></div>
          <p className="mt-3 text-gray-600">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 flex flex-col">
      {/* Top Bar */}
      <div className="bg-white shadow-sm border-b border-gray-200 sticky top-0 z-50">
        <div className="px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 items-center justify-between">
            <div className="flex items-center">
              <Link href="/" className="text-2xl font-bold bg-gradient-to-r from-purple-600 to-blue-600 bg-clip-text text-transparent">
                FutureForceAI
              </Link>
            </div>
            
            <div className="flex items-center gap-x-4">
              <span className="text-sm text-gray-700 font-medium">
                Welcome, {getUsername()}
              </span>
              
              {/* Custom Dropdown */}
              <div className="relative" ref={dropdownRef}>
                <button
                  onClick={() => setDropdownOpen(!isDropdownOpen)}
                  className="flex items-center justify-center w-10 h-10 rounded-full bg-purple-100 hover:bg-purple-200 transition-colors"
                >
                  <User className="w-5 h-5 text-purple-700" />
                </button>
                
                {isDropdownOpen && (
                  <div className="absolute right-0 mt-2 w-48 origin-top-right rounded-xl bg-white py-2 shadow-lg ring-1 ring-black/5">
                    <Link
                      href="/dashboard/profile"
                      className="flex items-center px-4 py-2 text-sm text-gray-700 hover:bg-purple-50"
                      onClick={() => setDropdownOpen(false)}
                    >
                      <User className="w-4 h-4 mr-3" />
                      Profile
                    </Link>
                    <button
                      onClick={() => {
                        setDropdownOpen(false);
                        handleLogout();
                      }}
                      className="flex items-center px-4 py-2 text-sm text-gray-700 hover:bg-purple-50 w-full text-left"
                    >
                      <LogOut className="w-4 h-4 mr-3" />
                      Logout
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="flex flex-1">
        {/* Sidebar - Only shown when a tool is active */}
        {activeTool && (
          <aside
            className={`${
              isSidebarOpen ? 'w-72' : 'w-16'
            } bg-white border-r border-gray-200 min-h-[calc(100vh-4rem)] transition-all duration-300 ease-in-out shadow-lg`}
          >
            <div className="flex flex-col h-full">
              <div className="flex items-center justify-between p-4 border-b border-gray-200">
                {isSidebarOpen && (
                  <h2 className="text-lg font-semibold text-gray-900">Tools</h2>
                )}
                <button
                  onClick={() => setSidebarOpen(!isSidebarOpen)}
                  className="p-2 rounded-lg hover:bg-purple-50"
                >
                  {isSidebarOpen ? (
                    <ChevronLeft className="w-5 h-5 text-gray-600" />
                  ) : (
                    <ChevronRight className="w-5 h-5 text-gray-600" />
                  )}
                </button>
              </div>
              
              <nav className="flex-1 px-3 py-4 space-y-1">
                <button
                  onClick={() => setActiveTool(null)}
                  className={`w-full flex items-center ${
                    isSidebarOpen ? 'px-3' : 'justify-center'
                  } py-3 rounded-lg text-gray-700 hover:bg-purple-50 transition-colors group`}
                >
                  <Home className="w-5 h-5 text-gray-500 group-hover:text-purple-600 flex-shrink-0" />
                  {isSidebarOpen && <span className="ml-3">Dashboard</span>}
                </button>
                
                {tools.map((tool) => (
                  <button
                    key={tool.id}
                    onClick={() => setActiveTool(tool.id)}
                    className={`w-full flex items-center ${
                      isSidebarOpen ? 'px-3' : 'justify-center'
                    } py-3 rounded-lg transition-all duration-200 ${
                      activeTool === tool.id
                        ? 'bg-purple-100 text-purple-700'
                        : 'text-gray-700 hover:bg-purple-50'
                    }`}
                  >
                    <div className={`flex-shrink-0 ${activeTool === tool.id ? 'text-purple-600' : 'text-gray-500'}`}>
                      {tool.icon}
                    </div>
                    {isSidebarOpen && (
                      <span className="ml-3 text-left flex-1">
                        {tool.name.includes('Job Description') ? (
                          <>
                            <span className="block">Job Description</span>
                            <span className="block">Research</span>
                          </>
                        ) : tool.name.includes('Career Guidance') ? (
                          <>
                            <span className="block">Career Guidance</span>
                            <span className="block">Assistant</span>
                          </>
                        ) : (
                          tool.name
                        )}
                      </span>
                    )}
                  </button>
                ))}
              </nav>
              
              <div className="border-t border-gray-200">
                <div className="p-3 space-y-1">
                  <Link
                    href="/dashboard/profile"
                    className={`flex items-center ${
                      isSidebarOpen ? 'px-3' : 'justify-center'
                    } py-3 rounded-lg text-gray-700 hover:bg-purple-50`}
                  >
                    <User className="w-5 h-5 text-gray-500 flex-shrink-0" />
                    {isSidebarOpen && <span className="ml-3">Profile</span>}
                  </Link>
                  <button
                    onClick={handleLogout}
                    className={`flex items-center w-full ${
                      isSidebarOpen ? 'px-3' : 'justify-center'
                    } py-3 rounded-lg text-gray-700 hover:bg-purple-50 text-left`}
                  >
                    <LogOut className="w-5 h-5 text-gray-500 flex-shrink-0" />
                    {isSidebarOpen && <span className="ml-3">Logout</span>}
                  </button>
                </div>
              </div>
            </div>
          </aside>
        )}

        {/* Main Content */}
        <main className={`flex-1 ${activeTool ? 'p-8' : 'p-6 sm:p-8 lg:p-12'}`}>
          {!activeTool ? (
            <>
              <div className="mb-12 text-center">
                <h2 className="text-4xl font-bold text-gray-900 mb-4">Welcome to FutureForceAI</h2>
                <p className="text-xl text-gray-600 max-w-3xl mx-auto leading-relaxed">
                  Select a tool to get started with your career journey. Our AI-powered platform helps you succeed.
                </p>
              </div>

              <div className="grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-3 max-w-7xl mx-auto">
                {tools.map((tool) => (
                  <button
                    key={tool.id}
                    onClick={() => setActiveTool(tool.id)}
                    className={`group p-8 rounded-2xl border-2 transition-all duration-300 hover:scale-[1.02] hover:shadow-xl ${getColorClasses(tool.color)}`}
                  >
                    <div className="flex items-center mb-6">
                      <div className={`p-4 rounded-xl ${getIconColorClasses(tool.color)} shadow-sm`}>
                        {tool.icon}
                      </div>
                      <h3 className="ml-4 text-xl font-semibold">{tool.name}</h3>
                    </div>
                    <p className="text-sm opacity-90 leading-relaxed">{tool.description}</p>
                  </button>
                ))}
              </div>
            </>
          ) : (
            <>
              <div className="mb-8">
                <h2 className="text-3xl font-bold text-gray-900">
                  {tools.find(tool => tool.id === activeTool)?.name}
                </h2>
                <p className="mt-3 text-lg text-gray-600">
                  {tools.find(tool => tool.id === activeTool)?.description}
                </p>
              </div>
              
              <div className="bg-white rounded-2xl shadow-lg border border-gray-200">
                {renderActiveTool()}
              </div>
            </>
          )}
        </main>
      </div>

      {/* Simple Footer */}
      <footer className="bg-white border-t border-gray-200">
        <div className="px-4 py-6 text-center">
          <p className="text-sm text-gray-600">© 2025 FutureForceAI. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}