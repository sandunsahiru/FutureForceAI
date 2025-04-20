import { NextResponse } from "next/server";

export async function POST(request) {
  console.log("==== CHAT API ROUTE HANDLER START ====");
  try {
    // Parse the JSON body
    const body = await request.json();
    console.log("Chat request received:", body);
    
    // Validate the request body
    if (!body.session_id) {
      console.error("Missing session_id in request");
      return NextResponse.json(
        { detail: "Missing session_id" },
        { status: 400 }
      );
    }
    
    if (!body.user_message) {
      console.error("Missing user_message in request");
      return NextResponse.json(
        { detail: "Missing user_message" },
        { status: 400 }
      );
    }
    
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
    
    // Set up API URL and headers
    const fastApiUrl = process.env.FASTAPI_URL || "http://fastapi:8000";
    const headers = {
      "Content-Type": "application/json",
      "Cookie": `token=${token}`
    };
    
    console.log(`Forwarding to: ${fastApiUrl}/api/interview/chat`);
    
    try {
      // Make the request to FastAPI
      const response = await fetch(`${fastApiUrl}/api/interview/chat`, {
        method: "POST",
        headers: headers,
        body: JSON.stringify(body),
      });
      
      console.log(`FastAPI response status: ${response.status} ${response.statusText}`);
      
      // Handle error responses
      if (!response.ok) {
        console.error(`Error response from FastAPI: ${response.status}`);
        
        // Try to get error details
        let errorDetail = "Failed to process chat message";
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
        
        return NextResponse.json(
          { detail: errorDetail },
          { status: response.status }
        );
      }
      
      // Parse the successful response
      try {
        const data = await response.json();
        console.log("Successfully parsed response:", data);
        
        // Check if we have the expected messages array
        if (!data.messages || !Array.isArray(data.messages)) {
          console.error("Incomplete data from API:", data);
          
          // Create fallback messages if needed
          const fallbackMessages = [
            { 
              sender: "ai", 
              text: "I received your message, but there was an issue processing it. Could you please continue?" 
            }
          ];
          
          return NextResponse.json({ messages: fallbackMessages });
        }
        
        return NextResponse.json(data);
      } catch (parseError) {
        console.error("Error parsing response:", parseError);
        
        // Fallback if we can't parse the JSON
        const fallbackMessages = [
          { 
            sender: "ai", 
            text: "I received your message, but there was an issue with our system. Let's continue the interview. What skills do you have that are relevant to this position?" 
          }
        ];
        
        return NextResponse.json({ messages: fallbackMessages });
      }
    } catch (fetchError) {
      console.error("Fetch error:", fetchError);
      
      // If backend is completely unavailable
      const existingMessages = [
        { sender: "user", text: body.user_message },
        { 
          sender: "ai", 
          text: "Thank you for your response. Due to technical difficulties, I'm unable to provide a personalized reply, but please continue with the interview. Can you tell me about a challenging project you've worked on?" 
        }
      ];
      
      return NextResponse.json({ messages: existingMessages });
    }
  } catch (error) {
    console.error("Unhandled error in chat route handler:", error);
    return NextResponse.json(
      { 
        detail: "Server error: " + error.message,
        messages: [
          { 
            sender: "ai", 
            text: "Sorry, there was an error processing your message. Please try again." 
          }
        ]
      },
      { status: 500 }
    );
  } finally {
    console.log("==== CHAT API ROUTE HANDLER END ====");
  }
}