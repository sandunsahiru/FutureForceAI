import { NextResponse } from "next/server";
import connectToDatabase from "@/lib/db";
import User from "@/models/User";
import bcrypt from "bcryptjs";
import jwt from "jsonwebtoken";

export async function POST(request) {
  try {
    // Add this at the top of your POST function
console.log("==== JWT SECRET DEBUG INFO ====");
console.log("JWT_SECRET:", process.env.JWT_SECRET || "(not set)");
if (process.env.JWT_SECRET) {
  console.log("Secret length:", process.env.JWT_SECRET.length);
  console.log("First 3 chars:", process.env.JWT_SECRET.substring(0, 3));
  console.log("Last 3 chars:", process.env.JWT_SECRET.substring(process.env.JWT_SECRET.length - 3));
}
console.log("==============================");

    const { email, password } = await request.json();

    if (!email || !password) {
      return NextResponse.json({ error: "Missing email or password" }, { status: 400 });
    }

    await connectToDatabase();
    const user = await User.findOne({ email });
    if (!user) {
      return NextResponse.json({ error: "Invalid credentials" }, { status: 401 });
    }

    const isMatch = await bcrypt.compare(password, user.passwordHash);
    if (!isMatch) {
      return NextResponse.json({ error: "Invalid credentials" }, { status: 401 });
    }

    // Create JWT
    const token = jwt.sign({ userId: user._id.toString() }, process.env.JWT_SECRET, {
      expiresIn: "1h",
    });

    const response = NextResponse.json({ message: "Login successful" });
    response.cookies.set("token", token, {
      httpOnly: true,
      sameSite: "lax", // Use "lax" for local development
      maxAge: 60 * 60, // 1 hour
      path: "/",
      secure: false, // For local development, secure must be false
    });

    return response;
  } catch (error) {
    console.error("Login error:", error);
    return NextResponse.json({ error: "Server error" }, { status: 500 });
  }
}