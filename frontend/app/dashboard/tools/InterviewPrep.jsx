"use client";
import { useState } from "react";

export default function InterviewPrep() {
  const [cvFile, setCvFile] = useState(null);
  const [jobRole, setJobRole] = useState("");
  const [chatStarted, setChatStarted] = useState(false);
  const [chatMessages, setChatMessages] = useState([]);
  const [currentInput, setCurrentInput] = useState("");

  // Handle file upload and store CV file
  const handleFileChange = (e) => {
    setCvFile(e.target.files[0]);
  };

  // Start the interview chat
  const handleStartChat = async () => {
    if (!cvFile || !jobRole) {
      alert("Please upload your CV and specify the job role.");
      return;
    }
    // Here you would normally:
    // 1. Upload and store the CV (and possibly process it via Cloud Vision or similar)
    // 2. Send the CV content and job role to OpenAI/Gemini to analyze and generate an interview script.
    // For now, we simulate starting the chat with a welcome question.
    setChatStarted(true);
    setChatMessages([
      {
        sender: "ai",
        text: `Thank you for uploading your CV for the ${jobRole} role. Let's begin your interview. Can you tell me about yourself?`,
      },
    ]);
  };

  // Send a user message and simulate an AI response
  const handleSendMessage = async () => {
    if (!currentInput.trim()) return;

    // Append user's message
    const userMessage = { sender: "user", text: currentInput };
    setChatMessages((prev) => [...prev, userMessage]);

    // Here you would normally call your backend API passing the chat history,
    // the user's answer, CV details, and job role. The API would return the next interview question
    // along with feedback. For now, we'll simulate a simple static response.
    let aiResponseText = "";
    if (currentInput.length < 20) {
      aiResponseText =
        "I appreciate your effort, but could you provide more details?";
    } else {
      aiResponseText =
        "Well said! Can you elaborate on your key strengths for this role?";
    }

    // Simulate delay for AI response
    setTimeout(() => {
      setChatMessages((prev) => [
        ...prev,
        { sender: "ai", text: aiResponseText },
      ]);
    }, 800);

    setCurrentInput("");
  };

  return (
    <div className="p-6 bg-white rounded-xl shadow-md">
      <h2 className="text-2xl font-bold text-purple-700 mb-4">
        Interview Prep Bot
      </h2>
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
            className="bg-purple-700 text-white px-4 py-2 rounded-md hover:bg-purple-800 transition"
          >
            Start Interview
          </button>
        </div>
      ) : (
        <div className="mt-6">
          <div className="h-80 overflow-y-auto border rounded-md p-4 bg-gray-50">
            {chatMessages.map((msg, index) => (
              <div
                key={index}
                className={`mb-2 ${
                  msg.sender === "ai"
                    ? "text-purple-700"
                    : "text-gray-800"
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
            />
            <button
              onClick={handleSendMessage}
              className="bg-purple-700 text-white px-4 py-2 rounded-r-md hover:bg-purple-800 transition"
            >
              Send
            </button>
          </div>
        </div>
      )}
    </div>
  );
}