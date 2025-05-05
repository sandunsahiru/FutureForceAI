"use client";
import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { 
  FileText, 
  Upload, 
  Download, 
  Target, 
  CheckCircle, 
  XCircle, 
  AlertTriangle,
  Trash2,
  RefreshCw,
  Search,
  BarChart,
  BookOpenCheck,
  Zap,
  Shield,
  ArrowRight,
  FileCheck,
  Loader,
  AlertCircle
} from "lucide-react";

export default function ResumeAnalyzer() {
  // State management
  const [resumeFile, setResumeFile] = useState(null);
  const [targetRole, setTargetRole] = useState("");
  const [savedResumes, setSavedResumes] = useState([]);
  const [showResumeSelector, setShowResumeSelector] = useState(false);
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [analysisResults, setAnalysisResults] = useState(null);
  const [suggestedRoles, setSuggestedRoles] = useState([]);
  const [optimizing, setOptimizing] = useState(false);
  const [optimizedResume, setOptimizedResume] = useState(null);
  
  // Refs
  const resultsRef = useRef(null);
  const router = useRouter();

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
        
        // Fetch user's saved resumes
        fetchSavedResumes();
      } catch (err) {
        console.error("Error checking authentication:", err);
        router.push("/login");
      }
    };
    
    checkAuth();
  }, [router]);

  // Fetch user's saved resumes from the server
  const fetchSavedResumes = async () => {
    try {
      setLoading(true);
      const response = await fetch("/api/user/resumes", {
        credentials: "include"
      });
      
      if (response.ok) {
        const data = await response.json();
        setSavedResumes(data.resumes || []);
      }
    } catch (err) {
      console.error("Error fetching saved resumes:", err);
    } finally {
      setLoading(false);
    }
  };

  // Handle file upload
  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      // Validate file type
      const validTypes = ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
      if (!validTypes.includes(file.type)) {
        setError("Please select a PDF or Word document (.pdf, .doc, .docx)");
        setTimeout(() => setError(null), 5000);
        return;
      }
      
      // Validate file size (10MB max)
      if (file.size > 10 * 1024 * 1024) {
        setError("File size exceeds the maximum limit of 10MB");
        setTimeout(() => setError(null), 5000);
        return;
      }
      
      setResumeFile(file);
      // After file selection, suggest roles based on resume
      suggestRolesFromResume(file);
    }
  };

  // Suggest roles based on resume content
  const suggestRolesFromResume = async (resume) => {
    try {
      setAnalyzing(true);
      setSuggestedRoles([]);
      setError(null);
      
      let requestData;
      let url;
      
      if (resume.useSaved) {
        // If using a saved resume
        url = "/api/resume/suggest-roles";
        requestData = {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({ resume_id: resume.id }),
          credentials: "include"
        };
      } else {
        // If uploading a new resume file
        url = "/api/resume/suggest-roles-upload";
        const formData = new FormData();
        formData.append("resume_file", resume);
        
        requestData = {
          method: "POST",
          body: formData,
          credentials: "include"
        };
      }
      
      const response = await fetch(url, requestData);
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || errorData.detail || "Failed to analyze resume");
      }
      
      const data = await response.json();
      setSuggestedRoles(data.suggested_roles || []);
      
      if (data.resume_id && !resume.useSaved) {
        // Update the resume file object with the saved ID
        setResumeFile({
          ...resume,
          id: data.resume_id,
          useSaved: true
        });
      }
    } catch (err) {
      console.error("Error analyzing resume:", err);
      setError(`Error analyzing your resume: ${err.message}`);
      setTimeout(() => setError(null), 5000);
    } finally {
      setAnalyzing(false);
    }
  };

  // Handle selecting a saved resume
  const handleSelectResume = (resume) => {
    setShowResumeSelector(false);
    
    const savedResume = {
      ...resume,
      name: resume.filename || resume.originalName,
      useSaved: true,
      id: resume.id
    };
    
    setResumeFile(savedResume);
    suggestRolesFromResume(savedResume);
  };

  // Delete a saved resume
  const handleDeleteResume = async (resumeId, e) => {
    // Prevent the click from triggering the parent button
    if (e) {
      e.stopPropagation();
    }
    
    if (!confirm("Are you sure you want to delete this resume?")) {
      return;
    }
    
    try {
      setLoading(true);
      
      const response = await fetch(`/api/user/resumes/${resumeId}`, {
        method: "DELETE",
        credentials: "include"
      });
      
      if (response.ok) {
        // If the deleted resume is the currently selected one, clear it
        if (resumeFile && resumeFile.id === resumeId) {
          setResumeFile(null);
          setSuggestedRoles([]);
          setAnalysisResults(null);
        }
        
        // Refresh the resume list
        fetchSavedResumes();
        
        setSuccess("Resume deleted successfully");
        setTimeout(() => setSuccess(null), 3000);
      } else {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to delete resume");
      }
    } catch (err) {
      console.error("Error deleting resume:", err);
      setError("Error deleting resume. Please try again.");
      setTimeout(() => setError(null), 5000);
    } finally {
      setLoading(false);
    }
  };

  // Analyze resume against ATS requirements
  const analyzeResume = async (role = targetRole) => {
    if (!resumeFile) {
      setError("Please upload or select a resume first");
      setTimeout(() => setError(null), 3000);
      return;
    }
    
    if (!role) {
      setError("Please enter a target job role");
      setTimeout(() => setError(null), 3000);
      return;
    }
    
    try {
      setLoading(true);
      setAnalysisResults(null);
      setOptimizedResume(null);
      
      // Set the input field to the selected role if it's different
      if (role !== targetRole) {
        setTargetRole(role);
      }
      
      const requestBody = {
        target_role: role,
        resume_id: resumeFile && resumeFile.useSaved ? resumeFile.id : null
      };
      
      // If uploading a new resume file
      if (!resumeFile.useSaved) {
        const formData = new FormData();
        formData.append("resume_file", resumeFile);
        formData.append("target_role", role);
        
        const response = await fetch("/api/resume/analyze-upload", {
          method: "POST",
          body: formData,
          credentials: "include"
        });
        
        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || "Failed to analyze resume");
        }
        
        const data = await response.json();
        setAnalysisResults(data);
      } else {
        // If using a saved resume
        const response = await fetch("/api/resume/analyze", {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify(requestBody),
          credentials: "include"
        });
        
        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || "Failed to analyze resume");
        }
        
        const data = await response.json();
        setAnalysisResults(data);
      }
      
      // Scroll to results
      if (resultsRef.current) {
        resultsRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    } catch (err) {
      console.error("Error analyzing resume:", err);
      setError(err.message || "Error analyzing resume. Please try again.");
      setTimeout(() => setError(null), 3000);
    } finally {
      setLoading(false);
    }
  };

  // Optimize resume based on analysis
  const optimizeResume = async () => {
    if (!analysisResults) return;
    
    try {
      setOptimizing(true);
      
      const response = await fetch("/api/resume/optimize", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          resume_id: resumeFile.id,
          target_role: targetRole,
          analysis: analysisResults
        }),
        credentials: "include"
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to optimize resume");
      }
      
      const data = await response.json();
      setOptimizedResume(data);
      
      setSuccess("Resume optimized successfully!");
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      console.error("Error optimizing resume:", err);
      setError("Error optimizing resume. Please try again.");
      setTimeout(() => setError(null), 3000);
    } finally {
      setOptimizing(false);
    }
  };

  // Download optimized resume
  const downloadOptimizedResume = async () => {
    if (!optimizedResume) return;
    
    try {
      const response = await fetch("/api/resume/download-optimized", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          optimized_id: optimizedResume.id
        }),
        credentials: "include"
      });
      
      if (!response.ok) {
        throw new Error("Failed to download optimized resume");
      }
      
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${targetRole.replace(/\s+/g, '_')}_Optimized_Resume.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      
      setSuccess("Optimized resume downloaded successfully");
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      console.error("Error downloading resume:", err);
      setError("Error downloading resume. Please try again.");
      setTimeout(() => setError(null), 3000);
    }
  };

  // Render ATS score with visual indicator
  const renderATSScore = (score) => {
    let color = "red";
    let bgColor = "bg-red-100";
    let borderColor = "border-red-300";
    let textColor = "text-red-700";
    
    if (score >= 80) {
      color = "green";
      bgColor = "bg-green-100";
      borderColor = "border-green-300";
      textColor = "text-green-700";
    } else if (score >= 60) {
      color = "yellow";
      bgColor = "bg-yellow-100";
      borderColor = "border-yellow-300";
      textColor = "text-yellow-700";
    }
    
    return (
      <div className={`${bgColor} ${borderColor} ${textColor} border-2 rounded-lg p-4 text-center`}>
        <div className="text-3xl font-bold mb-1">{score}%</div>
        <div className="text-sm">ATS Compatibility Score</div>
      </div>
    );
  };

  // If not authenticated yet, show loading
  if (!isAuthenticated && !error) {
    return (
      <div className="p-6 bg-white rounded-xl shadow-md">
        <h2 className="text-2xl font-bold text-purple-700 mb-4">
          ATS Resume Analyzer
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
        ATS Resume Analyzer
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
      
      <div className="space-y-6">
        {/* Resume Selection Section */}
        <div className="bg-gray-50 p-4 rounded-lg border border-gray-200">
          <h3 className="text-lg font-medium text-gray-800 mb-3 flex items-center">
            <FileText className="mr-2 h-5 w-5 text-purple-600" />
            Your Resume
          </h3>
          
          {resumeFile ? (
            <div className="flex items-center p-3 border rounded bg-purple-50">
              <div className="flex-1">
                <p className="font-medium text-gray-800">{resumeFile.name}</p>
                <p className="text-sm text-gray-600">
                  {resumeFile.size ? `${Math.round(resumeFile.size / 1024)} KB` : ""}
                </p>
              </div>
              <button
                onClick={() => {
                  setResumeFile(null);
                  setSuggestedRoles([]);
                  setAnalysisResults(null);
                  setOptimizedResume(null);
                }}
                className="text-red-500 hover:text-red-700"
                title="Remove Resume"
              >
                <Trash2 size={18} />
              </button>
            </div>
          ) : (
            <div className="flex gap-3">
              <button
                onClick={() => setShowResumeSelector(!showResumeSelector)}
                className="flex-1 px-4 py-2 border border-purple-300 rounded text-purple-700 hover:bg-purple-50 transition flex items-center justify-center"
              >
                <FileText size={16} className="mr-2" /> 
                Select Saved Resume
              </button>
              <label className="flex-1 px-4 py-2 bg-purple-600 text-white rounded hover:bg-purple-700 transition cursor-pointer flex items-center justify-center">
                <Upload size={16} className="mr-2" /> 
                Upload New Resume
                <input
                  type="file"
                  accept=".pdf,.doc,.docx"
                  onChange={handleFileChange}
                  className="hidden"
                />
              </label>
            </div>
          )}
          
          {/* Saved Resumes Selector */}
          {showResumeSelector && (
            <div className="mt-3 border rounded p-3 bg-white shadow-md">
              <h4 className="font-medium text-gray-800 mb-2">Your Saved Resumes</h4>
              
              {loading ? (
                <div className="py-8 flex justify-center items-center">
                  <div className="animate-spin rounded-full h-6 w-6 border-2 border-purple-500 border-t-transparent"></div>
                </div>
              ) : savedResumes.length === 0 ? (
                <div className="text-center py-4">
                  <FileText className="mx-auto h-10 w-10 text-gray-300 mb-2" />
                  <p className="text-gray-500">No saved resumes found. Upload a new one.</p>
                </div>
              ) : (
                <ul className="divide-y">
                  {savedResumes.map((resume) => (
                    <li key={resume.id} className="py-2">
                      <button 
                        onClick={() => handleSelectResume(resume)}
                        className="w-full text-left hover:bg-purple-50 p-2 rounded flex items-center justify-between"
                      >
                        <div>
                          <div className="font-medium text-gray-800">{resume.filename}</div>
                          <div className="text-sm text-gray-600">
                            {new Date(resume.uploadedAt).toLocaleDateString()} • {Math.round(resume.size/1024)} KB
                          </div>
                        </div>
                        <button
                          onClick={(e) => handleDeleteResume(resume.id, e)}
                          className="text-red-500 hover:text-red-700"
                          title="Delete Resume"
                        >
                          <Trash2 size={16} />
                        </button>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
        
        {/* Suggested Roles Section */}
        {analyzing ? (
          <div className="bg-blue-50 p-4 rounded-lg border border-blue-200 flex items-center justify-center space-x-3">
            <div className="animate-spin rounded-full h-5 w-5 border-2 border-blue-500 border-t-transparent"></div>
            <p className="text-blue-700">Analyzing your resume to suggest relevant job roles...</p>
          </div>
        ) : suggestedRoles.length > 0 ? (
          <div className="bg-blue-50 p-4 rounded-lg border border-blue-200">
            <h3 className="text-lg font-medium text-gray-800 mb-3 flex items-center">
              <Zap className="mr-2 h-5 w-5 text-blue-600" />
              Suggested Target Roles Based on Your Resume
            </h3>
            <div className="flex flex-wrap gap-2 mt-2">
              {suggestedRoles.map((role, index) => (
                <button
                  key={index}
                  onClick={() => analyzeResume(role)}
                  className="bg-white border border-blue-300 text-blue-700 px-3 py-1.5 rounded-full text-sm font-medium hover:bg-blue-700 hover:text-white transition-colors flex items-center"
                >
                  <Target className="mr-1.5 h-4 w-4" />
                  {role}
                </button>
              ))}
            </div>
          </div>
        ) : null}
        
        {/* Target Role Input Section */}
        <div className="space-y-4">
          <div className="flex space-x-2">
            <div className="flex-1 relative">
              <input
                type="text"
                value={targetRole}
                onChange={(e) => setTargetRole(e.target.value)}
                placeholder="Enter target job role (e.g., Software Engineer, Data Scientist)"
                className="w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              />
              <Target className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
            </div>
            <button
              onClick={() => analyzeResume()}
              disabled={loading || !targetRole || !resumeFile}
              className="px-4 py-2.5 bg-purple-600 text-white rounded-md hover:bg-purple-700 transition disabled:bg-purple-300 flex items-center"
            >
              {loading ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent mr-2"></div>
                  Analyzing...
                </>
              ) : (
                <>
                  <Search className="mr-1.5 h-5 w-5" />
                  Analyze
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Analysis Results */}
      {analysisResults && (
        <div ref={resultsRef} className="mt-8 border-t pt-6">
          <div className="flex justify-between items-center mb-6">
            <h3 className="text-xl font-bold text-gray-800">
              Analysis Results for {targetRole}
            </h3>
            {!optimizedResume && (
              <button
                onClick={optimizeResume}
                disabled={optimizing}
                className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition disabled:bg-green-400 flex items-center text-sm"
              >
                {optimizing ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent mr-1.5"></div>
                    Optimizing...
                  </>
                ) : (
                  <>
                    <Zap className="mr-1.5 h-4 w-4" />
                    Optimize Resume
                  </>
                )}
              </button>
            )}
          </div>
          
          {/* ATS Score */}
          <div className="mb-6">
            {renderATSScore(analysisResults.ats_score)}
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Keywords Analysis */}
            <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
              <h4 className="font-bold text-gray-800 mb-3 flex items-center">
                <FileCheck className="mr-2 h-5 w-5 text-purple-600" />
                Keyword Analysis
              </h4>
              <div className="space-y-3">
                <div>
                  <h5 className="font-medium text-green-700 mb-2">Found Keywords:</h5>
                  <div className="flex flex-wrap gap-2">
                    {analysisResults.keywords?.found?.map((keyword, index) => (
                      <span key={index} className="bg-green-100 text-green-800 text-xs font-medium px-2.5 py-1 rounded flex items-center">
                        <CheckCircle className="mr-1 h-3 w-3" />
                        {keyword}
                      </span>
                    ))}
                  </div>
                </div>
                <div>
                  <h5 className="font-medium text-red-700 mb-2">Missing Keywords:</h5>
                  <div className="flex flex-wrap gap-2">
                    {analysisResults.keywords?.missing?.map((keyword, index) => (
                      <span key={index} className="bg-red-100 text-red-800 text-xs font-medium px-2.5 py-1 rounded flex items-center">
                        <XCircle className="mr-1 h-3 w-3" />
                        {keyword}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>
            
            {/* Format Issues */}
            {analysisResults.format_issues && analysisResults.format_issues.length > 0 && (
              <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
                <h4 className="font-bold text-gray-800 mb-3 flex items-center">
                  <AlertTriangle className="mr-2 h-5 w-5 text-yellow-600" />
                  Format Issues
                </h4>
                <ul className="space-y-2">
                  {analysisResults.format_issues.map((issue, index) => (
                    <li key={index} className="flex items-start">
                      <div className="min-w-4 h-4 mt-1 mr-2 bg-yellow-200 rounded-full flex items-center justify-center text-xs text-yellow-700">!</div>
                      <span className="text-gray-700">{issue}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            
            {/* Recommendations */}
            <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm md:col-span-2">
              <h4 className="font-bold text-gray-800 mb-3 flex items-center">
                <BookOpenCheck className="mr-2 h-5 w-5 text-blue-600" />
                Optimization Recommendations
              </h4>
              <ul className="space-y-2">
                {analysisResults.recommendations?.map((recommendation, index) => (
                  <li key={index} className="flex items-start">
                    <ArrowRight className="min-w-5 h-5 mt-0.5 mr-2 text-blue-500" />
                    <span className="text-gray-700">{recommendation}</span>
                  </li>
                ))}
              </ul>
            </div>
            
            {/* Section Analysis */}
            {analysisResults.sections && (
              <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm md:col-span-2">
                <h4 className="font-bold text-gray-800 mb-3 flex items-center">
                  <BarChart className="mr-2 h-5 w-5 text-indigo-600" />
                  Section Analysis
                </h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {Object.entries(analysisResults.sections).map(([section, status]) => (
                    <div key={section} className="flex items-center justify-between p-2 bg-gray-50 rounded">
                      <span className="font-medium capitalize">{section}</span>
                      {status ? (
                        <span className="flex items-center text-green-600">
                          <CheckCircle className="h-4 w-4 mr-1" />
                          Present
                        </span>
                      ) : (
                        <span className="flex items-center text-red-600">
                          <XCircle className="h-4 w-4 mr-1" />
                          Missing
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
          
          {/* Optimized Resume Section */}
          {optimizedResume && (
            <div className="mt-8 bg-green-50 border border-green-200 rounded-lg p-6">
              <h4 className="font-bold text-gray-800 mb-3 flex items-center">
                <Shield className="mr-2 h-5 w-5 text-green-600" />
                Optimized Resume Ready
              </h4>
              <p className="text-gray-700 mb-4">
                Your resume has been optimized for the {targetRole} position. The ATS score has improved to <strong>{optimizedResume.ats_score}%</strong>.
              </p>
              <div className="flex gap-3">
                <button
                  onClick={downloadOptimizedResume}
                  className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition flex items-center"
                >
                  <Download className="mr-1.5 h-4 w-4" />
                  Download Optimized Resume
                </button>
                <button
                  onClick={() => {
                    setOptimizedResume(null);
                    // Re-analyze with the optimized resume
                    analyzeResume();
                  }}
                  className="px-4 py-2 border border-green-600 text-green-700 rounded-md hover:bg-green-50 transition flex items-center"
                >
                  <RefreshCw className="mr-1.5 h-4 w-4" />
                  Re-analyze
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}