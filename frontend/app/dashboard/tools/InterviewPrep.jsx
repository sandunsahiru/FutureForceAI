"use client";
import { useState } from "react";

export default function InterviewPrep() {
  const [cvFile, setCvFile] = useState(null);
  const [jobRole, setJobRole] = useState("");
  const [chatStarted, setChatStarted] = useState(false);
  const [chatMessages, setChatMessages] = useState([]);
  const [currentInput, setCurrentInput] = useState("");
  const [sessionId, setSessionId] = useState(null);
  const [loading, setLoading] = useState(false);

  // Handle file upload
  const handleFileChange = (e) => {
    setCvFile(e.target.files[0]);
  };

  // Start the interview by calling the backend's /start endpoint
  const handleStartChat = async () => {
    if (!cvFile || !jobRole) {
      alert("Please upload your CV and specify the job role.");
      return;
    }

    try {
      setLoading(true);

      // Prepare form data for file upload + job role
      const formData = new FormData();
      // You can replace "12345" with the actual user_id from your auth system
      formData.append("user_id", "12345");
      formData.append("cv_file", cvFile);
      formData.append("job_role", jobRole);

      // Call the FastAPI backend
      const response = await fetch("http://localhost:8000/api/interview/start", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        // If the server returned an error, display it
        alert(`Error: ${data.detail || "Unable to start interview"}`);
        setLoading(false);
        return;
      }

      // Store session ID and the first AI message
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
      alert("Something went wrong starting the interview.");
    } finally {
      setLoading(false);
    }
  };

  // Send a user message and get AI response from /chat endpoint
  const handleSendMessage = async () => {
    if (!currentInput.trim()) return;

    // First, append the user's message to the chat
    const userMessage = { sender: "user", text: currentInput };
    setChatMessages((prev) => [...prev, userMessage]);

    try {
      setLoading(true);

      // Call the chat endpoint with session_id and user's message
      const response = await fetch("http://localhost:8000/api/interview/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          user_message: currentInput,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        alert(`Error: ${data.detail || "Unable to continue interview"}`);
        setLoading(false);
        return;
      }

      // data.messages is the entire updated conversation
      setChatMessages(data.messages);
      setCurrentInput("");
    } catch (err) {
      console.error("Error during chat:", err);
      alert("Something went wrong during the interview.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 bg-white rounded-xl shadow-md">
      <h2 className="text-2xl font-bold text-purple-700 mb-4">
        Interview Prep Bot
      </h2>

      {/* If the interview hasn't started yet, show file/jobRole inputs */}
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
          </div>

          <div>
            <label className="block text-gray-700">Job Role for Interview:</label>
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
            className="bg-purple-700 text-white px-4 py-2 rounded-md hover:bg-purple-800 transition"
            disabled={loading}
          >
            {loading ? "Starting..." : "Start Interview"}
          </button>
        </div>
      ) : (
        // If the interview has started, show the chat window
        <div className="mt-6">
          <div className="h-80 overflow-y-auto border rounded-md p-4 bg-gray-50">
            {chatMessages.map((msg, index) => (
              <div
                key={index}
                className={`mb-2 ${
                  msg.sender === "ai" ? "text-purple-700" : "text-gray-800"
                }`}
              >
                <strong>{msg.sender === "ai" ? "Interviewer:" : "You:"}</strong>{" "}
                {msg.text}
              </div>
            ))}
          </div>

          <div className="mt-4 flex">
            <input
              type="text"
              value={currentInput}
              onChange={(e) => setCurrentInput(e.target.value)}
              className="flex-1 border rounded-l-md p-2"
              placeholder="Type your answer here..."
              disabled={loading}
            />
            <button
              onClick={handleSendMessage}
              className="bg-purple-700 text-white px-4 py-2 rounded-r-md hover:bg-purple-800 transition"
              disabled={loading}
            >
              {loading ? "Sending..." : "Send"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}