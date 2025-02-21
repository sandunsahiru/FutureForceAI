// frontend/app/api/register/route.js
import { NextResponse } from 'next/server';
import connectToDatabase from '@/lib/db';
import User from '@/models/User';
import bcrypt from 'bcryptjs';

export async function POST(request) {
  try {
    const body = await request.json();
    const { fullName, email, password, careerInterest, experience } = body;

    // Validate required fields
    if (!fullName || !email || !password || !careerInterest) {
      return NextResponse.json({ error: 'Missing required fields' }, { status: 400 });
    }

    // Connect to MongoDB
    await connectToDatabase();

    // Check if user already exists
    const existingUser = await User.findOne({ email });
    if (existingUser) {
      return NextResponse.json({ error: 'User already exists' }, { status: 400 });
    }

    // Hash the password
    const salt = await bcrypt.genSalt(10);
    const passwordHash = await bcrypt.hash(password, salt);

    // Create a new user document
    const user = new User({
      fullName,
      email,
      passwordHash,
      careerInterest,
      experience: experience ? Number(experience) : 0,
    });

    await user.save();

    return NextResponse.json({ message: 'User registered successfully' }, { status: 201 });
  } catch (error) {
    console.error('Registration error:', error);
    return NextResponse.json({ error: 'Registration failed' }, { status: 500 });
  }
}