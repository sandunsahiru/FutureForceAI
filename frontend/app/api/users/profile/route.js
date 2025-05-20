// app/api/users/profile/route.js
import { NextResponse } from "next/server";
import connectToDatabase from "../../../../lib/db";
import User from "../../../../models/User";
import jwt from "jsonwebtoken";

// Helper function to extract user ID from JWT token
const getUserIdFromToken = (request) => {
  try {
    const token = request.cookies.get("token")?.value;
    if (!token) return null;
    
    const decoded = jwt.verify(token, process.env.JWT_SECRET);
    return decoded.userId;
  } catch (error) {
    console.error("Error decoding token:", error);
    return null;
  }
};

// GET: Fetch the user's profile
export async function GET(request) {
  try {
    const userId = getUserIdFromToken(request);
    
    if (!userId) {
      return NextResponse.json(
        { error: "Not authenticated" },
        { status: 401 }
      );
    }
    
    await connectToDatabase();
    
    const user = await User.findById(userId).select("-passwordHash");
    
    if (!user) {
      return NextResponse.json(
        { error: "User not found" },
        { status: 404 }
      );
    }
    
    return NextResponse.json({
      fullName: user.fullName,
      email: user.email,
      careerInterest: user.careerInterest,
      experience: user.experience,
      createdAt: user.createdAt
    });
  } catch (error) {
    console.error("Error fetching profile:", error);
    return NextResponse.json(
      { error: "Server error" },
      { status: 500 }
    );
  }
}

// PUT: Update the user's profile
export async function PUT(request) {
  try {
    const userId = getUserIdFromToken(request);
    
    if (!userId) {
      return NextResponse.json(
        { error: "Not authenticated" },
        { status: 401 }
      );
    }
    
    const data = await request.json();
    
    // Validate input data
    if (!data.fullName) {
      return NextResponse.json(
        { error: "Full name is required" },
        { status: 400 }
      );
    }
    
    if (!data.careerInterest) {
      return NextResponse.json(
        { error: "Career interest is required" },
        { status: 400 }
      );
    }
    
    await connectToDatabase();
    
    // Find the user and update their profile
    // Note: We don't allow email to be updated
    const updatedUser = await User.findByIdAndUpdate(
      userId,
      {
        fullName: data.fullName,
        careerInterest: data.careerInterest,
        experience: data.experience || 0, // Default to 0 if not provided
      },
      { new: true, runValidators: true }
    ).select("-passwordHash");
    
    if (!updatedUser) {
      return NextResponse.json(
        { error: "User not found" },
        { status: 404 }
      );
    }
    
    return NextResponse.json({
      fullName: updatedUser.fullName,
      email: updatedUser.email,
      careerInterest: updatedUser.careerInterest,
      experience: updatedUser.experience,
    });
  } catch (error) {
    console.error("Error updating profile:", error);
    return NextResponse.json(
      { error: "Server error" },
      { status: 500 }
    );
  }
}