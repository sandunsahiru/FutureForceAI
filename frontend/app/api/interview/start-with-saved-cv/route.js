import { NextResponse } from "next/server";
import jwt from "jsonwebtoken";
import connectToDatabase from '@/lib/db';
import CV from '@/models/CV';
import { readFile } from 'fs/promises';
import { existsSync } from 'fs';

export async function POST(request) {
  console.log("==== START API ROUTE HANDLER: /api/interview/start-with-saved-cv ====");
  try {
    // Get token from cookies
    const tokenCookie = request.cookies.get("token");
    const token = tokenCookie?.value;
    
    // Log all headers for debugging
    console.log("Request headers:", Object.fromEntries([...request.headers.entries()]));
    
    if (!token) {
      console.error("Authentication error: No token found in cookies");
      return NextResponse.json(
        { detail: "Authentication required" },
        { status: 401 }
      );
    }

    // Verify token
    let userId;
    try {
      const decoded = jwt.verify(token, process.env.JWT_SECRET);
      userId = decoded.userId;
      console.log("Token verified for user:", userId);
    } catch (jwtError) {
      console.error("Invalid token:", jwtError);
      return NextResponse.json(
        { detail: "Invalid authentication token" },
        { status: 401 }
      );
    }
    
    // Get JSON data from request
    const jsonData = await request.json();
    console.log("Received JSON data:", jsonData);
    
    const { cv_id, job_role } = jsonData;
    
    if (!cv_id || !job_role) {
      console.error("Missing required fields: cv_id or job_role");
      return NextResponse.json(
        { detail: "CV ID and job role are required" },
        { status: 400 }
      );
    }
    
    // Connect to database and get CV
    await connectToDatabase();
    
    // Find the CV record
    const cvRecord = await CV.findById(cv_id);
    if (!cvRecord || cvRecord.userId.toString() !== userId) {
      console.error(`CV not found or not owned by user: ${cv_id}`);
      return NextResponse.json(
        { detail: "CV not found or unauthorized" },
        { status: 404 }
      );
    }
    
    console.log(`Found CV: ${cvRecord.originalName}`);
    
    // Update lastUsed timestamp
    cvRecord.lastUsed = new Date();
    await cvRecord.save();
    
    // Verify file exists
    if (!cvRecord.filePath || !existsSync(cvRecord.filePath)) {
      console.error(`CV file not found on disk: ${cvRecord.filePath}`);
      return NextResponse.json(
        { detail: "CV file not found on disk" },
        { status: 404 }
      );
    }
    
    // Call FastAPI endpoint for saved CV
    const fastApiUrl = process.env.FASTAPI_URL || "http://fastapi:8000";
    const endpoint = `${fastApiUrl}/api/interview/start-with-saved-cv`;
    
    // Create payload
    const payload = {
      job_role: job_role,
      cv_id: cv_id.toString(),
      user_id: userId
    };
    
    console.log(`Calling FastAPI endpoint: ${endpoint}`);
    console.log("With payload:", payload);
    
    // IMPORTANT: Pass token in multiple ways to ensure it's received
    const headers = {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${token}`,
      "Cookie": `token=${token}`
    };
    
    console.log("Request headers:", headers);
    
    // Make the API call
    const response = await fetch(endpoint, {
      method: "POST",
      headers: headers,
      body: JSON.stringify(payload),
      credentials: "include"
    });
    
    console.log(`FastAPI response status: ${response.status}`);
    
    // Handle error responses
    if (!response.ok) {
      let errorDetail = "Failed to start interview";
      try {
        const errorData = await response.json();
        console.error("Error details:", errorData);
        errorDetail = errorData.detail || errorDetail;
      } catch (e) {
        try {
          const errorText = await response.text();
          console.error("Error text:", errorText);
          errorDetail = errorText || errorDetail;
        } catch (textErr) {}
      }
      
      return NextResponse.json(
        { detail: errorDetail },
        { status: response.status }
      );
    }
    
    // Parse successful response
    try {
      const data = await response.json();
      console.log("Successfully received response from FastAPI");
      
      // Validate response structure and provide fallback if needed
      if (!data.session_id || !data.first_ai_message) {
        console.warn("Incomplete data from FastAPI:", data);
        
        const completeData = {
          session_id: data.session_id || `fallback-${Date.now()}`,
          first_ai_message: data.first_ai_message || {
            sender: "ai",
            text: "Welcome to the interview. Can you tell me about yourself?"
          },
          cv_id: cv_id.toString() // Include the CV ID in the response
        };
        
        return NextResponse.json(completeData);
      }
      
      // Add CV ID to the response for reference on the frontend
      const enhancedData = {
        ...data,
        cv_id: cv_id.toString()
      };
      
      return NextResponse.json(enhancedData);
    } catch (parseErr) {
      console.error("Error parsing FastAPI response:", parseErr);
      
      // Provide a fallback response
      return NextResponse.json({
        session_id: `fallback-${Date.now()}`,
        first_ai_message: {
          sender: "ai",
          text: "Welcome to the interview. Can you tell me about yourself?"
        },
        cv_id: cv_id.toString()
      });
    }
  } catch (error) {
    console.error("Unhandled error:", error);
    return NextResponse.json(
      { 
        detail: "Server error: " + error.message,
        session_id: `error-${Date.now()}`,
        first_ai_message: {
          sender: "ai",
          text: "There was an error starting the interview. Please try again."
        }
      },
      { status: 500 }
    );
  } finally {
    console.log("==== END API ROUTE HANDLER: /api/interview/start-with-saved-cv ====");
  }
}