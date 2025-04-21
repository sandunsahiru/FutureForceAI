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
    
    // Create upload directory if it doesn't exist
    const uploadDir = join(process.cwd(), 'uploads');
    try {
      await mkdir(uploadDir, { recursive: true });
      console.log(`Created upload directory: ${uploadDir}`);
    } catch (err) {
      // Directory might already exist, continue
      console.log(`Upload directory exists or error: ${err.message}`);
    }
    
    // Generate unique filename
    const filename = `${new mongoose.Types.ObjectId().toString()}_${cvFile.name}`;
    const filePath = join(uploadDir, filename);
    
    // Write file to disk
    await writeFile(filePath, buffer);
    console.log(`CV file saved to: ${filePath}`);
    
    // Connect to database
    await connectToDatabase();
    
    // Try to extract text from CV - in a real app you'd have more robust extraction logic
    // For now, just save file metadata
    
    // Save to MongoDB
    const cvRecord = new CV({
      userId: new mongoose.Types.ObjectId(userId),
      filename: filename,
      originalName: cvFile.name,
      fileSize: buffer.length,
      filePath: filePath,
      contentType: cvFile.type || 'application/octet-stream',
      extractedText: '', // Set empty for now
      uploadedAt: new Date(),
      lastUsed: new Date()
    });
    
    await cvRecord.save();
    console.log(`CV record saved to database with ID: ${cvRecord._id}`);
    
    // Also try to save CV to FastAPI for redundancy
    try {
      const fastApiUrl = process.env.FASTAPI_URL || "http://fastapi:8000";
      const endpoint = `${fastApiUrl}/api/cv/save-cv`;
      
      const apiFormData = new FormData();
      apiFormData.append("cv_file", cvFile);
      
      const headers = {
        "Authorization": `Bearer ${token}`,
        "Cookie": `token=${token}`
      };
      
      fetch(endpoint, {
        method: "POST",
        headers: headers,
        body: apiFormData
      }).then(res => {
        if (res.ok) {
          console.log("CV also saved to FastAPI");
        } else {
          console.warn("Failed to save CV to FastAPI");
        }
      }).catch(err => {
        console.error("Error saving CV to FastAPI:", err);
      });
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
        lastUsed: cvRecord.lastUsed
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