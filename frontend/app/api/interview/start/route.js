import { NextResponse } from "next/server";
import jwt from "jsonwebtoken";
import connectToDatabase from '@/lib/db';
import CV from '@/models/CV';
import mongoose from 'mongoose';
import { writeFile, mkdir, readFile } from 'fs/promises';
import { join } from 'path';
import { existsSync } from 'fs';

export async function POST(request) {
  console.log("==== START API ROUTE HANDLER: /api/interview/start ====");
  try {
    // Check if the request is multipart/form-data or application/json
    const contentType = request.headers.get("content-type") || "";
    console.log(`Content type: ${contentType}`);
    
    // Log all headers for debugging
    console.log("Request headers:", Object.fromEntries([...request.headers.entries()]));
    
    // Get the token from cookies or headers
    const tokenCookie = request.cookies.get("token");
    const token = tokenCookie?.value;
    console.log("Token from cookies:", token ? "found" : "not found");
    
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
    
    // Check if this is a JSON request (for saved CV)
    if (contentType.includes("application/json")) {
      console.log("Processing JSON request for saved CV");
      const jsonData = await request.json();
      console.log("Received JSON data:", jsonData);
      
      const { cv_id, job_role } = jsonData;
      
      if (!cv_id || !job_role) {
        console.error("Missing required fields in JSON payload");
        return NextResponse.json(
          { detail: "CV ID and job role are required" },
          { status: 400 }
        );
      }
      
      // Forward request to FastAPI saved CV endpoint
      const fastApiUrl = process.env.FASTAPI_URL || "http://fastapi:8000";
      const endpoint = `${fastApiUrl}/api/interview/start-with-saved-cv`;
      
      console.log(`Calling FastAPI saved CV endpoint: ${endpoint}`);
      
      // Include token in multiple ways to ensure it's received
      const response = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`,
          "Cookie": `token=${token}`
        },
        body: JSON.stringify({
          cv_id,
          job_role,
          user_id: userId
        }),
        credentials: 'include'
      });
      
      console.log(`FastAPI response status: ${response.status}`);
      
      // Handle error responses
      if (!response.ok) {
        let errorDetail = "Failed to start interview with saved CV";
        try {
          const errorData = await response.json();
          console.error("Error response data:", errorData);
          errorDetail = errorData.detail || errorDetail;
        } catch (e) {
          try {
            const errorText = await response.text();
            console.error("Error response text:", errorText);
            errorDetail = errorText || errorDetail;
          } catch (textErr) {}
        }
        
        return NextResponse.json(
          { detail: errorDetail },
          { status: response.status }
        );
      }
      
      // Return successful response
      const data = await response.json();
      console.log("Successful response data:", data);
      return NextResponse.json(data);
    }
    // Handle form data requests
    else if (contentType.includes("multipart/form-data")) {
      console.log("Processing form data request");
      const formData = await request.formData();
      console.log("Form data keys received:", [...formData.keys()]);
      
      // Extract required parameters
      const cvId = formData.get("cv_id");
      const cvFile = formData.get("cv_file");
      const jobRole = formData.get("job_role");
      
      // Validate required parameters
      if (!jobRole) {
        console.error("Missing job_role in request");
        return NextResponse.json(
          { detail: "Job role is required" },
          { status: 400 }
        );
      }
      
      if (!cvFile && !cvId) {
        console.error("Neither cv_id nor cv_file provided");
        return NextResponse.json(
          { detail: "Either CV ID or CV file must be provided" },
          { status: 400 }
        );
      }
      
      console.log(`Processing request for job role: ${jobRole}`);
      
      // Create a new FormData object specifically for FastAPI
      const fastApiFormData = new FormData();
      
      // Add job role first (important!)
      fastApiFormData.append("job_role", jobRole);
      
      // Connect to database
      await connectToDatabase();
      
      let cvRecord = null;
      
      // Handle CV processing based on whether we have an ID or file
      if (cvId) {
        console.log(`Using existing CV with ID: ${cvId}`);
        cvRecord = await CV.findById(cvId);
        
        if (!cvRecord || cvRecord.userId.toString() !== userId) {
          console.error(`CV not found or not owned by user: ${cvId}`);
          return NextResponse.json(
            { detail: "CV not found or unauthorized" },
            { status: 404 }
          );
        }
        
        console.log(`Found CV record: ${cvRecord.originalName}`);
        
        // Update lastUsed timestamp
        cvRecord.lastUsed = new Date();
        await cvRecord.save();
        
        // If we have a file path, read the file
        if (cvRecord.filePath && existsSync(cvRecord.filePath)) {
          try {
            const fileBuffer = await readFile(cvRecord.filePath);
            const file = new File([fileBuffer], cvRecord.originalName, { 
              type: cvRecord.contentType || 'application/pdf' 
            });
            fastApiFormData.append("cv_file", file);
            console.log(`Added CV file to request: ${cvRecord.originalName}`);
            
            // Also append cv_id for reference
            fastApiFormData.append("cv_id", cvId.toString());
          } catch (fileErr) {
            console.error(`Error reading CV file: ${fileErr}`);
            return NextResponse.json(
              { detail: "Error reading CV file" },
              { status: 500 }
            );
          }
        } else {
          console.error("CV file not found on disk");
          return NextResponse.json(
            { detail: "CV file not found" },
            { status: 404 }
          );
        }
      } else {
        // Using uploaded CV file
        console.log(`Using uploaded CV file: ${cvFile.name}`);
        
        // Add the file directly to the FastAPI form data
        fastApiFormData.append("cv_file", cvFile);
        console.log(`Added CV file to request: ${cvFile.name}`);
        
        // Check if we should save the CV for future use
        const saveCV = formData.get("save_cv") === "true";
        if (saveCV) {
          console.log("Saving uploaded CV to database");
          
          try {
            // Convert file to buffer for saving
            const bytes = await cvFile.arrayBuffer();
            const buffer = Buffer.from(bytes);
            
            // Create upload directory if it doesn't exist
            const uploadDir = join(process.cwd(), 'uploads');
            await mkdir(uploadDir, { recursive: true });
            
            // Generate unique filename
            const filename = `${new mongoose.Types.ObjectId().toString()}_${cvFile.name}`;
            const filePath = join(uploadDir, filename);
            
            // Write file to disk
            await writeFile(filePath, buffer);
            console.log(`Saved CV to disk: ${filePath}`);
            
            // Create CV record in database
            cvRecord = new CV({
              userId: new mongoose.Types.ObjectId(userId),
              filename: filename,
              originalName: cvFile.name,
              fileSize: buffer.length,
              filePath: filePath,
              contentType: cvFile.type || 'application/octet-stream',
              uploadedAt: new Date(),
              lastUsed: new Date()
            });
            
            await cvRecord.save();
            console.log(`Saved CV to database with ID: ${cvRecord._id}`);
          } catch (saveErr) {
            console.error("Error saving CV to database:", saveErr);
            // Continue with the interview even if saving fails
          }
        }
      }
      
      // Add authentication token to the form data
      fastApiFormData.append("auth_token", token);
      
      // Set up FastAPI URL 
      const fastApiUrl = process.env.FASTAPI_URL || "http://fastapi:8000";
      const endpoint = `${fastApiUrl}/api/interview/start`;
      console.log(`Forwarding request to: ${endpoint}`);
      
      // Set up headers - include token in multiple ways
      const headers = {
        "Authorization": `Bearer ${token}`,
        "Cookie": `token=${token}`
      };
      
      // Log what we're sending
      console.log("Form data keys being sent to FastAPI:", [...fastApiFormData.keys()]);
      
      // Make the request to FastAPI
      console.log("Sending request to FastAPI...");
      const response = await fetch(endpoint, {
        method: "POST",
        headers: headers,
        body: fastApiFormData,
        credentials: 'include'
      });
      
      console.log(`FastAPI response status: ${response.status} ${response.statusText}`);
      
      // Handle error responses
      if (!response.ok) {
        console.error(`Error response from FastAPI: ${response.status}`);
        
        // Try to get detailed error message
        let errorDetail = "Failed to start interview";
        try {
          const errorData = await response.json();
          console.error("Error details:", errorData);
          errorDetail = errorData.detail || errorDetail;
        } catch (parseErr) {
          try {
            errorDetail = await response.text();
            console.error("Error text:", errorDetail);
          } catch (textErr) {
            console.error("Could not parse error details:", textErr);
          }
        }
        
        // Return appropriate error status
        return NextResponse.json(
          { detail: errorDetail },
          { status: response.status }
        );
      }
      
      // Parse successful response
      try {
        const data = await response.json();
        console.log("Successfully received response from FastAPI:", data);
        
        // Add CV ID to response if we saved one
        if (cvRecord) {
          data.cv_id = cvRecord._id.toString();
        }
        
        return NextResponse.json(data);
      } catch (parseErr) {
        console.error("Error parsing FastAPI response:", parseErr);
        
        // Provide a fallback response
        const fallbackResponse = {
          session_id: `fallback-${Date.now()}`,
          first_ai_message: {
            sender: "ai",
            text: "Welcome to the interview. Can you tell me about yourself?"
          }
        };
        
        if (cvRecord) {
          fallbackResponse.cv_id = cvRecord._id.toString();
        }
        
        return NextResponse.json(fallbackResponse);
      }
    }
    else {
      console.error(`Unsupported content type: ${contentType}`);
      return NextResponse.json(
        { detail: "Unsupported content type" },
        { status: 400 }
      );
    }
  } catch (error) {
    console.error("Unhandled error in route handler:", error);
    
    // Provide error response with fallback interview starter
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
    console.log("==== END API ROUTE HANDLER: /api/interview/start ====");
  }
}