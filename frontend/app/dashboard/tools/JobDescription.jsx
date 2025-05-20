"use client";
import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { 
  Search, 
  Upload, 
  Download, 
  Briefcase, 
  FileText, 
  Book, 
  Code, 
  DollarSign, 
  Award, 
  Zap, 
  Trash2, 
  Clipboard, 
  BarChart2,
  AlertCircle,
  CheckCircle,
  Loader
} from "lucide-react";

export default function JobDescription() {
  // State management
  const [cvFile, setCvFile] = useState(null);
  const [jobRole, setJobRole] = useState("");
  const [suggestedRoles, setSuggestedRoles] = useState([]);
  const [savedCVs, setSavedCVs] = useState([]);
  const [showCVSelector, setShowCVSelector] = useState(false);
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [jobData, setJobData] = useState(null);
  const [searchHistory, setSearchHistory] = useState([]);
  const [pdfGenerating, setPdfGenerating] = useState(false);

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
        
        // Fetch user's saved CVs
        fetchSavedCVs();
        
        // Fetch search history
        fetchSearchHistory();
      } catch (err) {
        console.error("Error checking authentication:", err);
        router.push("/login");
      }
    };
    
    checkAuth();
  }, [router]);

  // Fetch user's saved CVs from the server
  const fetchSavedCVs = async () => {
    try {
      setLoading(true);
      const response = await fetch("/api/user/cvs", {
        credentials: "include"
      });
      
      if (response.ok) {
        const data = await response.json();
        setSavedCVs(data.cvs || []);
        
        // If user has CVs, automatically select the most recent one
        if (data.cvs && data.cvs.length > 0) {
          // Sort by date and get the most recent
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

  // Fetch search history
  const fetchSearchHistory = async () => {
    try {
      const response = await fetch("/api/job-description/history", {
        credentials: "include"
      });
      
      if (response.ok) {
        const data = await response.json();
        setSearchHistory(data.history || []);
      }
    } catch (err) {
      console.error("Error fetching search history:", err);
    }
  };

  // Handle file upload
  // Update these functions in JobDescription.jsx

const handleFileChange = (e) => {
  const file = e.target.files[0];
  if (file) {
    console.log("Selected file:", file.name, file.type, file.size);
    
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
    
    setCvFile(file);
    // After file selection, analyze CV to suggest roles
    analyzeCVForRoles(file);
  }
};

const analyzeCVForRoles = async (cv) => {
  try {
    setAnalyzing(true);
    setSuggestedRoles([]);
    setError(null);
    
    // Prepare request data based on whether it's a file or saved CV
    let requestData;
    let url;
    
    if (cv.useSaved) {
      // If using a saved CV
      url = "/api/job-description/suggest-roles";
      requestData = {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ cv_id: cv.id }),
        credentials: "include"
      };
    } else {
      // If uploading a new CV file
      url = "/api/job-description/suggest-roles-upload";
      const formData = new FormData();
      
      // Add browser fingerprinting data to help avoid bot detection
      const browserInfo = {
        screenWidth: window.screen.width,
        screenHeight: window.screen.height,
        colorDepth: window.screen.colorDepth,
        pixelRatio: window.devicePixelRatio,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        platform: navigator.platform,
        language: navigator.language,
        languages: navigator.languages?.join(','),
        doNotTrack: navigator.doNotTrack,
        cookiesEnabled: navigator.cookieEnabled,
        webdriver: navigator.webdriver || false,
        plugins: Array.from(navigator.plugins || []).map(p => p.name).join(','),
        timestamp: new Date().getTime()
      };
      
      // Ensure we're appending with the correct field name
      formData.append("cv_file", cv);
      formData.append("browser_info", JSON.stringify(browserInfo));
      
      requestData = {
        method: "POST",
        // Don't set Content-Type header when sending FormData
        body: formData,
        credentials: "include"
      };
    }
    
    console.log("Sending request to:", url);
    console.log("CV object:", cv.useSaved ? "Using saved CV" : {
      name: cv.name,
      type: cv.type,
      size: cv.size,
      lastModified: cv.lastModified
    });
    
    // Add a loading indicator
    setError("Analyzing your CV...");
    
    // Send request to get role suggestions
    const response = await fetch(url, requestData);
    
    // Log response status for debugging
    console.log("Response status:", response.status);
    
    // Clear the loading message
    setError(null);
    
    // Get the response data
    const responseData = await response.json();
    console.log("Response data:", responseData);
    
    // Check for CAPTCHA challenge response
    if (responseData.captcha_required) {
      console.log("CAPTCHA required, handling automatically...");
      setError("Verifying your request, please wait...");
      
      // The API route should have already attempted to solve the CAPTCHA
      // If we still get a CAPTCHA required response, that means it failed
      // Let's retry the request once more after a delay
      
      setTimeout(async () => {
        try {
          // Retry the request
          const retryResponse = await fetch(url, requestData);
          
          if (!retryResponse.ok) {
            const retryData = await retryResponse.json();
            throw new Error(retryData.error || retryData.detail || "Failed to analyze CV");
          }
          
          const finalData = await retryResponse.json();
          setSuggestedRoles(finalData.suggested_roles || []);
          
          if (finalData.cv_id && !cv.useSaved) {
            // Update the CV file object with the saved ID
            setCvFile({
              ...cv,
              id: finalData.cv_id,
              useSaved: true
            });
          }
          
          setError(null);
        } catch (retryErr) {
          console.error("Error retrying after CAPTCHA:", retryErr);
          setError("Verification failed. Please try again later.");
          setTimeout(() => setError(null), 5000);
        } finally {
          setAnalyzing(false);
        }
      }, 3000);
      
      return;
    }
    
    if (!response.ok) {
      // Handle error response
      const errorMsg = responseData.error || responseData.detail || "Failed to analyze CV";
      console.error("Error response:", errorMsg);
      throw new Error(errorMsg);
    }
    
    console.log("Received data:", responseData);
    setSuggestedRoles(responseData.suggested_roles || []);
    
    if (responseData.cv_id && !cv.useSaved) {
      // Update the CV file object with the saved ID
      setCvFile({
        ...cv,
        id: responseData.cv_id,
        useSaved: true
      });
    }
  } catch (err) {
    console.error("Error analyzing CV:", err);
    setError(`Error analyzing your CV: ${err.message || "Please try again with a different file format (PDF or DOCX recommended)"}.`);
    setTimeout(() => setError(null), 5000);
  } finally {
    setAnalyzing(false);
  }
};

const handleSelectCV = (cv) => {
  try {
    // Close the CV selector
    setShowCVSelector(false);
    
    // Create a file-like object with the saved CV's data
    const savedCv = {
      ...cv,
      name: cv.filename || cv.originalName,
      useSaved: true,
      id: cv.id
    };
    
    // Set it as the current CV
    setCvFile(savedCv);
    
    // Analyze the CV to get role suggestions
    analyzeCVForRoles(savedCv);
    
    console.log("Selected saved CV:", savedCv.name);
  } catch (err) {
    console.error("Error selecting CV:", err);
    setError("Error selecting CV. Please try again.");
    setTimeout(() => setError(null), 5000);
  }
};

const handleDeleteCV = async (cvId, e) => {
  // Prevent the click from triggering the parent button
  if (e) {
    e.stopPropagation();
  }
  
  if (!confirm("Are you sure you want to delete this CV?")) {
    return;
  }
  
  try {
    setLoading(true);
    
    const response = await fetch(`/api/user/cvs/${cvId}`, {
      method: "DELETE",
      credentials: "include"
    });
    
    if (response.ok) {
      // If the deleted CV is the currently selected one, clear it
      if (cvFile && cvFile.id === cvId) {
        setCvFile(null);
        setSuggestedRoles([]);
      }
      
      // Refresh the CV list
      fetchSavedCVs();
      
      setSuccess("CV deleted successfully");
      setTimeout(() => setSuccess(null), 3000);
    } else {
      const errorData = await response.json();
      throw new Error(errorData.detail || "Failed to delete CV");
    }
  } catch (err) {
    console.error("Error deleting CV:", err);
    setError("Error deleting CV. Please try again.");
    setTimeout(() => setError(null), 5000);
  } finally {
    setLoading(false);
  }
};

// Add this function to the component for handling the job search
const handleSearchJob = async (role) => {
  if (!isAuthenticated) {
    setError("Please log in to use this feature.");
    setTimeout(() => setError(null), 3000);
    return;
  }
  
  if (!role) {
    setError("Please enter a job role to search.");
    setTimeout(() => setError(null), 3000);
    return;
  }
  
  try {
    setLoading(true);
    setJobData(null);
    setError(null);
    
    // Set the input field to the selected role if it's different
    if (role !== jobRole) {
      setJobRole(role);
    }
    
    // Add browser fingerprinting data to help avoid bot detection
    const browserInfo = {
      screenWidth: window.screen.width,
      screenHeight: window.screen.height,
      colorDepth: window.screen.colorDepth,
      pixelRatio: window.devicePixelRatio,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      platform: navigator.platform,
      language: navigator.language,
      languages: navigator.languages?.join(','),
      doNotTrack: navigator.doNotTrack,
      cookiesEnabled: navigator.cookieEnabled,
      webdriver: navigator.webdriver || false,
      plugins: Array.from(navigator.plugins || []).map(p => p.name).join(','),
      timestamp: new Date().getTime()
    };
    
    const requestBody = {
      job_role: role,
      cv_id: cvFile && cvFile.useSaved ? cvFile.id : null,
      browser_info: browserInfo
    };
    
    console.log("Sending research request with:", requestBody);
    
    let response = await fetch("/api/job-description/research", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      credentials: "include",
      body: JSON.stringify(requestBody)
    });
    
    // Check if we got a CAPTCHA challenge
    if (response.status === 403) {
      const responseData = await response.json();
      
      if (responseData.captcha_required) {
        setError("CAPTCHA verification required. Solving automatically...");
        
        // Get the site key from the response
        const siteKey = responseData.captcha_site_key || "";
        
        // Call the CAPTCHA solving endpoint
        const solverResponse = await fetch("/api/job-description/solve-captcha", {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          credentials: "include",
          body: JSON.stringify({
            site_key: siteKey,
            page_url: "https://www.indeed.com/jobs",  // Use appropriate URL
            is_invisible: false
          })
        });
        
        if (!solverResponse.ok) {
          const errorData = await solverResponse.json();
          throw new Error(errorData.detail || "Failed to solve CAPTCHA");
        }
        
        const solverData = await solverResponse.json();
        const captchaToken = solverData.captcha_token;
        
        if (!captchaToken) {
          throw new Error("No CAPTCHA token received");
        }
        
        setError("CAPTCHA solved! Retrying search...");
        
        // Retry the search with the CAPTCHA token
        requestBody.captcha_token = captchaToken;
        
        response = await fetch("/api/job-description/research", {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          credentials: "include",
          body: JSON.stringify(requestBody)
        });
      }
    }
    
    // Handle the final response
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || "Failed to research job role");
    }
    
    const data = await response.json();
    setJobData(data);
    
    // If the result is AI-generated, show a notification
    if (data.is_ai_generated) {
      setSuccess("This job description was generated using AI due to scraping limitations.");
      setTimeout(() => setSuccess(null), 5000);
    }
    
    // Scroll to results
    if (resultsRef.current) {
      resultsRef.current.scrollIntoView({ behavior: 'smooth' });
    }
    
    // Update search history after successful search
    fetchSearchHistory();
  } catch (err) {
    console.error("Error researching job:", err);
    setError(err.message || "Error researching job role. Please try again.");
    setTimeout(() => setError(null), 3000);
  } finally {
    setLoading(false);
  }
};

 

  // Generate PDF report of job description
  const generatePDF = async () => {
    if (!jobData) return;
    
    try {
      setPdfGenerating(true);
      
      const response = await fetch("/api/job-description/generate-pdf", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        credentials: "include",
        body: JSON.stringify({
          job_role: jobRole,
          job_data: jobData
        })
      });
      
      if (!response.ok) {
        throw new Error("Failed to generate PDF");
      }
      
      // Get the PDF as a blob
      const blob = await response.blob();
      
      // Create a download link and trigger download
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${jobRole.replace(/\s+/g, '_')}_Job_Description.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      
      setSuccess("PDF generated successfully");
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      console.error("Error generating PDF:", err);
      setError("Error generating PDF. Please try again.");
      setTimeout(() => setError(null), 3000);
    } finally {
      setPdfGenerating(false);
    }
  };

  // Load a specific job from history
  const loadFromHistory = (historyItem) => {
    setJobRole(historyItem.job_role);
    // This will trigger a new search for the most up-to-date data
    handleSearchJob(historyItem.job_role);
  };

  // If not authenticated yet, show loading
  if (!isAuthenticated && !error) {
    return (
      <div className="p-6 bg-white rounded-xl shadow-md">
        <h2 className="text-2xl font-bold text-purple-700 mb-4">
          Job Description Research
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
        Job Description Research
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
        {/* CV Selection Section */}
        <div className="bg-gray-50 p-4 rounded-lg border border-gray-200">
          <h3 className="text-lg font-medium text-gray-800 mb-3 flex items-center">
            <FileText className="mr-2 h-5 w-5 text-purple-600" />
            Your CV
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
                onClick={() => {
                  setCvFile(null);
                  setSuggestedRoles([]);
                }}
                className="text-red-500 hover:text-red-700"
                title="Remove CV"
              >
                <Trash2 size={18} />
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
                        <button
                          onClick={(e) => handleDeleteCV(cv.id, e)}
                          className="text-red-500 hover:text-red-700"
                          title="Delete CV"
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
        
        {/* Job Role Suggestions Section */}
        {analyzing ? (
          <div className="bg-blue-50 p-4 rounded-lg border border-blue-200 flex items-center justify-center space-x-3">
            <div className="animate-spin rounded-full h-5 w-5 border-2 border-blue-500 border-t-transparent"></div>
            <p className="text-blue-700">Analyzing your CV to suggest relevant job roles...</p>
          </div>
        ) : suggestedRoles.length > 0 ? (
          <div className="bg-blue-50 p-4 rounded-lg border border-blue-200">
            <h3 className="text-lg font-medium text-gray-800 mb-3 flex items-center">
              <Zap className="mr-2 h-5 w-5 text-blue-600" />
              Suggested Job Roles Based on Your CV
            </h3>
            <div className="flex flex-wrap gap-2 mt-2">
              {suggestedRoles.map((role, index) => (
                <button
                  key={index}
                  onClick={() => handleSearchJob(role)}
                  className="bg-white border border-blue-300 text-blue-700 px-3 py-1.5 rounded-full text-sm font-medium hover:bg-blue-700 hover:text-white transition-colors flex items-center"
                >
                  <Briefcase className="mr-1.5 h-4 w-4" />
                  {role}
                </button>
              ))}
            </div>
          </div>
        ) : null}
        
        {/* Job Search Section */}
        <div className="space-y-4">
          <div className="flex space-x-2">
            <div className="flex-1 relative">
              <input
                type="text"
                value={jobRole}
                onChange={(e) => setJobRole(e.target.value)}
                placeholder="Enter a job role (e.g., Software Engineer, Data Scientist)"
                className="w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              />
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
            </div>
            <button
              onClick={() => handleSearchJob(jobRole)}
              disabled={loading || !jobRole}
              className="px-4 py-2.5 bg-purple-600 text-white rounded-md hover:bg-purple-700 transition disabled:bg-purple-300 flex items-center"
            >
              {loading ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent mr-2"></div>
                  Searching...
                </>
              ) : (
                <>
                  <Search className="mr-1.5 h-5 w-5" />
                  Research
                </>
              )}
            </button>
          </div>
          
          {/* Search History */}
          {searchHistory.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-gray-500 mb-2">Recent Searches:</h4>
              <div className="flex flex-wrap gap-2">
                {searchHistory.slice(0, 5).map((item, index) => (
                  <button
                    key={index}
                    onClick={() => loadFromHistory(item)}
                    className="bg-gray-100 hover:bg-gray-200 text-gray-700 text-sm px-3 py-1 rounded-full flex items-center"
                  >
                    <Clipboard className="mr-1 h-3.5 w-3.5" />
                    {item.job_role}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Job Description Results */}
      {jobData && (
        <div ref={resultsRef} className="mt-8 border-t pt-6">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-xl font-bold text-gray-800">
              {jobData.job_role}
            </h3>
          </div>
          
          <div className="bg-purple-50 p-4 rounded-lg mb-6">
            <p className="text-gray-700">{jobData.summary}</p>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Job Responsibilities */}
            <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
              <h4 className="font-bold text-gray-800 mb-3 flex items-center">
                <Clipboard className="mr-2 h-5 w-5 text-purple-600" />
                Key Responsibilities
              </h4>
              <ul className="space-y-2">
                {jobData.responsibilities?.map((item, index) => (
                  <li key={index} className="flex items-start">
                    <div className="min-w-4 h-4 mt-1 mr-2 bg-purple-200 rounded-full flex items-center justify-center text-xs text-purple-700">•</div>
                    <span className="text-gray-700">{item}</span>
                  </li>
                ))}
              </ul>
            </div>
            
            {/* Required Qualifications */}
            <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
              <h4 className="font-bold text-gray-800 mb-3 flex items-center">
                <Award className="mr-2 h-5 w-5 text-purple-600" />
                Required Qualifications
              </h4>
              <ul className="space-y-2">
                {jobData.qualifications?.map((item, index) => (
                  <li key={index} className="flex items-start">
                    <div className="min-w-4 h-4 mt-1 mr-2 bg-purple-200 rounded-full flex items-center justify-center text-xs text-purple-700">•</div>
                    <span className="text-gray-700">{item}</span>
                  </li>
                ))}
              </ul>
            </div>
            
            {/* Salary Info */}
            {jobData.salary && (
              <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
                <h4 className="font-bold text-gray-800 mb-3 flex items-center">
                  <DollarSign className="mr-2 h-5 w-5 text-green-600" />
                  Salary Information
                </h4>
                <p className="text-gray-700">{jobData.salary}</p>
                {jobData.benefits && (
                  <div className="mt-3">
                    <h5 className="font-medium text-gray-700 mb-1">Benefits:</h5>
                    <ul className="list-disc pl-5 text-gray-600 space-y-1">
                      {jobData.benefits.map((benefit, index) => (
                        <li key={index}>{benefit}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
            
            {/* Technologies and Tools */}
            {jobData.technologies && jobData.technologies.length > 0 && (
              <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
                <h4 className="font-bold text-gray-800 mb-3 flex items-center">
                  <Code className="mr-2 h-5 w-5 text-blue-600" />
                  Technologies & Tools
                </h4>
                <div className="flex flex-wrap gap-2">
                  {jobData.technologies.map((tech, index) => (
                    <span key={index} className="bg-blue-100 text-blue-800 text-xs font-medium px-2.5 py-1 rounded">
                      {tech}
                    </span>
                  ))}
                </div>
              </div>
            )}
            
            {/* Skills Gap Analysis - if CV was provided and analysis is available */}
            {jobData.skills_gap && (
              <div className="md:col-span-2 bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
                <h4 className="font-bold text-gray-800 mb-3 flex items-center">
                  <BarChart2 className="mr-2 h-5 w-5 text-orange-600" />
                  Skills Gap Analysis
                </h4>
                <div className="space-y-4">
                  {/* Matching Skills */}
                  <div>
                    <h5 className="font-medium text-green-700 mb-2">Your Matching Skills:</h5>
                    <div className="flex flex-wrap gap-2">
                      {jobData.skills_gap.matching_skills?.map((skill, index) => (
                        <span key={index} className="bg-green-100 text-green-800 text-xs font-medium px-2.5 py-1 rounded flex items-center">
                          <CheckCircle className="mr-1 h-3 w-3" />
                          {skill}
                        </span>
                      ))}
                    </div>
                  </div>
                  
                  {/* Missing Skills */}
                  <div>
                    <h5 className="font-medium text-orange-700 mb-2">Skills to Develop:</h5>
                    <div className="flex flex-wrap gap-2">
                      {jobData.skills_gap.missing_skills?.map((skill, index) => (
                        <span key={index} className="bg-orange-100 text-orange-800 text-xs font-medium px-2.5 py-1 rounded">
                          {skill}
                        </span>
                      ))}
                    </div>
                  </div>
                  
                  {/* Recommendations */}
                  {jobData.skills_gap.recommendations && (
                    <div className="mt-3 bg-blue-50 p-3 rounded">
                      <h5 className="font-medium text-blue-700 mb-1 flex items-center">
                        <Book className="mr-1.5 h-4 w-4" />
                        Learning Recommendations:
                      </h5>
                      <p className="text-blue-800 text-sm">{jobData.skills_gap.recommendations}</p>
                    </div>
                  )}
                </div>
              </div>
            )}
            
            {/* Additional sections from the job data */}
            {jobData.additional_info && (
              <div className="md:col-span-2 bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
                <h4 className="font-bold text-gray-800 mb-3">Additional Information</h4>
                <p className="text-gray-700">{jobData.additional_info}</p>
              </div>
            )}
          </div>
          
          {/* Sources */}
          {jobData.sources && jobData.sources.length > 0 && (
            <div className="mt-6 text-sm text-gray-500">
              <p className="font-medium">Sources:</p>
              <ul className="list-disc pl-5">
                {jobData.sources.map((source, index) => (
                  <li key={index}>{source}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}