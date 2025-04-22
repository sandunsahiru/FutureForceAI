import { NextResponse } from 'next/server';
import { writeFile, mkdir } from 'fs/promises';
import { join } from 'path';
import jwt from 'jsonwebtoken';
import connectToDatabase from '@/lib/db';
import CV from '@/models/CV';
import mongoose from 'mongoose';

export async function POST(request) {
  console.log("==== POST /api/user/save-cv ====");
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

    // Parse the form data
    const formData = await request.formData();
    const cvFile = formData.get("cv_file");
    
    if (!cvFile) {
      console.error("No CV file provided");
      return NextResponse.json(
        { error: "No CV file provided" },
        { status: 400 }
      );
    }

    // Extract file information
    const bytes = await cvFile.arrayBuffer();
    const buffer = Buffer.from(bytes);
    
    // IMPORTANT: Create upload directory in the shared volume location
    const uploadDir = join(process.cwd(), 'uploads');
    try {
      await mkdir(uploadDir, { recursive: true });
      console.log(`Created upload directory: ${uploadDir}`);
    } catch (err) {
      // Directory might already exist, continue
      console.log(`Upload directory exists or error: ${err.message}`);
    }
    
    // Generate timestamp-based ID for consistent naming
    const timestamp = new Date();
    const timestampStr = timestamp.toISOString().replace(/[:.]/g, '-');
    const randomSuffix = Math.random().toString(36).substring(2, 8);
    const fileId = `${timestampStr}_${randomSuffix}`;
    
    // Clean the original filename to avoid spaces and special characters
    const cleanFileName = cvFile.name.replace(/[^a-zA-Z0-9.-]/g, '_');
    
    // Create consistent filename with timestamp
    const filename = `${fileId}_${cleanFileName}`;
    const filePath = join(uploadDir, filename);
    
    // IMPORTANT: Store container-consistent paths to fix path issues
    // This is the path that will be consistent across containers
    const containerFilePath = `/app/uploads/${filename}`;
    
    // Write file to disk
    await writeFile(filePath, buffer);
    console.log(`CV file saved to local path: ${filePath}`);
    console.log(`CV file container path: ${containerFilePath}`);
    
    // Connect to database
    await connectToDatabase();
    
    // Save to MongoDB with container-consistent path and timestamp ID
    const cvRecord = new CV({
      _id: new mongoose.Types.ObjectId(), // MongoDB still needs its own ObjectId
      userId: new mongoose.Types.ObjectId(userId),
      filename: filename,
      originalName: cvFile.name,
      fileSize: buffer.length,
      filePath: containerFilePath, // Use the container path here
      contentType: cvFile.type || 'application/octet-stream',
      extractedText: '', // Set empty for now, will be updated by FastAPI
      uploadedAt: timestamp,
      lastUsed: timestamp,
      fileId: fileId // Store the timestamp-based ID for reference
    });
    
    await cvRecord.save();
    console.log(`CV record saved to database with ID: ${cvRecord._id}`);
    console.log(`CV file ID (timestamp-based): ${fileId}`);
    
    // Also try to save CV to FastAPI for text extraction
    try {
      const fastApiUrl = process.env.FASTAPI_URL || "http://fastapi:8000";
      const endpoint = `${fastApiUrl}/api/cv/save-cv`;
      
      console.log(`Sending CV to FastAPI at ${endpoint}`);
      
      // Create a new FormData object to send to FastAPI
      const apiFormData = new FormData();
      
      // Create a new file object from the original file
      const file = new File([buffer], filename, {
        type: cvFile.type || 'application/octet-stream'
      });
      
      apiFormData.append("cv_file", file);
      apiFormData.append("cv_id", cvRecord._id.toString());
      apiFormData.append("file_id", fileId); // Send the timestamp ID too
      apiFormData.append("file_path", containerFilePath);
      
      // Include auth token
      const headers = {
        "Authorization": `Bearer ${token}`,
        "Cookie": `token=${token}`
      };
      
      // Send to FastAPI (synchronous to ensure file is processed)
      const response = await fetch(endpoint, {
        method: "POST",
        headers: headers,
        body: apiFormData
      });
      
      if (response.ok) {
        console.log("CV successfully sent to FastAPI");
        const data = await response.json();
        
        if (data && data.extracted_text) {
          // Update our MongoDB record with the extracted text
          console.log(`Received extracted text (${data.extracted_text.length} chars), updating MongoDB`);
          await CV.findByIdAndUpdate(
            cvRecord._id, 
            { extractedText: data.extracted_text }
          );
          console.log("CV record updated with extracted text");
        }
      } else {
        console.warn(`Failed to send CV to FastAPI, status: ${response.status}`);
        const errorText = await response.text();
        console.warn("Error details:", errorText);
      }
    } catch (apiErr) {
      console.error("Error calling FastAPI save-cv endpoint:", apiErr);
      // Continue anyway, we saved the CV locally
    }
    
    // Return success response
    console.log("==== END POST /api/user/save-cv ====");
    return NextResponse.json({
      success: true,
      cv: {
        id: cvRecord._id.toString(),
        filename: cvFile.name,
        size: buffer.length,
        uploadedAt: cvRecord.uploadedAt,
        lastUsed: cvRecord.lastUsed,
        fileId: fileId
      }
    });
  } catch (error) {
    console.error("Error saving CV:", error);
    return NextResponse.json(
      { error: `Failed to save CV: ${error.message}` },
      { status: 500 }
    );
  }
}