// File: app/api/resume/analyze-upload/route.js
import { NextRequest, NextResponse } from 'next/server';

/**
 * API route to analyze a newly uploaded resume against ATS requirements
 * 
 * @param {NextRequest} req - The Next.js request object
 * @returns {NextResponse} - The Next.js response object
 */
export async function POST(req) {
  try {
    // Get the form data
    const formData = await req.formData();
    
    // Make sure we have a resume file and target role
    if (!formData.get("resume_file") || !formData.get("target_role")) {
      return NextResponse.json(
        { detail: "Resume file and target role are required" },
        { status: 400 }
      );
    }
    
    // Forward request to the FastAPI backend with correct URL
    const apiBaseUrl = process.env.API_BASE_URL || "http://fastapi:8000";
    const endpoint = `${apiBaseUrl}/api/resume/analyze-upload`;  // Updated to include '/api/' prefix
    
    console.log(`Calling FastAPI endpoint: ${endpoint}`);
    
    const response = await fetch(endpoint, {
      method: "POST",
      headers: {
        "Cookie": req.headers.get("cookie") || "",
      },
      body: formData,
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
    console.error("Error in resume analyze-upload API route:", error);
    return NextResponse.json(
      { detail: "Internal server error" },
      { status: 500 }
    );
  }
}