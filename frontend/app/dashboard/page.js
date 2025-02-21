// frontend/app/dashboard/page.js
"use client";
import { useState } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import {
    Bot,
    FileSearch,
    Search,
    Briefcase,
    Brain,
    GitBranch,
    BookOpen,
    User,
    LogOut,
} from "lucide-react";


// Dynamically import tool components from the tools folder
const InterviewPrep = dynamic(() => import("./tools/InterviewPrep"));
const ResumeAnalyzer = dynamic(() => import("./tools/ResumeAnalyzer"));
const JobDescription = dynamic(() => import("./tools/JobDescription"));
const JobSearch = dynamic(() => import("./tools/JobSearch"));
const CareerGuidance = dynamic(() => import("./tools/CareerGuidance"));
const MindMap = dynamic(() => import("./tools/MindMap"));
const TechNotes = dynamic(() => import("./tools/TechNotes"));

export default function Dashboard() {
    const [activeTool, setActiveTool] = useState(null);

    const tools = [
        {
            id: "interview",
            name: "Interview Prep Bot",
            icon: <Bot className="w-6 h-6 text-purple-600" />,
            description: "Practice interviews with our AI chatbot and get real-time feedback.",
        },
        {
            id: "resume",
            name: "ATS Resume Analyzer",
            icon: <FileSearch className="w-6 h-6 text-blue-500" />,
            description: "Optimize your resume for ATS and stand out to employers.",
        },
        {
            id: "jobDesc",
            name: "Job Description Research",
            icon: <Search className="w-6 h-6 text-purple-600" />,
            description: "Discover required skills and trends for your desired roles.",
        },
        {
            id: "jobSearch",
            name: "Smart Job Search",
            icon: <Briefcase className="w-6 h-6 text-blue-500" />,
            description: "Find job opportunities that match your skills and preferences.",
        },
        {
            id: "careerGuidance",
            name: "Career Guidance Assistant",
            icon: <Brain className="w-6 h-6 text-purple-600" />,
            description: "Get personalized career advice and development recommendations.",
        },
        {
            id: "mindMap",
            name: "Mind Map Generator",
            icon: <GitBranch className="w-6 h-6 text-blue-500" />,
            description: "Visualize and organize your career goals and learning paths.",
        },
        {
            id: "techNotes",
            name: "Tech Notes Generator",
            icon: <BookOpen className="w-6 h-6 text-purple-600" />,
            description: "Generate detailed notes and summaries for new technologies.",
        },
    ];

    const renderActiveTool = () => {
        switch (activeTool) {
            case "interview":
                return <InterviewPrep />;
            case "resume":
                return <ResumeAnalyzer />;
            case "jobDesc":
                return <JobDescription />;
            case "jobSearch":
                return <JobSearch />;
            case "careerGuidance":
                return <CareerGuidance />;
            case "mindMap":
                return <MindMap />;
            case "techNotes":
                return <TechNotes />;
            default:
                return (
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-8">
                        {tools.map((tool) => (
                            <div
                                key={tool.id}
                                onClick={() => setActiveTool(tool.id)}
                                className="cursor-pointer bg-white p-6 rounded-xl shadow-lg hover:shadow-2xl transition transform hover:-translate-y-1"
                            >
                                <div className="mb-4 flex items-center justify-center">
                                    {tool.icon}
                                </div>
                                <h3 className="text-xl font-semibold text-purple-700 mb-2 text-center">
                                    {tool.name}
                                </h3>
                                <p className="text-gray-600 text-center">{tool.description}</p>
                            </div>
                        ))}
                    </div>
                );
        }
    };

    return (

        <div className="min-h-screen flex bg-slate-50">
            {/* Sidebar */}
            <aside className="w-64 bg-white shadow-lg flex flex-col justify-between p-6">
                <div>
                    <h2 className="text-2xl font-bold text-purple-700 mb-8">Dashboard</h2>
                    <nav>
                        <ul className="space-y-4">
                            {tools.map((tool) => (
                                <li key={tool.id}>
                                    <button
                                        onClick={() => setActiveTool(tool.id)}
                                        className={`flex items-center w-full text-left px-3 py-2 rounded-md hover:bg-purple-50 transition ${activeTool === tool.id ? "bg-purple-100" : ""
                                            }`}
                                    >
                                        <span className="mr-3">{tool.icon}</span>
                                        <span className="text-gray-800">{tool.name}</span>
                                    </button>
                                </li>
                            ))}
                        </ul>
                    </nav>
                </div>
                <div className="border-t pt-4">
                    <Link href="/dashboard/profile">
                        <button className="flex items-center w-full text-left px-3 py-2 rounded-md hover:bg-purple-50 transition">
                            <User className="w-5 h-5 text-purple-600 mr-2" />
                            <span className="text-gray-800">Profile</span>
                        </button>
                    </Link>
                    <button className="flex items-center w-full text-left px-3 py-2 rounded-md hover:bg-purple-50 transition mt-2">
                        <LogOut className="w-5 h-5 text-red-600 mr-2" />
                        <span className="text-gray-800">Logout</span>
                    </button>
                </div>
            </aside>

            {/* Main Content Area */}
            <main className="flex-1 p-10">
                {activeTool ? (
                    <div>
                        <button
                            onClick={() => setActiveTool(null)}
                            className="mb-6 text-purple-600 underline"
                        >
                            ← Back to Dashboard
                        </button>
                        {renderActiveTool()}
                    </div>
                ) : (
                    <div>
                        <h1 className="text-3xl font-bold text-gray-800 mb-6">
                            Welcome to Your Dashboard
                        </h1>
                        {renderActiveTool()}
                    </div>
                )}
            </main>
        </div>
    );
}