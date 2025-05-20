// File: app/api/resume/download-optimized/route.js
import { NextRequest, NextResponse } from 'next/server';

/**
 * API route to download an optimized resume
 * 
 * @param {NextRequest} req - The Next.js request object
 * @returns {NextResponse} - The Next.js response object
 */
export async function POST(req) {
  try {
    // Get the JSON data
    const jsonData = await req.json();
    
    // Make sure we have required fields
    if (!jsonData.optimized_id) {
      return NextResponse.json(
        { detail: "Optimized resume ID is required" },
        { status: 400 }
      );
    }
    
    // Set up the API URL from environment variables
    const apiBaseUrl = process.env.API_BASE_URL || "http://fastapi:8000";
    const endpoint = `${apiBaseUrl}/api/resume/download-optimized`;  // Updated to include '/api/' prefix
    
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
        optimized_id: jsonData.optimized_id
      }),
    });
    
    // Check if the response is a PDF file
    const contentType = response.headers.get('content-type');
    if (contentType?.includes('application/pdf')) {
      // Get the PDF data
      const blob = await response.blob();
      
      // Return the PDF directly
      return new Response(blob, {
        status: 200,
        headers: {
          'Content-Type': 'application/pdf',
          'Content-Disposition': `attachment; filename="${jsonData.optimized_id}.pdf"`
        }
      });
    }
    
    // If it's not a PDF, try to process as JSON
    try {
      const result = await response.json();
      
      // Return error if response is not ok
      if (!response.ok) {
        return NextResponse.json(
          { detail: result.detail || "Failed to download optimized resume" },
          { status: response.status }
        );
      }
      
      // Return the result
      return NextResponse.json(result);
    } catch (e) {
      // If it's not JSON either, return the raw response
      const text = await response.text();
      return NextResponse.json(
        { detail: "Invalid response from server", raw: text },
        { status: 500 }
      );
    }
  } catch (error) {
    console.error("Error in resume download-optimized API route:", error);
    return NextResponse.json(
      { detail: "Internal server error" },
      { status: 500 }
    );
  }
}