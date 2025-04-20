import { NextResponse } from "next/server";
import jwt from "jsonwebtoken";

export async function POST(request) {
  console.log("==== START OF API ROUTE HANDLER ====");
  try {
    // Get the token cookie if available
    const tokenCookie = request.cookies.get("token");
    console.log("Token cookie:", tokenCookie ? "exists" : "not found");
    const token = tokenCookie?.value;
    
    if (!token) {
      console.error("Authentication error: No token found in cookies");
      return NextResponse.json(
        { detail: "Authentication required" },
        { status: 401 }
      );
    }

    // Verify token
    try {
      const decoded = jwt.verify(token, process.env.JWT_SECRET);
      console.log("Token verified for user:", decoded.userId);
    } catch (jwtError) {
      console.error("Invalid token:", jwtError);
      return NextResponse.json(
        { detail: "Invalid authentication token" },
        { status: 401 }
      );
    }
    
    // Get the form data from the request
    console.log("Attempting to extract form data from request");
    const formData = await request.formData();
    console.log("Form data keys:", [...formData.keys()]);
    
    // Log all form data fields
    console.log("Form data contents:");
    for (const [key, value] of formData.entries()) {
      if (value instanceof File) {
        console.log(`${key}: [File] name=${value.name}, size=${value.size}, type=${value.type}`);
      } else {
        console.log(`${key}: ${value}`);
      }
    }
    
    // Set up API URL
    const fastApiUrl = process.env.FASTAPI_URL || "http://fastapi:8000";
    console.log(`Using FastAPI URL: ${fastApiUrl}`);
    console.log(`Forwarding to: ${fastApiUrl}/api/interview/start`);
    
    // Create a new FormData to forward
    console.log("Creating new FormData for forwarding");
    const apiFormData = new FormData();
    
    // Copy all fields from the original formData
    for (const [key, value] of formData.entries()) {
      apiFormData.append(key, value);
      console.log(`Added form field to API request: ${key}`);
    }
    
    // Add the token as a field in the FormData
    // This is a workaround for FastAPI to receive the token
    apiFormData.append("auth_token", token);
    
    // Set headers - we're still sending the cookie, but also including the token in the form data
    const headers = {
      "Authorization": `Bearer ${token}`,  // Add Authorization header
      "Cookie": `token=${token}`
    };
    console.log("Request headers:", headers);
    
    try {
      // Send the request to FastAPI
      console.log("Sending fetch request to FastAPI");
      const response = await fetch(`${fastApiUrl}/api/interview/start`, {
        method: "POST",
        headers: headers,
        body: apiFormData,
      });
      
      console.log(`FastAPI response status: ${response.status} ${response.statusText}`);
      
      // If the response is not OK, handle the error
      if (!response.ok) {
        console.error(`Error response from FastAPI: ${response.status}`);
        
        // Try to get error details from response
        let errorDetail = "Failed to start interview";
        try {
          const errorData = await response.json();
          errorDetail = errorData.detail || errorDetail;
        } catch (e) {
          // If can't parse JSON, try to get text
          try {
            errorDetail = await response.text();
          } catch (textErr) {
            console.error("Error getting response text:", textErr);
          }
        }
        
        // If it's an auth error from the backend, return 401
        if (response.status === 401) {
          return NextResponse.json(
            { detail: errorDetail },
            { status: 401 }
          );
        }
        
        return NextResponse.json(
          { detail: errorDetail },
          { status: response.status }
        );
      }
      
      // Try to parse the response as JSON
      try {
        const data = await response.json();
        console.log("Successfully parsed response:", data);
        
        // Make sure we have the expected data structure
        if (!data.session_id || !data.first_ai_message) {
          console.error("Incomplete data from API:", data);
          
          // Provide a fallback response structure if needed
          const completeData = {
            session_id: data.session_id || `fallback-${Date.now()}`,
            first_ai_message: data.first_ai_message || {
              sender: "ai",
              text: "Welcome to the interview. Can you tell me about yourself?"
            }
          };
          
          return NextResponse.json(completeData);
        }
        
        return NextResponse.json(data);
      } catch (parseError) {
        console.error("Error parsing response:", parseError);
        
        // If we can't parse the JSON, create a fallback response
        return NextResponse.json(
          {
            session_id: `fallback-${Date.now()}`,
            first_ai_message: {
              sender: "ai",
              text: "Welcome to the interview. Can you tell me about yourself?"
            }
          }
        );
      }
    } catch (fetchError) {
      console.error("Fetch error:", fetchError);
      
      // If the backend is completely unavailable, use a fallback
      const fallbackResponse = {
        session_id: `fallback-${Date.now()}`,
        first_ai_message: {
          sender: "ai",
          text: "Welcome to the interview. Due to a temporary issue connecting to our AI service, we'll proceed with a simulation. Can you tell me about yourself?"
        }
      };
      
      console.log("Using fallback response:", fallbackResponse);
      return NextResponse.json(fallbackResponse);
    }
  } catch (error) {
    console.error("Unhandled error in route handler:", error);
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
    console.log("==== END OF API ROUTE HANDLER ====");
  }
}