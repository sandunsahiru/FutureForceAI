import { NextResponse } from 'next/server';
import jwt from 'jsonwebtoken';

export async function GET(request, { params }) {
  const { id } = params;
  console.log(`==== GET /api/interview/session/${id} ====`);
  
  try {
    // Get the token cookie if available
    const tokenCookie = request.cookies.get("token");
    console.log("Token cookie:", tokenCookie ? "exists" : "not found");
    const token = tokenCookie?.value;
    
    if (!token) {
      console.error("Authentication error: No token found in cookies");
      return NextResponse.json(
        { error: "Authentication required" },
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
        { error: "Invalid authentication token" },
        { status: 401 }
      );
    }
    
    // Try to fetch from database first
    try {
      console.log("Trying to fetch session from database");
      
      // Connect to MongoDB and fetch the conversation
      const connectToDatabase = (await import('@/lib/db')).default;
      const Conversation = (await import('@/models/Conversation')).default;
      
      await connectToDatabase();
      
      // Query the conversation
      const conversation = await Conversation.findOne({ 
        session_id: id,
        user_id: userId
      });
      
      if (conversation) {
        console.log(`Found session ${id} in database`);
        
        // Format the response
        const sessionData = {
          session_id: conversation.session_id,
          job_role: conversation.job_role,
          created_at: conversation.createdAt?.toISOString(),
          finished: conversation.finished || false,
          messages: conversation.messages || [],
          max_questions: 5 // Default
        };
        
        return NextResponse.json(sessionData);
      }
      
      console.log("Session not found in database, trying FastAPI");
    } catch (dbError) {
      console.error("Database error:", dbError);
      console.log("Continuing to try FastAPI endpoint");
    }
    
    // If not found in database, try FastAPI
    // Set up API URL
    const fastApiUrl = process.env.FASTAPI_URL || "http://fastapi:8000";
    const endpoint = `${fastApiUrl}/api/interview/session/${id}`;
    
    // Forward request to FastAPI
    console.log(`Forwarding to: ${endpoint}`);
    
    // Include token in request headers
    const headers = {
      "Authorization": `Bearer ${token}`,
      "Cookie": `token=${token}`
    };
    
    try {
      const response = await fetch(endpoint, {
        method: "GET",
        headers: headers,
      });
      
      console.log(`FastAPI response status: ${response.status}`);
      
      // Handle error response
      if (!response.ok) {
        let errorDetail = "Failed to fetch session";
        try {
          const errorData = await response.json();
          errorDetail = errorData.detail || errorDetail;
        } catch (e) {
          console.error("Error parsing error response:", e);
        }
        
        return NextResponse.json(
          { error: errorDetail },
          { status: response.status }
        );
      }
      
      // Parse successful response
      const data = await response.json();
      console.log(`Retrieved session ${id} with ${data.messages?.length || 0} messages`);
      
      return NextResponse.json(data);
    } catch (fetchError) {
      console.error("Fetch error:", fetchError);
      
      // Session not found in database or FastAPI
      return NextResponse.json(
        { error: "Session not found" },
        { status: 404 }
      );
    }
  } catch (error) {
    console.error("Unhandled error:", error);
    return NextResponse.json(
      { error: `Server error: ${error.message}` },
      { status: 500 }
    );
  } finally {
    console.log(`==== END GET /api/interview/session/${id} ====`);
  }
}