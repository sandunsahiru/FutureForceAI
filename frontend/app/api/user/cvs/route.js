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
    
    // Log database connection and collections for debugging
    const collections = await mongoose.connection.db.listCollections().toArray();
    console.log("Available collections:", collections.map(c => c.name));
    
    try {
      // First try: direct query with Mongoose model
      const cvs = await CV.find({ 
        $or: [
          { userId: userId }, // String format
          { userId: new mongoose.Types.ObjectId(userId) }, // ObjectId format
          { user_id: userId } // Alternative field name
        ]
      })
      .sort({ lastUsed: -1 })
      .select('_id filename originalName fileSize uploadedAt lastUsed contentType fileId')
      .limit(20);
      
      if (cvs && cvs.length > 0) {
        console.log(`Found ${cvs.length} CVs for user ${userId} using Mongoose model`);
        
        // Format the response
        const formattedCVs = cvs.map(cv => ({
          id: cv._id.toString(),
          filename: cv.originalName || cv.filename,
          size: cv.fileSize || 0,
          uploadedAt: cv.uploadedAt || new Date(),
          lastUsed: cv.lastUsed || new Date(),
          contentType: cv.contentType || "application/octet-stream",
          fileId: cv.fileId || undefined  // Include fileId if available
        }));
        
        console.log("==== END GET /api/user/cvs ====");
        return NextResponse.json({ cvs: formattedCVs });
      }
      
      // Second try: Direct MongoDB collection query without model
      console.log("No CVs found with Mongoose model, trying direct collection query");
      const db = mongoose.connection.db;
      
      // Try different collections that might contain CVs
      const collectionsToCheck = ["cvs", "CV", "cv"];
      let allCvs = [];
      
      for (const collectionName of collectionsToCheck) {
        if (db.collection(collectionName)) {
          const collection = db.collection(collectionName);
          
          // Try different field name patterns
          const results = await collection.find({
            $or: [
              { userId: userId }, // String format
              { userId: new mongoose.Types.ObjectId(userId) }, // ObjectId format
              { user_id: userId } // Alternative field name
            ]
          }).sort({ lastUsed: -1, uploadedAt: -1 }).limit(20).toArray();
          
          if (results && results.length > 0) {
            console.log(`Found ${results.length} CVs in collection '${collectionName}'`);
            allCvs = [...allCvs, ...results];
          }
        }
      }
      
      if (allCvs.length > 0) {
        // Format the response
        const formattedCVs = allCvs.map(cv => ({
          id: cv._id.toString(),
          filename: cv.originalName || cv.filename || "Unnamed CV",
          size: cv.fileSize || 0,
          uploadedAt: cv.uploadedAt || cv.uploaded_at || new Date(),
          lastUsed: cv.lastUsed || cv.last_used || new Date(),
          contentType: cv.contentType || cv.content_type || "application/octet-stream",
          fileId: cv.fileId || undefined  // Include fileId if available
        }));
        
        console.log(`Found ${formattedCVs.length} CVs for user ${userId} using direct collection query`);
        console.log("==== END GET /api/user/cvs ====");
        return NextResponse.json({ cvs: formattedCVs });
      }
      
      // No CVs found in any collection
      console.log(`Found 0 CVs for user ${userId}`);
      console.log("==== END GET /api/user/cvs ====");
      return NextResponse.json({ cvs: [] });
      
    } catch (dbError) {
      console.error('Database query error:', dbError);
      
      // If Mongoose query fails, try direct MongoDB query
      try {
        console.log("Trying direct MongoDB query as fallback");
        const db = mongoose.connection.db;
        const collection = db.collection('cvs');
        
        const results = await collection.find({
          $or: [
            { userId: userId },
            { userId: new mongoose.Types.ObjectId(userId) },
            { user_id: userId }
          ]
        }).toArray();
        
        console.log(`Found ${results.length} CVs with direct MongoDB query`);
        
        // Format the response
        const formattedCVs = results.map(cv => ({
          id: cv._id.toString(),
          filename: cv.originalName || cv.filename || "Unnamed CV",
          size: cv.fileSize || 0,
          uploadedAt: cv.uploadedAt || new Date(),
          lastUsed: cv.lastUsed || new Date(),
          contentType: cv.contentType || "application/octet-stream",
          fileId: cv.fileId || undefined
        }));
        
        console.log("==== END GET /api/user/cvs ====");
        return NextResponse.json({ cvs: formattedCVs });
      } catch (fallbackError) {
        console.error('Fallback query failed:', fallbackError);
        return NextResponse.json({ cvs: [] });
      }
    }
    
  } catch (error) {
    console.error('Error fetching CVs:', error);
    return NextResponse.json(
      { error: `Failed to fetch CVs: ${error.message}` },
      { status: 500 }
    );
  }
}