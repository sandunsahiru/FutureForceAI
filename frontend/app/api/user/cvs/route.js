import { NextResponse } from 'next/server';
import jwt from 'jsonwebtoken';
import connectToDatabase from '@/lib/db';
import CV from '@/models/CV';
import mongoose from 'mongoose';

export async function GET(request) {
  console.log("==== GET /api/user/cvs ====");
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
    
    // Connect to database
    await connectToDatabase();
    
    // Fetch user's CVs
    const cvs = await CV.find({ userId: new mongoose.Types.ObjectId(userId) })
      .sort({ lastUsed: -1 })
      .select('_id filename originalName fileSize uploadedAt lastUsed contentType')
      .limit(10);
    
    console.log(`Found ${cvs.length} CVs for user ${userId}`);
    
    // Format the response
    const formattedCVs = cvs.map(cv => ({
      id: cv._id.toString(),
      filename: cv.originalName || cv.filename,
      size: cv.fileSize,
      uploadedAt: cv.uploadedAt,
      lastUsed: cv.lastUsed,
      contentType: cv.contentType
    }));
    
    console.log("==== END GET /api/user/cvs ====");
    return NextResponse.json({ cvs: formattedCVs });
  } catch (error) {
    console.error('Error fetching CVs:', error);
    return NextResponse.json(
      { error: `Failed to fetch CVs: ${error.message}` },
      { status: 500 }
    );
  }
}