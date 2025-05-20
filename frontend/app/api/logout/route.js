// app/api/logout/route.js
import { NextResponse } from "next/server";

export async function GET(request) {
  const baseUrl = request.headers.get('x-forwarded-host') || 
                  request.headers.get('host') || 
                  'localhost';
  
  const protocol = request.headers.get('x-forwarded-proto') || 'http';
  
  // Create a response that redirects to the homepage
  const response = NextResponse.redirect(`${protocol}://${baseUrl}/`);
  
  // Clear the auth token cookie
  response.cookies.set("token", "", {
    httpOnly: true,
    expires: new Date(0), // Set expiration to epoch time (immediately expired)
    path: "/",
    sameSite: "lax",
  });
  
  console.log(`Logging out user and redirecting to ${protocol}://${baseUrl}/`);
  
  return response;
}