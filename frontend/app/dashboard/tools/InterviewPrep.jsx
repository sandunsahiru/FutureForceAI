"use client";
import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";

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
      } catch (err) {
        console.error("Error checking authentication:", err);
        router.push("/login");
      }
    };
    
    checkAuth();
  }, [router]);
  
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

  // Start the interview by calling the backend's /start endpoint
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
      console.log("Starting interview with:", { jobRole, cvFileName: cvFile.name });

      // Prepare form data with file and job role
      const formData = new FormData();
      formData.append("cv_file", cvFile);
      formData.append("job_role", jobRole);

      // Call the Next.js API route that forwards to FastAPI
      const response = await fetch("/api/interview/start", {
        method: "POST",
        body: formData,
        credentials: "include", // Include cookies
      });

      console.log("Response status:", response.status);
      
      // Handle authentication errors
      if (response.status === 401) {
        console.error("Authentication error - redirecting to login");
        setIsAuthenticated(false);
        router.push("/login?from=" + encodeURIComponent(window.location.pathname));
        return;
      }
      
      if (!response.ok) {
        // Try to get the error message from the response
        let errorDetail = "Unable to start interview";
        try {
          const errorData = await response.json();
          errorDetail = errorData.detail || errorDetail;
        } catch (e) {
          // If can't parse JSON, try to get text
          try {
            errorDetail = await response.text() || errorDetail;
          } catch (textErr) {
            console.error("Error getting response text:", textErr);
          }
        }
        setError(errorDetail);
        console.error("Error response:", errorDetail);
        return;
      }
      
      let data;
      try {
        data = await response.json();
        console.log("Start response data:", data);
      } catch (err) {
        setError("Invalid response format from server");
        console.error("Error parsing response:", err);
        return;
      }
      
      // Verify the data structure
      if (!data || !data.session_id || !data.first_ai_message) {
        setError("Missing required data in server response");
        console.error("Invalid response structure:", data);
        return;
      }

      // Store session_id and the first AI message
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
        credentials: "include", // Include cookies
        body: JSON.stringify({
          session_id: sessionId,
          user_message: inputToSend,
        }),
      });

      console.log("Chat response status:", response.status);
      
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
      <h2 className="text-2xl font-bold text-purple-700 mb-4">
        Interview Prep Bot
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

      {/* Show inputs if the interview hasn't started */}
      {!chatStarted ? (
        <div className="space-y-4">
          <div>
            <label className="block text-gray-700">Upload your CV:</label>
            <input
              type="file"
              accept=".pdf,.doc,.docx"
              onChange={handleFileChange}
              className="mt-1 block w-full"
            />
            {cvFile && (
              <p className="mt-1 text-sm text-gray-500">
                Selected: {cvFile.name} ({Math.round(cvFile.size / 1024)} KB)
              </p>
            )}
          </div>
          <div>
            <label className="block text-gray-700">
              Job Role for Interview:
            </label>
            <input
              type="text"
              value={jobRole}
              onChange={(e) => setJobRole(e.target.value)}
              className="mt-1 block w-full border rounded-md p-2"
              placeholder="e.g., Software Engineer"
            />
          </div>
          <button
            onClick={handleStartChat}
            className="bg-purple-700 text-white px-4 py-2 rounded-md hover:bg-purple-800 transition disabled:bg-purple-300"
            disabled={loading || !cvFile || !jobRole}
          >
            {loading ? (
              <span className="flex items-center">
                <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Starting...
              </span>
            ) : (
              "Start Interview"
            )}
          </button>
        </div>
      ) : (
        // If the interview has started, show the chat window
        <div className="mt-6">
          <div 
            ref={chatContainerRef}
            className="h-80 overflow-y-auto border rounded-md p-4 bg-gray-50"
          >
            {chatMessages.map((msg, index) => (
              <div
                key={index}
                className={`mb-4 p-2 rounded ${
                  msg.sender === "ai" 
                    ? "bg-purple-100 text-purple-900" 
                    : "bg-gray-100 text-gray-900 ml-auto max-w-[80%]"
                }`}
              >
                <strong>{msg.sender === "ai" ? "Interviewer:" : "You:"}</strong>{" "}
                {msg.text}
              </div>
            ))}
            {loading && (
              <div className="text-center text-gray-500 my-2">
                <div className="animate-pulse">Processing...</div>
              </div>
            )}
          </div>
          <div className="mt-4 flex">
            <input
              type="text"
              value={currentInput}
              onChange={(e) => setCurrentInput(e.target.value)}
              onKeyPress={handleKeyPress}
              className="flex-1 border rounded-l-md p-2"
              placeholder="Type your answer here..."
              disabled={loading}
            />
            <button
              onClick={handleSendMessage}
              className="bg-purple-700 text-white px-4 py-2 rounded-r-md hover:bg-purple-800 transition disabled:bg-purple-300"
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