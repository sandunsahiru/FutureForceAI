import { NextRequest, NextResponse } from 'next/server';

/**
 * API route to suggest job roles based on a newly uploaded resume
 * 
 * @param {NextRequest} req - The Next.js request object
 * @returns {NextResponse} - The Next.js response object
 */
export async function POST(req) {
  try {
    // Get the form data
    const formData = await req.formData();
    
    // Make sure we have a resume file
    if (!formData.get("resume_file")) {
      return NextResponse.json(
        { detail: "Resume file is required" },
        { status: 400 }
      );
    }
    
    // Forward request to the FastAPI backend
    const response = await fetch(`${process.env.API_BASE_URL}/resume/suggest-roles-upload`, {
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
        { detail: result.detail || "Failed to suggest roles" },
        { status: response.status }
      );
    }
    
    // Return the result
    return NextResponse.json(result);
  } catch (error) {
    console.error("Error in resume suggest-roles-upload API route:", error);
    return NextResponse.json(
      { detail: "Internal server error" },
      { status: 500 }
    );
  }
}