"use client";
import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { 
  Brain, 
  Upload, 
  FileText, 
  Target, 
  BookOpen, 
  Briefcase, 
  GraduationCap, 
  TrendingUp, 
  Award, 
  Lightbulb, 
  CheckCircle, 
  AlertCircle, 
  ChevronRight, 
  Star, 
  BarChart3, 
  Rocket, 
  Map, 
  Compass,
  Users,
  LineChart,
  Trophy,
  Zap,
  ArrowRight,
  Plus,
  X,
  Loader,
  RefreshCw
} from "lucide-react";

export default function CareerGuidance() {
  // State management
  const [cvFile, setCvFile] = useState(null);
  const [savedCVs, setSavedCVs] = useState([]);
  const [showCVSelector, setShowCVSelector] = useState(false);
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  
  // Career preferences
  const [careerInterests, setCareerInterests] = useState([]);
  const [customInterest, setCustomInterest] = useState("");
  const [careerGoals, setCareerGoals] = useState({
    shortTerm: "",
    longTerm: "",
    yearsExperience: "",
    desiredRole: "",
    industry: "",
    workStyle: "",
    priorities: []
  });
  
  // Analysis results
  const [careerAnalysis, setCareerAnalysis] = useState(null);
  const [careerPaths, setCareerPaths] = useState([]);
  const [skillGaps, setSkillGaps] = useState([]);
  const [learningResources, setLearningResources] = useState([]);
  const [activeTab, setActiveTab] = useState('overview');
  
  const router = useRouter();
  const resultsRef = useRef(null);

  // Predefined career interests
  const predefinedInterests = [
    "Software Development",
    "Data Science",
    "Machine Learning/AI",
    "Cloud Architecture",
    "DevOps",
    "Cybersecurity",
    "Product Management",
    "UX/UI Design",
    "Business Analysis",
    "Project Management",
    "Full Stack Development",
    "Mobile Development",
    "Database Administration",
    "Quality Assurance",
    "Technical Writing"
  ];

  // Work priorities
  const workPriorities = [
    "Work-Life Balance",
    "High Salary",
    "Career Growth",
    "Job Security",
    "Remote Work",
    "Innovation",
    "Team Collaboration",
    "Leadership Opportunities",
    "Learning & Development",
    "Company Culture",
    "Social Impact",
    "Technical Challenges"
  ];

  // Check authentication on component mount
  useEffect(() => {
    const checkAuth = async () => {
      try {
        const response = await fetch("/api/auth/check", {
          method: "GET",
          credentials: "include"
        });
        
        const data = await response.json();
        
        if (!response.ok || !data.authenticated) {
          router.push("/login?from=" + encodeURIComponent(window.location.pathname));
          return;
        }
        
        setIsAuthenticated(true);
        fetchSavedCVs();
      } catch (err) {
        console.error("Error checking authentication:", err);
        router.push("/login");
      }
    };
    
    checkAuth();
  }, [router]);

  // Fetch user's saved CVs
  const fetchSavedCVs = async () => {
    try {
      setLoading(true);
      const response = await fetch("/api/user/cvs", {
        credentials: "include"
      });
      
      if (response.ok) {
        const data = await response.json();
        setSavedCVs(data.cvs || []);
        
        // Auto-select most recent CV
        if (data.cvs && data.cvs.length > 0) {
          const sortedCVs = [...data.cvs].sort((a, b) => 
            new Date(b.uploadedAt) - new Date(a.uploadedAt)
          );
          handleSelectCV(sortedCVs[0]);
        }
      }
    } catch (err) {
      console.error("Error fetching saved CVs:", err);
    } finally {
      setLoading(false);
    }
  };

  // Handle file upload
  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      const validTypes = ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
      if (!validTypes.includes(file.type)) {
        setError("Please select a PDF or Word document (.pdf, .doc, .docx)");
        setTimeout(() => setError(null), 5000);
        return;
      }
      
      if (file.size > 10 * 1024 * 1024) {
        setError("File size exceeds the maximum limit of 10MB");
        setTimeout(() => setError(null), 5000);
        return;
      }
      
      setCvFile(file);
    }
  };

  // Handle selecting a saved CV
  const handleSelectCV = (cv) => {
    setShowCVSelector(false);
    const savedCv = {
      ...cv,
      name: cv.filename || cv.originalName,
      useSaved: true,
      id: cv.id
    };
    setCvFile(savedCv);
  };

  // Add career interest
  const addCareerInterest = (interest) => {
    if (!careerInterests.includes(interest)) {
      setCareerInterests([...careerInterests, interest]);
    }
  };

  // Add custom career interest
  const addCustomInterest = () => {
    if (customInterest.trim() && !careerInterests.includes(customInterest)) {
      setCareerInterests([...careerInterests, customInterest.trim()]);
      setCustomInterest("");
    }
  };

  // Remove career interest
  const removeCareerInterest = (interest) => {
    setCareerInterests(careerInterests.filter(item => item !== interest));
  };

  // Toggle work priority
  const togglePriority = (priority) => {
    const currentPriorities = careerGoals.priorities || [];
    let newPriorities;
    
    if (currentPriorities.includes(priority)) {
      newPriorities = currentPriorities.filter(p => p !== priority);
    } else {
      newPriorities = [...currentPriorities, priority];
    }
    
    setCareerGoals({
      ...careerGoals,
      priorities: newPriorities
    });
  };

  // Analyze career path
  const analyzeCareerPath = async () => {
    if (!cvFile) {
      setError("Please upload or select your CV first");
      setTimeout(() => setError(null), 3000);
      return;
    }

    if (careerInterests.length === 0) {
      setError("Please select at least one career interest");
      setTimeout(() => setError(null), 3000);
      return;
    }

    try {
      setAnalyzing(true);
      setError(null);
      
      const requestData = {
        cv_id: cvFile.useSaved ? cvFile.id : null,
        career_interests: careerInterests,
        career_goals: careerGoals
      };

      // If new CV file, upload it first
      if (!cvFile.useSaved) {
        const formData = new FormData();
        formData.append("cv_file", cvFile);
        
        const uploadResponse = await fetch("/api/career-guidance/upload-cv", {
          method: "POST",
          body: formData,
          credentials: "include"
        });

        if (!uploadResponse.ok) {
          throw new Error("Failed to upload CV");
        }

        const uploadData = await uploadResponse.json();
        requestData.cv_id = uploadData.cv_id;
      }

      // Analyze career path
      const response = await fetch("/api/career-guidance/analyze", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(requestData),
        credentials: "include"
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to analyze career path");
      }

      const data = await response.json();
      setCareerAnalysis(data.analysis);
      setCareerPaths(data.career_paths || []);
      setSkillGaps(data.skill_gaps || []);
      setLearningResources(data.learning_resources || []);

      // Scroll to results
      if (resultsRef.current) {
        resultsRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    } catch (err) {
      console.error("Error analyzing career path:", err);
      setError(err.message || "Error analyzing career path. Please try again.");
      setTimeout(() => setError(null), 3000);
    } finally {
      setAnalyzing(false);
    }
  };

  // Render skill level indicator
  const renderSkillLevel = (level) => {
    const levels = {
      'Beginner': { width: '25%', color: 'bg-red-500' },
      'Intermediate': { width: '50%', color: 'bg-yellow-500' },
      'Advanced': { width: '75%', color: 'bg-green-500' },
      'Expert': { width: '100%', color: 'bg-blue-500' }
    };

    const skillInfo = levels[level] || levels['Beginner'];

    return (
      <div className="w-32 bg-gray-200 rounded-full h-2">
        <div 
          className={`h-2 rounded-full ${skillInfo.color}`}
          style={{ width: skillInfo.width }}
        ></div>
      </div>
    );
  };

  // If not authenticated, show loading
  if (!isAuthenticated && !error) {
    return (
      <div className="p-6 bg-white rounded-xl shadow-md">
        <h2 className="text-2xl font-bold text-purple-700 mb-4">
          Career Guidance Assistant
        </h2>
        <div className="flex items-center justify-center h-40">
          <div className="animate-spin rounded-full h-10 w-10 border-t-2 border-b-2 border-purple-500"></div>
          <span className="ml-3 text-gray-600">Checking authentication...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 bg-white rounded-xl shadow-md">
      <h2 className="text-2xl font-bold text-purple-700 mb-4">
        Career Guidance Assistant
      </h2>
      
      {/* Error message display */}
      {error && (
        <div className="mb-4 p-3 bg-red-100 border border-red-300 text-red-700 rounded flex items-center">
          <AlertCircle className="mr-2 h-5 w-5" />
          <p>{error}</p>
        </div>
      )}
      
      {/* Success message display */}
      {success && (
        <div className="mb-4 p-3 bg-green-100 border border-green-300 text-green-700 rounded flex items-center">
          <CheckCircle className="mr-2 h-5 w-5" />
          <p>{success}</p>
        </div>
      )}
      
      <div className="space-y-8">
        {/* CV Upload Section */}
        <div className="bg-gray-50 p-4 rounded-lg border border-gray-200">
          <h3 className="text-lg font-medium text-gray-800 mb-3 flex items-center">
            <FileText className="mr-2 h-5 w-5 text-purple-600" />
            Step 1: Upload Your CV
          </h3>
          
          {cvFile ? (
            <div className="flex items-center p-3 border rounded bg-purple-50">
              <div className="flex-1">
                <p className="font-medium text-gray-800">{cvFile.name}</p>
                <p className="text-sm text-gray-600">
                  {cvFile.size ? `${Math.round(cvFile.size / 1024)} KB` : ""}
                </p>
              </div>
              <button
                onClick={() => setCvFile(null)}
                className="text-red-500 hover:text-red-700"
                title="Remove CV"
              >
                <X size={18} />
              </button>
            </div>
          ) : (
            <div className="flex gap-3">
              <button
                onClick={() => setShowCVSelector(!showCVSelector)}
                className="flex-1 px-4 py-2 border border-purple-300 rounded text-purple-700 hover:bg-purple-50 transition flex items-center justify-center"
              >
                <FileText size={16} className="mr-2" /> 
                Select Saved CV
              </button>
              <label className="flex-1 px-4 py-2 bg-purple-600 text-white rounded hover:bg-purple-700 transition cursor-pointer flex items-center justify-center">
                <Upload size={16} className="mr-2" /> 
                Upload New CV
                <input
                  type="file"
                  accept=".pdf,.doc,.docx"
                  onChange={handleFileChange}
                  className="hidden"
                />
              </label>
            </div>
          )}
          
          {/* Saved CVs Selector */}
          {showCVSelector && (
            <div className="mt-3 border rounded p-3 bg-white shadow-md">
              <h4 className="font-medium text-gray-800 mb-2">Your Saved CVs</h4>
              
              {loading ? (
                <div className="py-8 flex justify-center items-center">
                  <div className="animate-spin rounded-full h-6 w-6 border-2 border-purple-500 border-t-transparent"></div>
                </div>
              ) : savedCVs.length === 0 ? (
                <div className="text-center py-4">
                  <FileText className="mx-auto h-10 w-10 text-gray-300 mb-2" />
                  <p className="text-gray-500">No saved CVs found. Upload a new one.</p>
                </div>
              ) : (
                <ul className="divide-y">
                  {savedCVs.map((cv) => (
                    <li key={cv.id} className="py-2">
                      <button 
                        onClick={() => handleSelectCV(cv)}
                        className="w-full text-left hover:bg-purple-50 p-2 rounded flex items-center justify-between"
                      >
                        <div>
                          <div className="font-medium text-gray-800">{cv.filename}</div>
                          <div className="text-sm text-gray-600">
                            {new Date(cv.uploadedAt).toLocaleDateString()} • {Math.round(cv.size/1024)} KB
                          </div>
                        </div>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>

        {/* Career Interests Section */}
        <div className="bg-gray-50 p-4 rounded-lg border border-gray-200">
          <h3 className="text-lg font-medium text-gray-800 mb-3 flex items-center">
            <Target className="mr-2 h-5 w-5 text-purple-600" />
            Step 2: Select Your Career Interests
          </h3>
          
          <div className="mb-4">
            <p className="text-sm text-gray-600 mb-3">
              Select career paths you're interested in exploring:
            </p>
            
            <div className="flex flex-wrap gap-2 mb-4">
              {predefinedInterests.map((interest) => (
                <button
                  key={interest}
                  onClick={() => addCareerInterest(interest)}
                  disabled={careerInterests.includes(interest)}
                  className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                    careerInterests.includes(interest)
                      ? 'bg-purple-100 text-purple-700 cursor-not-allowed'
                      : 'bg-white border border-purple-300 text-purple-700 hover:bg-purple-50'
                  }`}
                >
                  {interest}
                </button>
              ))}
            </div>
            
            <div className="flex gap-2">
              <input
                type="text"
                value={customInterest}
                onChange={(e) => setCustomInterest(e.target.value)}
                placeholder="Add custom career interest"
                className="flex-1 px-3 py-2 border border-gray-300 rounded-md"
                onKeyPress={(e) => e.key === 'Enter' && addCustomInterest()}
              />
              <button
                onClick={addCustomInterest}
                className="px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700"
              >
                <Plus size={16} />
              </button>
            </div>
          </div>
          
          {careerInterests.length > 0 && (
            <div>
              <p className="text-sm font-medium text-gray-700 mb-2">Selected Interests:</p>
              <div className="flex flex-wrap gap-2">
                {careerInterests.map((interest) => (
                  <span
                    key={interest}
                    className="px-3 py-1.5 bg-purple-100 text-purple-700 rounded-full text-sm font-medium flex items-center"
                  >
                    {interest}
                    <button
                      onClick={() => removeCareerInterest(interest)}
                      className="ml-2 text-purple-600 hover:text-purple-800"
                    >
                      <X size={14} />
                    </button>
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Career Goals Section */}
        <div className="bg-gray-50 p-4 rounded-lg border border-gray-200">
          <h3 className="text-lg font-medium text-gray-800 mb-3 flex items-center">
            <Compass className="mr-2 h-5 w-5 text-purple-600" />
            Step 3: Define Your Career Goals
          </h3>
          
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Short-term Goals (1-2 years)
                </label>
                <input
                  type="text"
                  value={careerGoals.shortTerm}
                  onChange={(e) => setCareerGoals({...careerGoals, shortTerm: e.target.value})}
                  placeholder="e.g., Get promoted to Senior Developer"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Long-term Goals (5+ years)
                </label>
                <input
                  type="text"
                  value={careerGoals.longTerm}
                  onChange={(e) => setCareerGoals({...careerGoals, longTerm: e.target.value})}
                  placeholder="e.g., Become a Technical Director"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Desired Role/Position
                </label>
                <input
                  type="text"
                  value={careerGoals.desiredRole}
                  onChange={(e) => setCareerGoals({...careerGoals, desiredRole: e.target.value})}
                  placeholder="e.g., Solutions Architect"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Preferred Industry
                </label>
                <input
                  type="text"
                  value={careerGoals.industry}
                  onChange={(e) => setCareerGoals({...careerGoals, industry: e.target.value})}
                  placeholder="e.g., FinTech, Healthcare"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Work Priorities (select multiple)
              </label>
              <div className="flex flex-wrap gap-2">
                {workPriorities.map((priority) => (
                  <button
                    key={priority}
                    onClick={() => togglePriority(priority)}
                    className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                      careerGoals.priorities?.includes(priority)
                        ? 'bg-purple-600 text-white'
                        : 'bg-white border border-purple-300 text-purple-700 hover:bg-purple-50'
                    }`}
                  >
                    {priority}
                  </button>
                ))}
              </div>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Preferred Work Style
              </label>
              <select
                value={careerGoals.workStyle}
                onChange={(e) => setCareerGoals({...careerGoals, workStyle: e.target.value})}
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              >
                <option value="">Select work style</option>
                <option value="remote">Remote</option>
                <option value="hybrid">Hybrid</option>
                <option value="office">Office</option>
                <option value="flexible">Flexible</option>
              </select>
            </div>
          </div>
        </div>

        {/* Analyze Button */}
        <div className="flex justify-center">
          <button
            onClick={analyzeCareerPath}
            disabled={analyzing || !cvFile || careerInterests.length === 0}
            className="px-8 py-3 bg-purple-600 text-white rounded-md hover:bg-purple-700 transition disabled:bg-purple-300 flex items-center text-lg font-medium"
          >
            {analyzing ? (
              <>
                <Loader className="animate-spin mr-2 h-5 w-5" />
                Analyzing Your Career Path...
              </>
            ) : (
              <>
                <Brain className="mr-2 h-5 w-5" />
                Get Career Guidance
              </>
            )}
          </button>
        </div>

        {/* Analysis Results */}
        {careerAnalysis && (
          <div ref={resultsRef} className="mt-8 border-t pt-8">
            <h3 className="text-2xl font-bold text-gray-800 mb-6">
              Your Personalized Career Guidance
            </h3>
            
            {/* Navigation Tabs */}
            <div className="border-b border-gray-200 mb-6">
              <nav className="-mb-px flex space-x-8">
                <button
                  onClick={() => setActiveTab('overview')}
                  className={`pb-4 px-1 border-b-2 font-medium text-sm ${
                    activeTab === 'overview'
                      ? 'border-purple-500 text-purple-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  Overview
                </button>
                <button
                  onClick={() => setActiveTab('paths')}
                  className={`pb-4 px-1 border-b-2 font-medium text-sm ${
                    activeTab === 'paths'
                      ? 'border-purple-500 text-purple-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  Career Paths
                </button>
                <button
                  onClick={() => setActiveTab('skills')}
                  className={`pb-4 px-1 border-b-2 font-medium text-sm ${
                    activeTab === 'skills'
                      ? 'border-purple-500 text-purple-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  Skills Analysis
                </button>
                <button
                  onClick={() => setActiveTab('resources')}
                  className={`pb-4 px-1 border-b-2 font-medium text-sm ${
                    activeTab === 'resources'
                      ? 'border-purple-500 text-purple-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  Learning Resources
                </button>
              </nav>
            </div>
            
            {/* Tab Content */}
            {activeTab === 'overview' && (
              <div className="space-y-6">
                {/* Career Summary */}
                <div className="bg-purple-50 p-6 rounded-lg">
                  <h4 className="text-lg font-semibold text-gray-800 mb-3 flex items-center">
                    <Lightbulb className="mr-2 h-5 w-5 text-purple-600" />
                    Career Assessment Summary
                  </h4>
                  <p className="text-gray-700 mb-4">{careerAnalysis.summary}</p>
                  
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="bg-white p-4 rounded-lg shadow-sm">
                      <div className="text-purple-600 font-semibold mb-1">Current Level</div>
                      <div className="text-lg font-bold">{careerAnalysis.currentLevel}</div>
                    </div>
                    <div className="bg-white p-4 rounded-lg shadow-sm">
                      <div className="text-purple-600 font-semibold mb-1">Potential Growth</div>
                      <div className="text-lg font-bold">{careerAnalysis.growthPotential}</div>
                    </div>
                    <div className="bg-white p-4 rounded-lg shadow-sm">
                      <div className="text-purple-600 font-semibold mb-1">Market Demand</div>
                      <div className="text-lg font-bold">{careerAnalysis.marketDemand}</div>
                    </div>
                  </div>
                </div>
                
                {/* Key Strengths */}
                <div className="bg-green-50 p-6 rounded-lg">
                  <h4 className="text-lg font-semibold text-gray-800 mb-3 flex items-center">
                    <Trophy className="mr-2 h-5 w-5 text-green-600" />
                    Your Key Strengths
                  </h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {careerAnalysis.strengths?.map((strength, index) => (
                      <div key={index} className="flex items-start">
                        <CheckCircle className="mr-2 h-5 w-5 text-green-600 flex-shrink-0 mt-0.5" />
                        <div>
                          <div className="font-medium">{strength.title}</div>
                          <div className="text-sm text-gray-600">{strength.description}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                
                {/* Areas for Improvement */}
                <div className="bg-orange-50 p-6 rounded-lg">
                  <h4 className="text-lg font-semibold text-gray-800 mb-3 flex items-center">
                    <TrendingUp className="mr-2 h-5 w-5 text-orange-600" />
                    Areas for Development
                  </h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {careerAnalysis.improvements?.map((area, index) => (
                      <div key={index} className="flex items-start">
                        <AlertCircle className="mr-2 h-5 w-5 text-orange-600 flex-shrink-0 mt-0.5" />
                        <div>
                          <div className="font-medium">{area.title}</div>
                          <div className="text-sm text-gray-600">{area.description}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
            
            {activeTab === 'paths' && (
              <div className="space-y-6">
                {careerPaths.map((path, index) => (
                  <div key={index} className="border border-gray-200 rounded-lg p-6">
                    <div className="flex items-start justify-between mb-4">
                      <div>
                        <h4 className="text-xl font-semibold text-gray-800">{path.title}</h4>
                        <p className="text-gray-600 mt-1">{path.description}</p>
                      </div>
                      <div className={`px-3 py-1 rounded-full text-sm font-medium ${
                        path.fitScore >= 80 ? 'bg-green-100 text-green-800' :
                        path.fitScore >= 60 ? 'bg-yellow-100 text-yellow-800' :
                        'bg-red-100 text-red-800'
                      }`}>
                        {path.fitScore}% Match
                      </div>
                    </div>
                    
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div>
                        <h5 className="font-medium text-gray-700 mb-2">Why This Path Suits You:</h5>
                        <ul className="space-y-1">
                          {path.reasons?.map((reason, idx) => (
                            <li key={idx} className="flex items-start">
                              <CheckCircle className="mr-2 h-4 w-4 text-green-500 flex-shrink-0 mt-0.5" />
                              <span className="text-gray-600">{reason}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                      
                      <div>
                        <h5 className="font-medium text-gray-700 mb-2">Challenges to Consider:</h5>
                        <ul className="space-y-1">
                          {path.challenges?.map((challenge, idx) => (
                            <li key={idx} className="flex items-start">
                              <AlertCircle className="mr-2 h-4 w-4 text-orange-500 flex-shrink-0 mt-0.5" />
                              <span className="text-gray-600">{challenge}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    </div>
                    
                    <div className="mt-4">
                      <h5 className="font-medium text-gray-700 mb-2">Career Progression:</h5>
                      <div className="flex items-center space-x-2 mt-2">
                        {path.progression?.map((step, idx) => (
                          <React.Fragment key={idx}>
                            <div className="text-center">
                              <div className="bg-purple-100 text-purple-700 rounded-lg px-3 py-2 text-sm font-medium">
                                {step.role}
                              </div>
                              <div className="text-xs text-gray-500 mt-1">{step.years}</div>
                            </div>
                            {idx < path.progression.length - 1 && (
                              <ChevronRight className="h-4 w-4 text-gray-400" />
                            )}
                          </React.Fragment>
                        ))}
                      </div>
                    </div>
                    
                    <div className="mt-4 pt-4 border-t border-gray-200">
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div>
                          <span className="text-sm font-medium text-gray-600">Average Salary:</span>
                          <div className="text-lg font-semibold text-gray-900">{path.salary}</div>
                        </div>
                        <div>
                          <span className="text-sm font-medium text-gray-600">Job Growth:</span>
                          <div className="text-lg font-semibold text-gray-900">{path.growth}</div>
                        </div>
                        <div>
                          <span className="text-sm font-medium text-gray-600">Time to Transition:</span>
                          <div className="text-lg font-semibold text-gray-900">{path.timeToTransition}</div>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
            
            {activeTab === 'skills' && (
              <div className="space-y-6">
                {/* Current Skills */}
                <div className="bg-white border border-gray-200 rounded-lg p-6">
                  <h4 className="text-lg font-semibold text-gray-800 mb-4 flex items-center">
                    <Award className="mr-2 h-5 w-5 text-purple-600" />
                    Your Current Skills
                  </h4>
                  <div className="space-y-4">
                    {careerAnalysis.currentSkills?.map((skill, index) => (
                      <div key={index} className="flex items-center justify-between">
                        <span className="font-medium text-gray-700">{skill.name}</span>
                        <div className="flex items-center space-x-2">
                          {renderSkillLevel(skill.level)}
                          <span className="text-sm text-gray-500">{skill.level}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                
                {/* Skills Gap Analysis */}
                <div className="bg-white border border-gray-200 rounded-lg p-6">
                  <h4 className="text-lg font-semibold text-gray-800 mb-4 flex items-center">
                    <BarChart3 className="mr-2 h-5 w-5 text-orange-600" />
                    Skills Gap Analysis
                  </h4>
                  <div className="space-y-6">
                    {skillGaps.map((gap, index) => (
                      <div key={index} className="border-b border-gray-200 pb-4 last:border-0">
                        <div className="flex justify-between items-center mb-2">
                          <h5 className="font-medium text-gray-800">{gap.skill}</h5>
                          <span className={`px-2 py-1 rounded text-sm ${
                            gap.priority === 'High' ? 'bg-red-100 text-red-700' :
                            gap.priority === 'Medium' ? 'bg-yellow-100 text-yellow-700' :
                            'bg-green-100 text-green-700'
                          }`}>
                            {gap.priority} Priority
                          </span>
                        </div>
                        <div className="flex items-center space-x-4 mb-2">
                          <div className="flex-1">
                            <div className="flex justify-between text-sm mb-1">
                              <span>Current</span>
                              <span>Required</span>
                            </div>
                            <div className="h-2 bg-gray-200 rounded-full relative">
                              <div 
                                className="absolute h-2 bg-purple-500 rounded-full"
                                style={{ width: `${gap.currentLevel * 20}%` }}
                              ></div>
                              <div 
                                className="absolute h-2 border-2 border-purple-700 rounded-full"
                                style={{ width: `${gap.requiredLevel * 20}%`, background: 'transparent' }}
                              ></div>
                            </div>
                          </div>
                        </div>
                        <p className="text-sm text-gray-600 mb-2">{gap.importance}</p>
                        <div className="text-sm text-purple-600">
                          Recommended Learning: {gap.learningPath}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                
                {/* Future Skills */}
                <div className="bg-white border border-gray-200 rounded-lg p-6">
                  <h4 className="text-lg font-semibold text-gray-800 mb-4 flex items-center">
                    <Rocket className="mr-2 h-5 w-5 text-blue-600" />
                    Future Skills to Develop
                  </h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {careerAnalysis.futureSkills?.map((skill, index) => (
                      <div key={index} className="flex items-start p-3 bg-blue-50 rounded-lg">
                        <TrendingUp className="mr-2 h-5 w-5 text-blue-600 flex-shrink-0 mt-0.5" />
                        <div>
                          <div className="font-medium text-gray-800">{skill.name}</div>
                          <div className="text-sm text-gray-600">{skill.reason}</div>
                          <div className="text-xs text-blue-600 mt-1">
                            Market Demand: {skill.marketDemand}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
            
            {activeTab === 'resources' && (
              <div className="space-y-6">
                {/* Learning Paths */}
                <div className="bg-white border border-gray-200 rounded-lg p-6">
                  <h4 className="text-lg font-semibold text-gray-800 mb-4 flex items-center">
                    <BookOpen className="mr-2 h-5 w-5 text-green-600" />
                    Recommended Learning Paths
                  </h4>
                  <div className="space-y-4">
                    {learningResources.paths?.map((path, index) => (
                      <div key={index} className="border border-gray-200 rounded-lg p-4">
                        <div className="flex justify-between items-start mb-2">
                          <div>
                            <h5 className="font-medium text-gray-800">{path.title}</h5>
                            <p className="text-sm text-gray-600">{path.description}</p>
                          </div>
                          <span className="px-2 py-1 bg-green-100 text-green-700 rounded text-sm">
                            {path.duration}
                          </span>
                        </div>
                        <div className="mt-3">
                          <div className="text-sm font-medium text-gray-700 mb-2">Key Topics:</div>
                          <div className="flex flex-wrap gap-2">
                            {path.topics?.map((topic, idx) => (
                              <span key={idx} className="px-2 py-1 bg-gray-100 text-gray-700 rounded text-sm">
                                {topic}
                              </span>
                            ))}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                
                {/* Courses */}
                <div className="bg-white border border-gray-200 rounded-lg p-6">
                  <h4 className="text-lg font-semibold text-gray-800 mb-4 flex items-center">
                    <GraduationCap className="mr-2 h-5 w-5 text-purple-600" />
                    Recommended Courses
                  </h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {learningResources.courses?.map((course, index) => (
                      <div key={index} className="border border-gray-200 rounded-lg p-4">
                        <h5 className="font-medium text-gray-800 mb-1">{course.title}</h5>
                        <div className="flex items-center text-sm text-gray-600 mb-2">
                          <Users className="mr-1 h-4 w-4" />
                          {course.provider}
                        </div>
                        <div className="flex justify-between items-center">
                          <span className="text-sm text-gray-600">{course.duration}</span>
                          <span className={`px-2 py-1 rounded text-sm ${
                            course.level === 'Beginner' ? 'bg-green-100 text-green-700' :
                            course.level === 'Intermediate' ? 'bg-yellow-100 text-yellow-700' :
                            'bg-red-100 text-red-700'
                          }`}>
                            {course.level}
                          </span>
                        </div>
                        {course.price && (
                          <div className="mt-2 text-sm font-medium text-purple-600">
                            {course.price}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
                
                {/* Certifications */}
                <div className="bg-white border border-gray-200 rounded-lg p-6">
                  <h4 className="text-lg font-semibold text-gray-800 mb-4 flex items-center">
                    <Award className="mr-2 h-5 w-5 text-yellow-600" />
                    Professional Certifications
                  </h4>
                  <div className="space-y-4">
                    {learningResources.certifications?.map((cert, index) => (
                      <div key={index} className="flex items-start p-4 border border-gray-200 rounded-lg">
                        <Star className="mr-3 h-5 w-5 text-yellow-500 flex-shrink-0 mt-0.5" />
                        <div className="flex-1">
                          <h5 className="font-medium text-gray-800">{cert.name}</h5>
                          <p className="text-sm text-gray-600 mt-1">{cert.description}</p>
                          <div className="flex items-center mt-2 text-sm text-gray-500">
                            <span>Provider: {cert.provider}</span>
                            <span className="mx-2">•</span>
                            <span>Duration: {cert.duration}</span>
                            {cert.cost && (
                              <>
                                <span className="mx-2">•</span>
                                <span>Cost: {cert.cost}</span>
                              </>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
            
            {/* Action Plan */}
            <div className="mt-8 bg-gradient-to-r from-purple-600 to-blue-600 rounded-lg p-6 text-white">
              <h4 className="text-xl font-semibold mb-4 flex items-center">
                <Map className="mr-2 h-6 w-6" />
                Your Career Action Plan
              </h4>
              <div className="space-y-4">
                {careerAnalysis.actionPlan?.map((step, index) => (
                  <div key={index} className="flex items-start">
                    <div className="flex-shrink-0 w-8 h-8 bg-white/20 rounded-full flex items-center justify-center font-bold">
                      {index + 1}
                    </div>
                    <div className="ml-4">
                      <h5 className="font-semibold">{step.title}</h5>
                      <p className="text-white/80 text-sm mt-1">{step.description}</p>
                      <div className="text-white/60 text-xs mt-1">Timeline: {step.timeline}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            
            {/* Download Report Button */}
            <div className="mt-8 text-center">
              <button
                onClick={() => {/* Implement download functionality */}}
                className="px-6 py-3 bg-purple-600 text-white rounded-md hover:bg-purple-700 transition flex items-center mx-auto"
              >
                <ArrowRight className="mr-2 h-5 w-5" />
                Download Full Career Report
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}