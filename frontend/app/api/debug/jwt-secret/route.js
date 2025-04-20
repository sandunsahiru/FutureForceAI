import { NextResponse } from "next/server";

export async function GET() {
  // Get the JWT secret from environment variables
  const jwtSecret = process.env.JWT_SECRET || "(not set)";
  
  // Mask the secret for security
  const maskedSecret = jwtSecret === "(not set)" 
    ? "(not set)" 
    : jwtSecret.substr(0, 3) + "..." + jwtSecret.substr(-3);
  
  return NextResponse.json({
    jwtSecretExists: Boolean(process.env.JWT_SECRET),
    jwtSecretLength: jwtSecret === "(not set)" ? 0 : jwtSecret.length,
    jwtSecretPreview: maskedSecret
  });
}