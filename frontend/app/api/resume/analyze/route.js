// File: app/api/resume/analyze/route.js
import { NextRequest, NextResponse } from 'next/server';

/**
 * API route to analyze a resume
 * 
 * @param {NextRequest} req - The Next.js request object
 * @returns {NextResponse} - The Next.js response object
 */
export async function POST(req) {
  try {
    // Get the JSON data
    const jsonData = await req.json();
    
    // Make sure we have required fields
    if (!jsonData.resume_id || !jsonData.target_role) {
      return NextResponse.json(
        { detail: "Resume ID and target role are required" },
        { status: 400 }
      );
    }
    
    // Set up the API URL from environment variables
    const apiBaseUrl = process.env.API_BASE_URL || "http://fastapi:8000";
    const endpoint = `${apiBaseUrl}/api/resume/analyze`;  // Updated to include '/api/' prefix
    
    console.log(`Calling FastAPI endpoint: ${endpoint}`);
    console.log("With payload:", jsonData);
    
    // Forward request to the FastAPI backend
    const response = await fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Cookie": req.headers.get("cookie") || "",
      },
      body: JSON.stringify({
        resume_id: jsonData.resume_id,
        target_role: jsonData.target_role
      }),
    });
    
    // Get the response
    const result = await response.json();
    
    // Return error if response is not ok
    if (!response.ok) {
      return NextResponse.json(
        { detail: result.detail || "Failed to analyze resume" },
        { status: response.status }
      );
    }
    
    // Return the result
    return NextResponse.json(result);
  } catch (error) {
    console.error("Error in resume analyze API route:", error);
    return NextResponse.json(
      { detail: "Internal server error" },
      { status: 500 }
    );
  }
}