import { NextResponse } from 'next/server';
import { unlink } from 'fs/promises';
import { join } from 'path';
import fs from 'fs/promises';
import path from 'path';
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
    let cv;
    try {
      cv = await CV.findById(id);
    } catch (err) {
      console.error(`Error finding CV by ID: ${err.message}`);
      // Try as a string ID if ObjectId fails
      cv = await CV.findOne({ _id: id });
    }
    
    if (!cv) {
      console.log(`CV not found: ${id}`);
      return NextResponse.json({ error: 'CV not found' }, { status: 404 });
    }
    
    if (cv.userId.toString() !== userId) {
      console.error(`Unauthorized access: ${userId} trying to access CV ${id} owned by ${cv.userId}`);
      return NextResponse.json({ error: 'Unauthorized' }, { status: 403 });
    }
    
    // Get potential file paths from CV document
    const potentialPaths = [];
    
    // Primary path from database
    if (cv.filePath) {
      potentialPaths.push(cv.filePath);
    }
    
    // Check upload directory for files with matching patterns
    const uploadDir = join(process.cwd(), 'uploads');
    
    // Add timestamp-based path if available
    if (cv.fileId) {
      potentialPaths.push(join(uploadDir, `${cv.fileId}_${cv.originalName.replace(/[^a-zA-Z0-9.-]/g, '_')}`));
      potentialPaths.push(`/app/uploads/${cv.fileId}_${cv.originalName.replace(/[^a-zA-Z0-9.-]/g, '_')}`);
    }
    
    // Add path based on filename
    if (cv.filename) {
      potentialPaths.push(join(uploadDir, cv.filename));
      potentialPaths.push(`/app/uploads/${cv.filename}`);
    }
    
    // Try original name as fallback
    if (cv.originalName) {
      potentialPaths.push(join(uploadDir, cv.originalName));
      potentialPaths.push(`/app/uploads/${cv.originalName}`);
    }
    
    console.log("Potential file paths to delete:", potentialPaths);
    
    // Try to find and delete the file
    let fileDeleted = false;
    
    for (const filePath of potentialPaths) {
      try {
        // Check if file exists before attempting to delete
        await fs.access(filePath);
        await unlink(filePath);
        console.log(`Successfully deleted file: ${filePath}`);
        fileDeleted = true;
        break; // Exit loop once we've successfully deleted the file
      } catch (fileError) {
        console.log(`File not found at path: ${filePath}`);
        // Continue to next path
      }
    }
    
    if (!fileDeleted) {
      console.warn(`Could not find CV file to delete for ID: ${id}`);
      // Continue to delete the database record even if file not found
    }
    
    // Delete CV record from database
    await CV.findByIdAndDelete(id);
    console.log(`Deleted CV record: ${id}`);
    
    // Also search for any files in uploads folder that might match this CV
    try {
      const files = await fs.readdir(uploadDir);
      // Look for any files that might match by original name
      if (cv.originalName) {
        const originalNamePattern = cv.originalName.replace(/[^a-zA-Z0-9.-]/g, '_');
        const matchingFiles = files.filter(file => file.includes(originalNamePattern));
        
        for (const file of matchingFiles) {
          try {
            await unlink(join(uploadDir, file));
            console.log(`Deleted additional matching file: ${file}`);
          } catch (err) {
            console.log(`Error deleting matching file ${file}: ${err.message}`);
          }
        }
      }
    } catch (readDirErr) {
      console.log(`Error searching uploads directory: ${readDirErr.message}`);
    }
    
    console.log(`==== END DELETE /api/user/cv/${params.id} ====`);
    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Error deleting CV:', error);
    return NextResponse.json(
      { error: `Failed to delete CV: ${error.message}` },
      { status: 500 }
    );
  }
}