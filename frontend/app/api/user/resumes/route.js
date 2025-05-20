// File: app/api/user/resumes/route.js
import { NextResponse } from "next/server";
import jwt from "jsonwebtoken";
import connectToDatabase from '@/lib/db';
import CV from '@/models/CV';

export async function GET(request) {
  console.log("==== START API ROUTE HANDLER: /api/user/resumes ====");
  try {
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
    
    // Find all CVs owned by the user, sorted by lastUsed
    const cvRecords = await CV.find({ userId: userId })
      .sort({ lastUsed: -1 })
      .lean();
    
    console.log(`Found ${cvRecords.length} resumes for user: ${userId}`);
    
    // Transform the documents to match the frontend's expected format
    const resumes = cvRecords.map(cv => ({
      id: cv._id.toString(),
      filename: cv.originalName,
      originalName: cv.originalName,
      uploadedAt: cv.uploadedAt,
      size: cv.fileSize,
      userId: cv.userId
    }));
    
    return NextResponse.json({ resumes });
  } catch (error) {
    console.error("Unhandled error:", error);
    return NextResponse.json(
      { detail: "Server error: " + error.message },
      { status: 500 }
    );
  } finally {
    console.log("==== END API ROUTE HANDLER: /api/user/resumes ====");
  }
}