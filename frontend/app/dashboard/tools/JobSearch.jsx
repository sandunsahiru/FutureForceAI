"use client";
import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { 
  Search, 
  Upload, 
  FileText, 
  Briefcase, 
  MapPin, 
  DollarSign, 
  Building2, 
  Calendar, 
  ExternalLink, 
  Filter, 
  Trash2, 
  RefreshCw, 
  AlertCircle, 
  CheckCircle, 
  Clock, 
  Star, 
  Bookmark, 
  ChevronDown, 
  ChevronUp, 
  Send,
  Loader,
  BookmarkPlus,
  BookmarkCheck
} from "lucide-react";

export default function JobSearch() {
  // State management
  const [cvFile, setCvFile] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [location, setLocation] = useState("");
  const [jobType, setJobType] = useState("all");
  const [experienceLevel, setExperienceLevel] = useState("all");
  const [salaryRange, setSalaryRange] = useState("all");
  const [datePosted, setDatePosted] = useState("all");
  const [savedCVs, setSavedCVs] = useState([]);
  const [showCVSelector, setShowCVSelector] = useState(false);
  const [loading, setLoading] = useState(false);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [searchResults, setSearchResults] = useState([]);
  const [savedJobs, setSavedJobs] = useState([]);
  const [expandedJob, setExpandedJob] = useState(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [sortBy, setSortBy] = useState("relevance");
  const [showFilters, setShowFilters] = useState(false);

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
        
        // Fetch user's saved CVs and saved jobs
        fetchSavedCVs();
        fetchSavedJobs();
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
          const sortedCVs = [...data.cvs].sort((a, b) => 
            new Date(b.uploaded_at) - new Date(a.uploaded_at)
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

  // Fetch user's saved jobs
  const fetchSavedJobs = async () => {
    try {
      const response = await fetch("/api/user/saved-jobs", {
        credentials: "include"
      });
      
      if (response.ok) {
        const data = await response.json();
        setSavedJobs(data.jobs || []);
      }
    } catch (err) {
      console.error("Error fetching saved jobs:", err);
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
      
      // Upload file to server
      uploadCV(file);
    }
  };

  // Upload CV to server
  const uploadCV = async (file) => {
    try {
      setLoading(true);
      
      const formData = new FormData();
      formData.append("cv_file", file);
      
      const response = await fetch("/api/user/save-cv", {
        method: "POST",
        credentials: "include",
        body: formData
      });
      
      if (response.ok) {
        const data = await response.json();
        
        // Set the uploaded CV
        setCvFile({
          id: data.cv_id,
          name: file.name,
          size: file.size,
          useSaved: true
        });
        
        setSuccess("CV uploaded successfully");
        setTimeout(() => setSuccess(null), 3000);
        
        // Refresh saved CVs
        fetchSavedCVs();
      } else {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to upload CV");
      }
    } catch (err) {
      console.error("Error uploading CV:", err);
      setError("Error uploading CV. Please try again.");
      setTimeout(() => setError(null), 5000);
    } finally {
      setLoading(false);
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

  // Delete a saved CV
  const handleDeleteCV = async (cvId, e) => {
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
        if (cvFile && cvFile.id === cvId) {
          setCvFile(null);
        }
        
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

  // Search for jobs
  const searchJobs = async (pageNum = 1) => {
    if (!searchQuery.trim()) {
      setError("Please enter a job title or keywords to search");
      setTimeout(() => setError(null), 3000);
      return;
    }

    try {
      setSearching(true);
      setError(null);
      
      const searchParams = {
        query: searchQuery,
        location: location,
        job_type: jobType,
        experience_level: experienceLevel,
        salary_range: salaryRange,
        date_posted: datePosted,
        sort_by: sortBy,
        page: pageNum,
        cv_id: cvFile && cvFile.useSaved ? cvFile.id : null
      };

      const response = await fetch("/api/job-search", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify(searchParams),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to search jobs");
      }

      const data = await response.json();
      setSearchResults(data.jobs || []);
      setTotalPages(data.total_pages || 1);
      setPage(pageNum);

      if (resultsRef.current && pageNum === 1) {
        resultsRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    } catch (err) {
      console.error("Error searching jobs:", err);
      setError(err.message || "Error searching jobs. Please try again.");
      setTimeout(() => setError(null), 3000);
    } finally {
      setSearching(false);
    }
  };

  // Save/unsave a job
  const toggleSaveJob = async (job) => {
    try {
      const isSaved = savedJobs.some(savedJob => savedJob.id === job.id);
      
      if (isSaved) {
        // Unsave the job
        const response = await fetch(`/api/user/saved-jobs/${job.id}`, {
          method: "DELETE",
          credentials: "include"
        });
        
        if (response.ok) {
          setSavedJobs(savedJobs.filter(savedJob => savedJob.id !== job.id));
          setSuccess("Job removed from saved jobs");
        }
      } else {
        // Save the job
        const response = await fetch("/api/user/saved-jobs", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          credentials: "include",
          body: JSON.stringify({ job: job }),
        });
        
        if (response.ok) {
          setSavedJobs([...savedJobs, job]);
          setSuccess("Job saved successfully");
        }
      }
      
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      console.error("Error saving/unsaving job:", err);
      setError("Error updating saved jobs. Please try again.");
      setTimeout(() => setError(null), 3000);
    }
  };

  // Apply for a job
  const applyForJob = async (job) => {
    if (!cvFile) {
      setError("Please upload or select a CV before applying");
      setTimeout(() => setError(null), 3000);
      return;
    }

    try {
      const response = await fetch("/api/job-apply", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify({
          job_id: job.id,
          cv_id: cvFile.useSaved ? cvFile.id : null,
          job_url: job.url
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to apply for job");
      }

      // Open the job application page in a new tab
      window.open(job.url, '_blank');
      
      setSuccess("Application started. Complete your application in the new tab.");
      setTimeout(() => setSuccess(null), 5000);
    } catch (err) {
      console.error("Error applying for job:", err);
      setError(err.message || "Error applying for job. Please try again.");
      setTimeout(() => setError(null), 3000);
    }
  };

  // Format salary display
  const formatSalary = (salary) => {
    if (!salary) return "Not specified";
    return salary;
  };

  // Format date
  const formatDate = (dateString) => {
    if (!dateString) return "Unknown";
    const date = new Date(dateString);
    const now = new Date();
    const diffTime = Math.abs(now - date);
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    
    if (diffDays === 0) return "Today";
    if (diffDays === 1) return "Yesterday";
    if (diffDays < 7) return `${diffDays} days ago`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
    if (diffDays < 365) return `${Math.floor(diffDays / 30)} months ago`;
    return `${Math.floor(diffDays / 365)} years ago`;
  };

  // If not authenticated yet, show loading
  if (!isAuthenticated && !error) {
    return (
      <div className="p-6 bg-white rounded-xl shadow-md">
        <h2 className="text-2xl font-bold text-purple-700 mb-4">
          Smart Job Search
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
        Smart Job Search
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
            Your CV (Optional - for personalized recommendations)
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
                            {new Date(cv.uploaded_at).toLocaleDateString()} • {Math.round(cv.size/1024)} KB
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
        
        {/* Search Section */}
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="relative">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Job title, keywords, or company"
                className="w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                onKeyPress={(e) => e.key === 'Enter' && searchJobs()}
              />
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
            </div>
            <div className="relative">
              <input
                type="text"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="Location (city, state, or remote)"
                className="w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                onKeyPress={(e) => e.key === 'Enter' && searchJobs()}
              />
              <MapPin className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
            </div>
          </div>
          
          {/* Filters */}
          <div className="flex justify-between items-center">
            <button
              onClick={() => setShowFilters(!showFilters)}
              className="flex items-center text-purple-600 hover:text-purple-700"
            >
              <Filter className="mr-2 h-4 w-4" />
              {showFilters ? 'Hide Filters' : 'Show Filters'}
              {showFilters ? <ChevronUp className="ml-1 h-4 w-4" /> : <ChevronDown className="ml-1 h-4 w-4" />}
            </button>
            <button
              onClick={() => searchJobs()}
              disabled={searching}
              className="px-6 py-2.5 bg-purple-600 text-white rounded-md hover:bg-purple-700 transition disabled:bg-purple-300 flex items-center"
            >
              {searching ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent mr-2"></div>
                  Searching...
                </>
              ) : (
                <>
                  <Search className="mr-2 h-5 w-5" />
                  Search Jobs
                </>
              )}
            </button>
          </div>
          
          {/* Filter Options */}
          {showFilters && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 p-4 bg-gray-50 rounded-lg border border-gray-200">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Job Type</label>
                <select
                  value={jobType}
                  onChange={(e) => setJobType(e.target.value)}
                  className="w-full p-2 border border-gray-300 rounded-md"
                >
                  <option value="all">All Types</option>
                  <option value="full-time">Full Time</option>
                  <option value="part-time">Part Time</option>
                  <option value="contract">Contract</option>
                  <option value="internship">Internship</option>
                  <option value="temporary">Temporary</option>
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Experience Level</label>
                <select
                  value={experienceLevel}
                  onChange={(e) => setExperienceLevel(e.target.value)}
                  className="w-full p-2 border border-gray-300 rounded-md"
                >
                  <option value="all">All Levels</option>
                  <option value="entry">Entry Level</option>
                  <option value="mid">Mid Level</option>
                  <option value="senior">Senior Level</option>
                  <option value="executive">Executive</option>
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Date Posted</label>
                <select
                  value={datePosted}
                  onChange={(e) => setDatePosted(e.target.value)}
                  className="w-full p-2 border border-gray-300 rounded-md"
                >
                  <option value="all">Any Time</option>
                  <option value="24h">Last 24 hours</option>
                  <option value="3d">Last 3 days</option>
                  <option value="7d">Last 7 days</option>
                  <option value="14d">Last 14 days</option>
                  <option value="30d">Last 30 days</option>
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Salary Range</label>
                <select
                  value={salaryRange}
                  onChange={(e) => setSalaryRange(e.target.value)}
                  className="w-full p-2 border border-gray-300 rounded-md"
                >
                  <option value="all">Any Salary</option>
                  <option value="0-50k">$0 - $50,000</option>
                  <option value="50k-75k">$50,000 - $75,000</option>
                  <option value="75k-100k">$75,000 - $100,000</option>
                  <option value="100k-150k">$100,000 - $150,000</option>
                  <option value="150k+">$150,000+</option>
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Sort By</label>
                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value)}
                  className="w-full p-2 border border-gray-300 rounded-md"
                >
                  <option value="relevance">Relevance</option>
                  <option value="date">Date Posted</option>
                  <option value="salary">Salary</option>
                </select>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Search Results */}
      {searchResults.length > 0 && (
        <div ref={resultsRef} className="mt-8 border-t pt-6">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-xl font-bold text-gray-800">
              Found {searchResults.length} Jobs
            </h3>
            {totalPages > 1 && (
              <div className="flex items-center gap-2">
                <button
                  onClick={() => searchJobs(page - 1)}
                  disabled={page === 1 || searching}
                  className="px-3 py-1 border rounded-md disabled:opacity-50"
                >
                  Previous
                </button>
                <span className="text-sm text-gray-600">
                  Page {page} of {totalPages}
                </span>
                <button
                  onClick={() => searchJobs(page + 1)}
                  disabled={page === totalPages || searching}
                  className="px-3 py-1 border rounded-md disabled:opacity-50"
                >
                  Next
                </button>
              </div>
            )}
          </div>
          
          <div className="space-y-4">
            {searchResults.map((job) => (
              <div
                key={job.id}
                className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow"
              >
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <h4 className="text-lg font-semibold text-gray-900">
                      {job.title}
                    </h4>
                    <div className="flex items-center gap-4 mt-1 text-sm text-gray-600">
                      <span className="flex items-center">
                        <Building2 className="mr-1 h-4 w-4" />
                        {job.company}
                      </span>
                      <span className="flex items-center">
                        <MapPin className="mr-1 h-4 w-4" />
                        {job.location}
                      </span>
                      {job.salary && (
                        <span className="flex items-center">
                          <DollarSign className="mr-1 h-4 w-4" />
                          {formatSalary(job.salary)}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => toggleSaveJob(job)}
                      className={`p-2 rounded-full ${
                        savedJobs.some(savedJob => savedJob.id === job.id)
                          ? 'text-yellow-500 hover:text-yellow-600'
                          : 'text-gray-400 hover:text-gray-600'
                      }`}
                      title={savedJobs.some(savedJob => savedJob.id === job.id) ? 'Unsave job' : 'Save job'}
                    >
                      {savedJobs.some(savedJob => savedJob.id === job.id) ? (
                        <BookmarkCheck className="h-5 w-5" />
                      ) : (
                        <BookmarkPlus className="h-5 w-5" />
                      )}
                    </button>
                  </div>
                </div>
                
                <div className="mt-3 flex flex-wrap gap-2">
                  {job.type && (
                    <span className="px-2 py-1 bg-blue-100 text-blue-800 text-xs font-medium rounded">
                      {job.type}
                    </span>
                  )}
                  {job.experience_level && (
                    <span className="px-2 py-1 bg-green-100 text-green-800 text-xs font-medium rounded">
                      {job.experience_level}
                    </span>
                  )}
                  {job.remote && (
                    <span className="px-2 py-1 bg-purple-100 text-purple-800 text-xs font-medium rounded">
                      Remote
                    </span>
                  )}
                </div>
                
                <p className="mt-3 text-gray-700 line-clamp-2">
                  {job.description}
                </p>
                
                {/* Job Match Score if CV is provided */}
                {cvFile && job.match_score && (
                  <div className="mt-3 flex items-center">
                    <div className="flex-1 bg-gray-200 rounded-full h-2">
                      <div
                        className={`h-2 rounded-full ${
                          job.match_score >= 80 ? 'bg-green-500' :
                          job.match_score >= 60 ? 'bg-yellow-500' : 'bg-red-500'
                        }`}
                        style={{ width: `${job.match_score}%` }}
                      ></div>
                    </div>
                    <span className="ml-3 text-sm font-medium text-gray-700">
                      {job.match_score}% Match
                    </span>
                  </div>
                )}
                
                <div className="mt-4 flex justify-between items-center">
                  <div className="flex items-center text-sm text-gray-500">
                    <Clock className="mr-1 h-4 w-4" />
                    Posted {formatDate(job.posted_date)}
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setExpandedJob(expandedJob === job.id ? null : job.id)}
                      className="px-4 py-2 border border-purple-600 text-purple-600 rounded-md hover:bg-purple-50 transition flex items-center"
                    >
                      {expandedJob === job.id ? 'Show Less' : 'View Details'}
                      {expandedJob === job.id ? (
                        <ChevronUp className="ml-1 h-4 w-4" />
                      ) : (
                        <ChevronDown className="ml-1 h-4 w-4" />
                      )}
                    </button>
                    <button
                      onClick={() => applyForJob(job)}
                      className="px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700 transition flex items-center"
                    >
                      <Send className="mr-1 h-4 w-4" />
                      Apply
                    </button>
                  </div>
                </div>
                
                {/* Expanded Job Details */}
                {expandedJob === job.id && (
                  <div className="mt-4 border-t pt-4">
                    <div className="space-y-4">
                      {job.full_description && (
                        <div>
                          <h5 className="font-semibold text-gray-800 mb-2">Full Description</h5>
                          <p className="text-gray-700 whitespace-pre-line">{job.full_description}</p>
                        </div>
                      )}
                      
                      {job.requirements && job.requirements.length > 0 && (
                        <div>
                          <h5 className="font-semibold text-gray-800 mb-2">Requirements</h5>
                          <ul className="list-disc pl-5 space-y-1 text-gray-700">
                            {job.requirements.map((req, index) => (
                              <li key={index}>{req}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      
                      {job.responsibilities && job.responsibilities.length > 0 && (
                        <div>
                          <h5 className="font-semibold text-gray-800 mb-2">Responsibilities</h5>
                          <ul className="list-disc pl-5 space-y-1 text-gray-700">
                            {job.responsibilities.map((resp, index) => (
                              <li key={index}>{resp}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      
                      {job.benefits && job.benefits.length > 0 && (
                        <div>
                          <h5 className="font-semibold text-gray-800 mb-2">Benefits</h5>
                          <ul className="list-disc pl-5 space-y-1 text-gray-700">
                            {job.benefits.map((benefit, index) => (
                              <li key={index}>{benefit}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      
                      {job.skills && job.skills.length > 0 && (
                        <div>
                          <h5 className="font-semibold text-gray-800 mb-2">Required Skills</h5>
                          <div className="flex flex-wrap gap-2">
                            {job.skills.map((skill, index) => (
                              <span
                                key={index}
                                className="px-2 py-1 bg-purple-100 text-purple-800 text-xs font-medium rounded"
                              >
                                {skill}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                      
                      {job.company_info && (
                        <div>
                          <h5 className="font-semibold text-gray-800 mb-2">About {job.company}</h5>
                          <p className="text-gray-700">{job.company_info}</p>
                        </div>
                      )}
                      
                      <div className="flex justify-end gap-2 pt-4">
                        <button
                          onClick={() => applyForJob(job)}
                          className="px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700 transition flex items-center"
                        >
                          <Send className="mr-1 h-4 w-4" />
                          Apply Now
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
          
          {/* Pagination */}
          {totalPages > 1 && (
            <div className="mt-6 flex justify-center">
              <nav className="flex items-center gap-2">
                <button
                  onClick={() => searchJobs(1)}
                  disabled={page === 1 || searching}
                  className="px-3 py-1 border rounded-md disabled:opacity-50"
                >
                  First
                </button>
                <button
                  onClick={() => searchJobs(page - 1)}
                  disabled={page === 1 || searching}
                  className="px-3 py-1 border rounded-md disabled:opacity-50"
                >
                  Previous
                </button>
                
                {/* Page numbers */}
                {[...Array(Math.min(5, totalPages))].map((_, i) => {
                  const pageNum = page - 2 + i;
                  if (pageNum > 0 && pageNum <= totalPages) {
                    return (
                      <button
                        key={pageNum}
                        onClick={() => searchJobs(pageNum)}
                        disabled={searching}
                        className={`px-3 py-1 border rounded-md ${
                          pageNum === page
                            ? 'bg-purple-600 text-white border-purple-600'
                            : 'hover:bg-gray-50'
                        }`}
                      >
                        {pageNum}
                      </button>
                    );
                  }
                  return null;
                })}
                
                <button
                  onClick={() => searchJobs(page + 1)}
                  disabled={page === totalPages || searching}
                  className="px-3 py-1 border rounded-md disabled:opacity-50"
                >
                  Next
                </button>
                <button
                  onClick={() => searchJobs(totalPages)}
                  disabled={page === totalPages || searching}
                  className="px-3 py-1 border rounded-md disabled:opacity-50"
                >
                  Last
                </button>
              </nav>
            </div>
          )}
        </div>
      )}
      
      {/* No results message */}
      {searchResults.length === 0 && !searching && searchQuery && (
        <div className="mt-8 text-center py-8">
          <Briefcase className="mx-auto h-12 w-12 text-gray-400 mb-3" />
          <h3 className="text-lg font-medium text-gray-900 mb-1">No jobs found</h3>
          <p className="text-gray-500">Try adjusting your search criteria or filters</p>
        </div>
      )}
      
      {/* Saved Jobs */}
      {savedJobs.length > 0 && (
        <div className="mt-12">
          <h3 className="text-xl font-bold text-gray-800 mb-4">
            Your Saved Jobs ({savedJobs.length})
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {savedJobs.map((job) => (
              <div
                key={job.id}
                className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow"
              >
                <div className="flex justify-between items-start">
                  <div>
                    <h4 className="font-semibold text-gray-900">{job.title}</h4>
                    <p className="text-sm text-gray-600">{job.company}</p>
                    <p className="text-sm text-gray-500">{job.location}</p>
                  </div>
                  <button
                    onClick={() => toggleSaveJob(job)}
                    className="text-yellow-500 hover:text-yellow-600"
                    title="Remove from saved"
                  >
                    <BookmarkCheck className="h-5 w-5" />
                  </button>
                </div>
                <div className="mt-3 flex justify-end gap-2">
                  <a
                    href={job.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-purple-600 hover:text-purple-700 text-sm flex items-center"
                  >
                    <ExternalLink className="mr-1 h-3 w-3" />
                    View
                  </a>
                  <button
                    onClick={() => applyForJob(job)}
                    className="text-purple-600 hover:text-purple-700 text-sm flex items-center"
                  >
                    <Send className="mr-1 h-3 w-3" />
                    Apply
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}