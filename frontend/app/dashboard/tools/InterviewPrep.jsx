"use client";
import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Clock, Upload, Trash2, History, MessageSquare, FileText, CheckCircle } from "lucide-react";

export default function InterviewPrep() {
  const [cvFile, setCvFile] = useState(null);
  const [jobRole, setJobRole] = useState("");
  const [chatStarted, setChatStarted] = useState(false);
  const [chatMessages, setChatMessages] = useState([]);
  const [currentInput, setCurrentInput] = useState("");
  const [sessionId, setSessionId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [savedCVs, setSavedCVs] = useState([]);
  const [showCVSelector, setShowCVSelector] = useState(false);
  const [pastSessions, setPastSessions] = useState([]);
  const [showSessionHistory, setShowSessionHistory] = useState(false);
  const chatContainerRef = useRef(null);
  const router = useRouter();
  
  // Check authentication on component mount
  useEffect(() => {
    const checkAuth = async () => {
      try {
        console.log("Checking authentication status...");
        const response = await fetch("/api/auth/check", {
          method: "GET",
          credentials: "include" // Include cookies in the request
        });
        
        const data = await response.json();
        console.log("Auth check response:", data);
        
        if (!response.ok || !data.authenticated) {
          console.log("Auth check failed, redirecting to login");
          router.push("/login?from=" + encodeURIComponent(window.location.pathname));
          return;
        }
        
        console.log("User is authenticated:", data.userId);
        setIsAuthenticated(true);
        
        // Fetch user's saved CVs
        fetchSavedCVs();
        
        // Fetch past interview sessions
        fetchPastSessions();
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
        console.log("Fetched saved CVs:", data.cvs);
      } else {
        const errorData = await response.json();
        console.error("Error response:", errorData);
      }
    } catch (err) {
      console.error("Error fetching saved CVs:", err);
    } finally {
      setLoading(false);
    }
  };
  
// Save CV to MongoDB function
const saveCVToDatabase = async (file) => {
  try {
    console.log("Saving CV to database:", file.name);
    const formData = new FormData();
    formData.append("cv_file", file);
    
    const response = await fetch("/api/user/save-cv", {
      method: "POST",
      body: formData,
      credentials: "include"
    });
    
    if (!response.ok) {
      console.error("Failed to save CV to database:", response.status);
      return null;
    }
    
    const data = await response.json();
    console.log("CV saved to database:", data);
    return data.cv;
  } catch (err) {
    console.error("Error saving CV to database:", err);
    return null;
  }
};

// Updated handleStartChat function for InterviewPrep.jsx

const handleStartChat = async () => {
  if (!isAuthenticated) {
    setError("Please log in to use this feature.");
    return;
  }
  
  if (!cvFile || !jobRole) {
    setError("Please upload your CV and specify the job role.");
    return;
  }

  try {
    setLoading(true);
    setError(null);
    
    // Check if we're using a saved CV
    if (cvFile.useSaved && cvFile.id) {
      console.log("Using saved CV approach with ID:", cvFile.id);
      
      // Make a request to the saved CV endpoint
      const response = await fetch("/api/interview/start-with-saved-cv", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        credentials: "include", // Important: Send cookies with the request
        body: JSON.stringify({
          cv_id: cvFile.id,
          job_role: jobRole
        })
      });
      
      console.log("Saved CV response status:", response.status);
      
      if (!response.ok) {
        // Handle error response
        let errorDetail = "Unable to start interview";
        try {
          const errorData = await response.json();
          console.error("Error response:", errorData);
          errorDetail = errorData.detail || errorDetail;
        } catch (e) {
          try {
            const textError = await response.text();
            console.error("Text error:", textError);
            errorDetail = textError || errorDetail;
          } catch (textErr) {}
        }
        setError(errorDetail);
        return;
      }
      
      // Handle successful response
      const data = await response.json();
      console.log("Saved CV start response data:", data);
      
      setSessionId(data.session_id);
      setChatMessages([
        {
          sender: data.first_ai_message.sender,
          text: data.first_ai_message.text,
        },
      ]);
      setChatStarted(true);
      return;
    }
    
    // If we reach here, we're using an uploaded CV file
    console.log("Using uploaded CV approach");
    
    const formData = new FormData();
    formData.append("job_role", jobRole);
    formData.append("cv_file", cvFile);
    
    // Log what we're sending
    console.log("Form data keys:", [...formData.keys()]);
    for (let pair of formData.entries()) {
      console.log(pair[0], ':', typeof pair[1], pair[1] instanceof File ? pair[1].name : pair[1]);
    }
    
    // Upload CV with FormData
    const response = await fetch("/api/interview/start", {
      method: "POST",
      body: formData,
      credentials: "include", // Include cookies
    });
    
    console.log("Uploaded CV response status:", response.status);
    
    if (!response.ok) {
      let errorDetail = "Unable to start interview";
      try {
        const errorData = await response.json();
        console.error("Error response:", errorData);
        errorDetail = errorData.detail || errorDetail;
      } catch (e) {
        try {
          const textError = await response.text();
          console.error("Text error:", textError);
          errorDetail = textError || errorDetail;
        } catch (textErr) {}
      }
      setError(errorDetail);
      return;
    }
    
    const data = await response.json();
    console.log("Uploaded CV start response data:", data);

    setSessionId(data.session_id);
    setChatMessages([
      {
        sender: data.first_ai_message.sender,
        text: data.first_ai_message.text,
      },
    ]);
    setChatStarted(true);
    
  } catch (err) {
    console.error("Error starting interview:", err);
    setError("Something went wrong starting the interview. Please try again.");
  } finally {
    setLoading(false);
  }
};


  // Fetch past interview sessions
  const fetchPastSessions = async () => {
    try {
      setLoading(true);
      const response = await fetch("/api/interview/sessions", {
        credentials: "include"
      });
      
      if (response.ok) {
        const data = await response.json();
        setPastSessions(data.sessions || []);
        console.log("Fetched past sessions:", data.sessions);
      } else {
        const errorData = await response.json();
        console.error("Error response:", errorData);
      }
    } catch (err) {
      console.error("Error fetching past sessions:", err);
    } finally {
      setLoading(false);
    }
  };
  
  // Scroll to bottom of chat whenever messages change
  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [chatMessages]);

  // Handle file upload
  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      console.log("File selected:", file.name, file.type, file.size);
      setCvFile(file);
    }
  };
  
  // Select a saved CV
  const handleSelectCV = (cv) => {
    setCvFile({
      id: cv.id,
      name: cv.filename,
      size: cv.size,
      useSaved: true
    });
    setShowCVSelector(false);
  };
  
  // Load a past session
  const handleLoadSession = async (sessionId) => {
    try {
      setLoading(true);
      const response = await fetch(`/api/interview/session/${sessionId}`, {
        credentials: "include"
      });
      
      if (response.ok) {
        const data = await response.json();
        setSessionId(data.session_id);
        setChatMessages(data.messages);
        setJobRole(data.job_role);
        setChatStarted(true);
      } else {
        setError("Failed to load session");
      }
    } catch (err) {
      console.error("Error loading session:", err);
      setError("Something went wrong while loading the session.");
    } finally {
      setLoading(false);
      setShowSessionHistory(false);
    }
  };
  
  // Delete a saved CV
  const handleDeleteCV = async (cvId, e) => {
    e.stopPropagation();
    try {
      const response = await fetch(`/api/user/cv/${cvId}`, {
        method: "DELETE",
        credentials: "include"
      });
      
      if (response.ok) {
        setSavedCVs(savedCVs.filter(cv => cv.id !== cvId));
      } else {
        setError("Failed to delete CV");
      }
    } catch (err) {
      console.error("Error deleting CV:", err);
    }
  };

  // Send a user message and get AI response from /chat endpoint
  const handleSendMessage = async () => {
    if (!isAuthenticated) {
      setError("Please log in to use this feature.");
      return;
    }
    
    if (!currentInput.trim() || loading) return;

    // Append the user's message locally
    const userMessage = { sender: "user", text: currentInput };
    setChatMessages((prev) => [...prev, userMessage]);
    const inputToSend = currentInput;
    setCurrentInput(""); // Clear input right away for better UX

    try {
      setLoading(true);
      setError(null);
      console.log("Sending message with session ID:", sessionId);

      // Call the Next.js API route that forwards to FastAPI
      const response = await fetch("/api/interview/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          session_id: sessionId,
          user_message: inputToSend,
        }),
      });
      
      // Handle authentication errors
      if (response.status === 401) {
        console.error("Authentication error - redirecting to login");
        setIsAuthenticated(false);
        router.push("/login?from=" + encodeURIComponent(window.location.pathname));
        return;
      }
      
      if (!response.ok) {
        // Try to get the error message from the response
        let errorDetail = "Unable to continue interview";
        try {
          const errorData = await response.json();
          errorDetail = errorData.detail || errorDetail;
        } catch (e) {
          // Keep default error message
        }
        setError(errorDetail);
        console.error("Error response:", errorDetail);
        return;
      }
      
      const data = await response.json();
      console.log("Chat response data:", data);

      // Update messages with the server response
      if (data && data.messages) {
        setChatMessages(data.messages);
      } else {
        setError("Invalid response format from server");
        console.error("Invalid chat response format:", data);
      }
    } catch (err) {
      console.error("Error during chat:", err);
      setError("Something went wrong during the interview. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  // Handle pressing Enter key in the input field
  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !loading) {
      e.preventDefault();
      handleSendMessage();
    }
  };
  
  // Reset the interview
  const handleReset = () => {
    setChatStarted(false);
    setChatMessages([]);
    setSessionId(null);
  };

  // If not authenticated yet, show loading
  if (!isAuthenticated && !error) {
    return (
      <div className="p-6 bg-white rounded-xl shadow-md">
        <h2 className="text-2xl font-bold text-purple-700 mb-4">
          Interview Prep Bot
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
      <h2 className="text-2xl font-bold text-purple-700 mb-4 flex items-center justify-between">
        Interview Prep Bot
        <div className="flex space-x-3">
          {chatStarted && (
            <button
              onClick={handleReset}
              className="text-sm px-3 py-1 rounded bg-gray-100 text-gray-700 hover:bg-gray-200 transition flex items-center"
            >
              <Trash2 size={14} className="mr-1" /> Reset
            </button>
          )}
          <button
            onClick={() => setShowSessionHistory(!showSessionHistory)}
            className="text-sm px-3 py-1 rounded bg-purple-100 text-purple-700 hover:bg-purple-200 transition flex items-center"
          >
            <History size={14} className="mr-1" /> History
          </button>
        </div>
      </h2>

      {/* Error message display */}
      {error && (
        <div className="mb-4 p-3 bg-red-100 border border-red-300 text-red-700 rounded">
          <p>{error}</p>
          <button 
            onClick={() => setError(null)}
            className="text-sm text-red-700 hover:text-red-900 mt-1 underline"
          >
            Dismiss
          </button>
        </div>
      )}
      
      {/* Session History Modal */}
      {showSessionHistory && (
        <div className="mb-4 p-4 border rounded bg-white shadow-md">
          <div className="flex justify-between items-center mb-3">
            <h3 className="font-bold text-purple-700">Interview History</h3>
            <div className="flex items-center">
              {loading && (
                <div className="mr-3 text-sm text-gray-500 flex items-center">
                  <svg className="animate-spin h-4 w-4 mr-1 text-purple-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Loading...
                </div>
              )}
              <button 
                onClick={() => setShowSessionHistory(false)}
                className="text-gray-500 hover:text-gray-700"
              >
                &times;
              </button>
            </div>
          </div>
          
          {pastSessions.length === 0 ? (
            <p className="text-gray-500">No past interviews found.</p>
          ) : (
            <ul className="divide-y">
              {pastSessions.map((session) => (
                <li key={session.id} className="py-2">
                  <button 
                    onClick={() => handleLoadSession(session.id)}
                    className="w-full text-left hover:bg-purple-50 p-2 rounded flex items-center justify-between"
                  >
                    <div>
                      <div className="font-medium text-gray-900">{session.job_role}</div>
                      <div className="text-sm text-gray-500 flex items-center">
                        <Clock size={14} className="mr-1" /> 
                        {new Date(session.created_at).toLocaleString()}
                      </div>
                    </div>
                    <div className="text-sm text-purple-600 flex items-center">
                      <MessageSquare size={14} className="mr-1" /> 
                      {session.message_count} messages
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Show inputs if the interview hasn't started */}
      {!chatStarted ? (
        <div className="space-y-4">
          <div>
            <label className="block text-gray-800 font-medium mb-1">CV/Resume:</label>
            
            {/* CV Selection or Upload */}
            {cvFile ? (
              <div className="flex items-center mt-2 p-3 border rounded bg-purple-50">
                <div className="flex-1">
                  <p className="font-medium text-gray-800">{cvFile.name}</p>
                  <p className="text-sm text-gray-600">
                    {Math.round((cvFile.size || 0) / 1024)} KB
                  </p>
                </div>
                <button
                  onClick={() => setCvFile(null)}
                  className="text-red-500 hover:text-red-700"
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
                  <History size={16} className="mr-2" /> 
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
                    <svg className="animate-spin h-6 w-6 text-purple-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
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
          
          <div>
            <label className="block text-gray-800 font-medium mb-1">
              Job Role for Interview:
            </label>
            <input
              type="text"
              value={jobRole}
              onChange={(e) => setJobRole(e.target.value)}
              className="w-full border border-gray-300 rounded-md p-2 text-gray-800 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              placeholder="e.g., Software Engineer, Project Manager"
            />
          </div>
          
          <button
            onClick={handleStartChat}
            className="w-full bg-purple-700 text-white px-4 py-3 rounded-md hover:bg-purple-800 transition disabled:bg-purple-300 font-medium"
            disabled={loading || !cvFile || !jobRole}
          >
            {loading ? (
              <span className="flex items-center justify-center">
                <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Starting Interview...
              </span>
            ) : (
              "Start Interview"
            )}
          </button>
        </div>
      ) : (
        // If the interview has started, show the chat window
        <div className="mt-2">
          <div 
            ref={chatContainerRef}
            className="h-96 overflow-y-auto border rounded-md p-4 bg-gray-50"
          >
            {chatMessages.map((msg, index) => (
              <div
                key={index}
                className={`mb-4 p-3 rounded-lg shadow-sm ${
                  msg.sender === "ai" 
                    ? "bg-purple-100 text-gray-800 border-l-4 border-purple-500" 
                    : "bg-white border border-gray-200 text-gray-800 ml-auto max-w-[80%]"
                }`}
              >
                <strong className={msg.sender === "ai" ? "text-purple-700" : "text-gray-700"}>
                  {msg.sender === "ai" ? "Interviewer:" : "You:"}
                </strong>{" "}
                {msg.text}
              </div>
            ))}
            {loading && (
              <div className="text-center text-gray-500 my-2">
                <div className="animate-pulse flex items-center justify-center">
                  <div className="h-2 w-2 bg-purple-500 rounded-full mr-1"></div>
                  <div className="h-2 w-2 bg-purple-500 rounded-full mr-1 animate-bounce delay-100"></div>
                  <div className="h-2 w-2 bg-purple-500 rounded-full animate-bounce delay-200"></div>
                </div>
              </div>
            )}
          </div>
          <div className="mt-4 flex">
            <input
              type="text"
              value={currentInput}
              onChange={(e) => setCurrentInput(e.target.value)}
              onKeyPress={handleKeyPress}
              className="flex-1 border border-gray-300 rounded-l-md p-3 text-gray-800 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              placeholder="Type your answer here..."
              disabled={loading}
            />
            <button
              onClick={handleSendMessage}
              className="bg-purple-700 text-white px-6 py-3 rounded-r-md hover:bg-purple-800 transition disabled:bg-purple-300 font-medium"
              disabled={loading || !currentInput.trim()}
            >
              {loading ? (
                <span className="flex items-center">
                  <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Sending...
                </span>
              ) : (
                "Send"
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}