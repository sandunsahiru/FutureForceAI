import { NextResponse } from 'next/server';
import { unlink } from 'fs/promises';
import jwt from 'jsonwebtoken';
import connectToDatabase from '@/lib/db';
import CV from '@/models/CV';
import mongoose from 'mongoose';

export async function DELETE(request, { params }) {
  console.log(`==== DELETE /api/user/cv/${params.id} ====`);
  try {
    const { id } = params;
    
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
    
    // Find CV and verify ownership
    const cv = await CV.findById(id);
    if (!cv) {
      console.log(`CV not found: ${id}`);
      return NextResponse.json({ error: 'CV not found' }, { status: 404 });
    }
    
    if (cv.userId.toString() !== userId) {
      console.error(`Unauthorized access: ${userId} trying to access CV ${id} owned by ${cv.userId}`);
      return NextResponse.json({ error: 'Unauthorized' }, { status: 403 });
    }
    
    // Try to delete the physical file if a path exists
    try {
      if (cv.filePath) {
        await unlink(cv.filePath);
        console.log(`Deleted file: ${cv.filePath}`);
      }
    } catch (fileError) {
      console.error(`Error deleting file ${cv.filePath}:`, fileError);
      // Continue anyway - we'll still delete the DB record
    }
    
    // Delete CV from database
    await CV.findByIdAndDelete(id);
    console.log(`Deleted CV record: ${id}`);
    
    console.log(`==== END DELETE /api/user/cv/${params.id} ====`);
    return NextResponse.json({ message: 'CV deleted successfully' });
  } catch (error) {
    console.error('Error deleting CV:', error);
    return NextResponse.json(
      { error: `Failed to delete CV: ${error.message}` },
      { status: 500 }
    );
  }
}