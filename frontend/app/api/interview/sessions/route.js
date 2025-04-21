import { NextResponse } from 'next/server';
import jwt from 'jsonwebtoken';

export async function GET(request) {
  console.log("==== GET /api/interview/sessions ====");
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
    
    // Set up API URL
    const fastApiUrl = process.env.FASTAPI_URL || "http://fastapi:8000";
    const endpoint = `${fastApiUrl}/api/interview/sessions`;
    
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
        // If the endpoint doesn't exist yet, create mock data
        if (response.status === 404) {
          console.log("Sessions endpoint not found, using database query instead");
          
          // Connect to MongoDB and fetch conversations directly
          const connectToDatabase = (await import('@/lib/db')).default;
          const Conversation = (await import('@/models/Conversation')).default;
          
          await connectToDatabase();
          
          // Query the conversations collection
          const conversations = await Conversation.find({ user_id: userId })
            .sort({ createdAt: -1 })
            .limit(10);
          
          // Format the data
          const sessions = conversations.map(convo => ({
            id: convo.session_id,
            job_role: convo.job_role,
            created_at: convo.createdAt?.toISOString(),
            finished: convo.finished || false,
            message_count: convo.messages?.length || 0
          }));
          
          console.log(`Found ${sessions.length} sessions in database`);
          return NextResponse.json({ sessions });
        }
        
        let errorDetail = "Failed to fetch sessions";
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
      console.log(`Retrieved ${data.sessions?.length || 0} sessions`);
      
      return NextResponse.json(data);
    } catch (fetchError) {
      console.error("Fetch error:", fetchError);
      
      // For development - try to directly query the database
      try {
        console.log("Fetch failed, trying to query database directly");
        
        // Connect to MongoDB and fetch conversations directly
        const connectToDatabase = (await import('@/lib/db')).default;
        const Conversation = (await import('@/models/Conversation')).default;
        
        await connectToDatabase();
        
        // Query the conversations collection
        const conversations = await Conversation.find({ user_id: userId })
          .sort({ createdAt: -1 })
          .limit(10);
        
        // Format the data
        const sessions = conversations.map(convo => ({
          id: convo.session_id,
          job_role: convo.job_role,
          created_at: convo.createdAt?.toISOString(),
          finished: convo.finished || false,
          message_count: convo.messages?.length || 0
        }));
        
        console.log(`Found ${sessions.length} sessions in database`);
        return NextResponse.json({ sessions });
      } catch (dbError) {
        console.error("Database error:", dbError);
        
        // Last resort - return empty sessions array
        return NextResponse.json({ sessions: [] });
      }
    }
  } catch (error) {
    console.error("Unhandled error:", error);
    return NextResponse.json(
      { error: `Server error: ${error.message}` },
      { status: 500 }
    );
  } finally {
    console.log("==== END GET /api/interview/sessions ====");
  }
}