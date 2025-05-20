// File: app/api/resume/suggest-roles/route.js
import { NextRequest, NextResponse } from 'next/server';

/**
 * API route to suggest potential job roles based on resume content
 * 
 * @param {NextRequest} req - The Next.js request object
 * @returns {NextResponse} - The Next.js response object
 */
export async function POST(req) {
  try {
    // Get the JSON data
    const jsonData = await req.json();
    
    // Make sure we have required fields
    if (!jsonData.resume_id) {
      return NextResponse.json(
        { detail: "Resume ID is required" },
        { status: 400 }
      );
    }
    
    // Set up the API URL from environment variables
    const apiBaseUrl = process.env.API_BASE_URL || "http://fastapi:8000";
    const endpoint = `${apiBaseUrl}/api/resume/suggest-roles`;
    
    console.log(`Calling FastAPI endpoint: ${endpoint}`);
    console.log("With payload:", jsonData);
    
    // Forward request to the FastAPI backend with string resume_id
    const response = await fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Cookie": req.headers.get("cookie") || "",
      },
      body: JSON.stringify({
        resume_id: String(jsonData.resume_id)  // Ensure resume_id is a string
      }),
    });
    
    // Get the response
    const responseText = await response.text();
    let result;
    
    try {
      // Try to parse the response as JSON
      result = JSON.parse(responseText);
    } catch (parseError) {
      console.error("Error parsing API response:", parseError);
      console.error("Raw response:", responseText);
      return NextResponse.json(
        { detail: "Invalid response from API server" },
        { status: 500 }
      );
    }
    
    // Return error if response is not ok
    if (!response.ok) {
      console.error("API error:", result);
      return NextResponse.json(
        { detail: result.detail || "Failed to suggest roles" },
        { status: response.status }
      );
    }
    
    // Return the result
    return NextResponse.json(result);
  } catch (error) {
    console.error("Error in resume suggest-roles API route:", error);
    return NextResponse.json(
      { detail: "Internal server error" },
      { status: 500 }
    );
  }
}