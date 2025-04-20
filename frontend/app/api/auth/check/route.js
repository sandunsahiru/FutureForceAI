import { NextResponse } from "next/server";
import jwt from "jsonwebtoken";

export async function GET(request) {
  try {
    // Get the token from cookies
    const token = request.cookies.get("token")?.value;
    
    // If no token exists, return unauthorized
    if (!token) {
      console.log("No auth token found");
      return NextResponse.json(
        { authenticated: false, message: "No authentication token found" },
        { status: 401 }
      );
    }
    
    // Verify the token
    try {
      const decoded = jwt.verify(token, process.env.JWT_SECRET);
      console.log("Auth check successful for user:", decoded.userId);
      
      return NextResponse.json({
        authenticated: true,
        userId: decoded.userId
      });
    } catch (jwtError) {
      console.error("JWT verification error:", jwtError);
      return NextResponse.json(
        { authenticated: false, message: "Invalid token" },
        { status: 401 }
      );
    }
  } catch (error) {
    console.error("Auth check error:", error);
    return NextResponse.json(
      { authenticated: false, message: "Server error" },
      { status: 500 }
    );
  }
}