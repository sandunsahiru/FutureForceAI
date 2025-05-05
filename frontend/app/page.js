// app/page.js
import { Brain, Users, Briefcase, Search, Bot, FileSearch, MapPin, BookOpen, GitBranch, Sparkles } from 'lucide-react';
import Header from './Header';
import Footer from './Footer';
import Link from 'next/link';
import Image from 'next/image';


export default function Home() {
  return (
    <div className="bg-slate-50">
      <Header />

      {/* HERO SECTION - Updated description */}
      <section className="pt-32 pb-20 px-4 bg-gradient-to-br from-purple-50 via-white to-blue-50">
        <div className="max-w-7xl mx-auto grid md:grid-cols-2 gap-12 items-center">
          <div>
            <h2 className="text-5xl md:text-6xl font-bold leading-tight mb-6">
              <span className="bg-gradient-to-r from-purple-600 to-blue-500 bg-clip-text text-transparent">
                Transform
              </span>
              <span className="text-indigo-600"> Your Career with AI</span>
            </h2>
            <p className="text-lg text-gray-700 mb-8">
              FutureForceAI is your comprehensive AI-powered career platform featuring interview preparation, 
              resume optimization, job search, career guidance, and interactive learning tools—all in one place.
            </p>
            <div className="flex gap-4">
              <Link 
                href="/register"
                className="bg-gradient-to-r from-purple-600 to-blue-500 text-white px-8 py-3 rounded-full hover:shadow-lg transition-all"
              >
                Sign Up
              </Link>
              <button className="border border-purple-600 text-purple-600 px-8 py-3 rounded-full hover:bg-purple-50 transition-all">
                Learn More
              </button>
            </div>
          </div>
          <div className="relative">
            <img 
              src="https://i.ibb.co/27YW6ZZT/webbanner1.jpg" 
              alt="AI Career Platform" 
              className="w-full h-auto"
            />
          </div>
        </div>
      </section>

      {/* FEATURES SECTION - Updated with all tools */}
      <section id="features" className="py-20 px-4">
        <div className="max-w-7xl mx-auto text-center">
          <h3 className="text-3xl font-bold mb-12">
            <span className="bg-gradient-to-r from-purple-600 to-blue-500 bg-clip-text text-transparent">
              AI-Powered Career Tools
            </span>
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {[
              {
                icon: <Bot className="w-8 h-8 text-purple-600" />,
                title: "Interview Prep Bot",
                description: "Practice interviews with our AI chatbot and receive real-time feedback to improve your performance."
              },
              {
                icon: <FileSearch className="w-8 h-8 text-blue-500" />,
                title: "ATS Resume Analyzer",
                description: "Get detailed feedback and instructions to make your resume ATS-friendly and stand out to employers."
              },
              {
                icon: <Search className="w-8 h-8 text-purple-600" />,
                title: "Job Description Research",
                description: "Analyze job roles to understand required skills, qualifications, and industry trends."
              },
              {
                icon: <Briefcase className="w-8 h-8 text-blue-500" />,
                title: "Smart Job Search",
                description: "Find relevant job openings matched to your skills and preferences using AI-powered search."
              },
              {
                icon: <Brain className="w-8 h-8 text-purple-600" />,
                title: "Career Guidance Assistant",
                description: "Receive personalized career advice and development recommendations from our AI assistant."
              },
              {
                icon: <GitBranch className="w-8 h-8 text-blue-500" />,
                title: "Mind Map Generator",
                description: "Create visual mind maps to organize career paths, skills, and learning objectives."
              },
              {
                icon: <BookOpen className="w-8 h-8 text-purple-600" />,
                title: "Tech Notes Generator",
                description: "Generate comprehensive study materials and notes for new technologies and skills."
              }
            ].map((feature, index) => (
              <div key={index} className="bg-white p-8 rounded-xl shadow-lg hover:shadow-xl transition-all hover:-translate-y-1">
                <div className="bg-purple-50 w-16 h-16 rounded-xl flex items-center justify-center mb-4 mx-auto">
                  {feature.icon}
                </div>
                <h4 className="text-xl font-semibold mb-3 text-gray-900">{feature.title}</h4>
                <p className="text-gray-700">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* HOW IT WORKS SECTION - Updated steps */}
      <section id="how-it-works" className="py-20 px-4 bg-gradient-to-br from-purple-50 via-white to-blue-50">
        <div className="max-w-7xl mx-auto text-center">
          <h3 className="text-3xl font-bold mb-12 bg-gradient-to-r from-purple-600 to-blue-500 bg-clip-text text-transparent">
            How It Works
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {[
              {
                step: "1",
                title: "Create Your Profile",
                description: "Set up your profile with your career goals, skills, and preferences for personalized recommendations."
              },
              {
                step: "2",
                title: "Access AI Tools",
                description: "Use our suite of AI-powered tools for resume optimization, interview practice, and career guidance."
              },
              {
                step: "3",
                title: "Achieve Your Goals",
                description: "Track your progress, learn new skills, and advance your career with continuous AI support."
              }
            ].map((step, index) => (
              <div key={index} className="bg-white p-8 rounded-xl shadow-lg relative group hover:shadow-xl transition-all">
                <div className="absolute -top-6 left-1/2 -translate-x-1/2 w-12 h-12 bg-gradient-to-r from-purple-600 to-blue-500 rounded-full flex items-center justify-center text-white font-bold text-xl group-hover:scale-110 transition-transform">
                  {step.step}
                </div>
                <h4 className="text-xl font-semibold mt-6 mb-3 text-gray-900">{step.title}</h4>
                <p className="text-gray-700">{step.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* SUCCESS STORIES SECTION */}
      <section id="success-stories" className="py-20 px-4">
        <div className="max-w-7xl mx-auto text-center">
          <h3 className="text-3xl font-bold mb-12 bg-gradient-to-r from-purple-600 to-blue-500 bg-clip-text text-transparent">
            Success Stories
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {[
              {
                quote: "FutureForceAI transformed my resume and helped me ace interviews. I landed my dream job in just two weeks!",
                author: "Sarah T.",
                role: "Software Engineer"
              },
              {
                quote: "The personalized career guidance gave me clarity on my skill gaps. Now I'm upskilling with confidence!",
                author: "Michael B.",
                role: "Marketing Manager"
              }
            ].map((story, index) => (
              <div key={index} className="bg-white p-8 rounded-xl shadow-lg relative group hover:shadow-xl transition-all">
                <Sparkles className="absolute top-4 right-4 text-purple-400 w-6 h-6" />
                <p className="text-gray-600 mb-6 italic">{story.quote}</p>
                <div className="flex items-center gap-4 justify-center">
                  <div className="w-12 h-12 bg-gradient-to-br from-purple-400 to-blue-400 rounded-full"></div>
                  <div className="text-left">
                    <h4 className="font-semibold text-gray-900">{story.author}</h4>
                    <p className="text-sm text-gray-500">{story.role}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CALL-TO-ACTION SECTION */}
      <section className="py-20 px-4">
        <div className="max-w-4xl mx-auto">
          <div className="bg-gradient-to-r from-purple-600 to-blue-500 p-12 rounded-3xl shadow-xl text-center">
            <h3 className="text-3xl font-bold text-white mb-6">Ready to Boost Your Career?</h3>
            <p className="text-white/90 mb-8">
              Sign up today and unlock personalized career support and AI-powered insights.
            </p>
            <button className="bg-white text-purple-600 px-8 py-3 rounded-full hover:shadow-lg transition-all">
              Join Now
            </button>
          </div>
        </div>
      </section>


      <Footer />
    </div>
  );
}