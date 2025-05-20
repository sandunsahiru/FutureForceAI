// File: app/api/user/resumes/[id]/route.js
import { NextResponse } from "next/server";
import jwt from "jsonwebtoken";
import connectToDatabase from '@/lib/db';
import CV from '@/models/CV';
import { existsSync, unlinkSync } from 'fs';

export async function DELETE(request, { params }) {
  console.log(`==== START API ROUTE HANDLER: /api/user/resumes/${params.id} DELETE ====`);
  try {
    const resumeId = params.id;
    
    // Get token from cookies
    const tokenCookie = request.cookies.get("token");
    const token = tokenCookie?.value;
    
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
    
    // Connect to database
    await connectToDatabase();
    
    // Find the CV
    const cvRecord = await CV.findById(resumeId);
    
    if (!cvRecord) {
      console.error(`Resume not found: ${resumeId}`);
      return NextResponse.json(
        { detail: "Resume not found" },
        { status: 404 }
      );
    }
    
    // Check ownership
    if (cvRecord.userId.toString() !== userId) {
      console.error(`Unauthorized access to resume: ${resumeId}`);
      return NextResponse.json(
        { detail: "You don't have permission to delete this resume" },
        { status: 403 }
      );
    }
    
    // Delete physical file if it exists
    if (cvRecord.filePath && existsSync(cvRecord.filePath)) {
      try {
        unlinkSync(cvRecord.filePath);
        console.log(`Deleted file: ${cvRecord.filePath}`);
      } catch (fileErr) {
        console.error(`Error deleting file: ${fileErr}`);
        // Continue with deletion even if file removal fails
      }
    }
    
    // Delete from database
    await CV.findByIdAndDelete(resumeId);
    console.log(`Deleted resume: ${resumeId}`);
    
    return NextResponse.json({ success: true });
  } catch (error) {
    console.error("Unhandled error:", error);
    return NextResponse.json(
      { detail: "Server error: " + error.message },
      { status: 500 }
    );
  } finally {
    console.log(`==== END API ROUTE HANDLER: /api/user/resumes/${params.id} DELETE ====`);
  }
}