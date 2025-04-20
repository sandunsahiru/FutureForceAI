// frontend/app/dashboard/page.js
"use client";
import { useState } from 'react';
import { FileSearch, Bot, Briefcase, Search, Brain, GitBranch, BookOpen } from 'lucide-react';
import InterviewPrep from './tools/InterviewPrep';
import Link from 'next/link';

export default function Dashboard() {
  const [activeTool, setActiveTool] = useState('interview');

  const tools = [
    {
      id: 'interview',
      name: 'Interview Prep Bot',
      icon: <Bot className="w-6 h-6" />,
      description: 'Practice interviews with AI and get real-time feedback'
    },
    {
      id: 'resume',
      name: 'ATS Resume Analyzer',
      icon: <FileSearch className="w-6 h-6" />,
      description: 'Optimize your resume to pass ATS systems'
    },
    {
      id: 'job-description',
      name: 'Job Description Research',
      icon: <Search className="w-6 h-6" />,
      description: 'Analyze job requirements and qualifications'
    },
    {
      id: 'job-search',
      name: 'Smart Job Search',
      icon: <Briefcase className="w-6 h-6" />,
      description: 'Find relevant jobs matched to your skills'
    },
    {
      id: 'career-guidance',
      name: 'Career Guidance Assistant',
      icon: <Brain className="w-6 h-6" />,
      description: 'Get personalized career advice and insights'
    },
    {
      id: 'mind-map',
      name: 'Mind Map Generator',
      icon: <GitBranch className="w-6 h-6" />,
      description: 'Create visual maps of career paths and skills'
    },
    {
      id: 'tech-notes',
      name: 'Tech Notes Generator',
      icon: <BookOpen className="w-6 h-6" />,
      description: 'Generate comprehensive study materials'
    }
  ];

  // Render the appropriate tool based on selection
  const renderActiveTool = () => {
    switch (activeTool) {
      case 'interview':
        return <InterviewPrep />;
      case 'resume':
        return <div className="p-6 bg-white rounded-xl shadow-md">ATS Resume Analyzer (Coming soon)</div>;
      case 'job-description':
        return <div className="p-6 bg-white rounded-xl shadow-md">Job Description Research (Coming soon)</div>;
      case 'job-search':
        return <div className="p-6 bg-white rounded-xl shadow-md">Smart Job Search (Coming soon)</div>;
      case 'career-guidance':
        return <div className="p-6 bg-white rounded-xl shadow-md">Career Guidance Assistant (Coming soon)</div>;
      case 'mind-map':
        return <div className="p-6 bg-white rounded-xl shadow-md">Mind Map Generator (Coming soon)</div>;
      case 'tech-notes':
        return <div className="p-6 bg-white rounded-xl shadow-md">Tech Notes Generator (Coming soon)</div>;
      default:
        return <div className="p-6 bg-white rounded-xl shadow-md">Select a tool from the sidebar</div>;
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex">
      {/* Sidebar */}
      <div className="w-64 bg-white shadow-md">
        <div className="p-6">
          <h2 className="text-xl font-bold text-purple-700">Dashboard</h2>
        </div>
        <nav className="mt-2">
          {tools.map((tool) => (
            <button
              key={tool.id}
              onClick={() => setActiveTool(tool.id)}
              className={`w-full flex items-center gap-3 p-4 hover:bg-purple-50 transition-colors ${
                activeTool === tool.id ? 'bg-purple-100 border-l-4 border-purple-600' : ''
              }`}
            >
              <div className={`${activeTool === tool.id ? 'text-purple-600' : 'text-gray-600'}`}>
                {tool.icon}
              </div>
              <span className={`${activeTool === tool.id ? 'text-purple-600 font-medium' : 'text-gray-700'}`}>
                {tool.name}
              </span>
            </button>
          ))}
        </nav>
        <div className="absolute bottom-0 w-64 border-t p-4">
          <div className="flex gap-4 mb-4">
            <Link href="/dashboard/profile" className="text-purple-600 text-sm hover:underline">
              Profile
            </Link>
            <Link href="/api/logout" className="text-purple-600 text-sm hover:underline">
              Logout
            </Link>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 p-8">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-800">Welcome to FutureForceAI</h1>
          <p className="text-gray-600">Select a tool from the sidebar to get started.</p>
        </div>

        {/* Active Tool */}
        <div className="mb-8">
          <div className="flex items-center mb-4">
            <h2 className="text-xl font-semibold text-gray-800">
              {tools.find(tool => tool.id === activeTool)?.name}
            </h2>
          </div>
          {renderActiveTool()}
        </div>
      </div>
    </div>
  );
}