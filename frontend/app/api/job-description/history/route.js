// 1. Fix backend API route handlers
// File: frontend/app/api/job-description/history/route.js
import { NextResponse } from 'next/server';

export async function GET(request) {
  try {
    // Get cookies for authentication
    const cookies = request.cookies.getAll();
    const tokenCookie = cookies.find(cookie => cookie.name === 'token');
    const token = tokenCookie ? tokenCookie.value : null;
    
    if (!token) {
      console.log('No authentication token found');
      return NextResponse.json(
        { error: 'Authentication required' },
        { status: 401 }
      );
    }
    
    // Get the backend URL from environment variable or use the default
    const backendUrl = process.env.BACKEND_API_URL || 'http://fastapi:8000/api';
    console.log('Using backend URL:', backendUrl);
    
    // Forward the request to the backend API
    const response = await fetch(`${backendUrl}/job-description/history`, {
      method: 'GET',
      headers: {
        'Cookie': `token=${token}`,
        'Authorization': `Bearer ${token}`
      }
    });
    
    console.log('History response status:', response.status);
    
    // Get the response data
    let data;
    try {
      data = await response.json();
    } catch (error) {
      console.error('Error parsing JSON from backend:', error);
      
      // Return empty history on error instead of failing
      return NextResponse.json({ history: [] });
    }
    
    // If the response is not OK, return empty history instead of error
    if (!response.ok) {
      console.warn('Backend returned error, using empty history');
      return NextResponse.json({ history: [] });
    }
    
    // Return the data
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error in job history API route:', error);
    
    // Return empty history on error instead of failing
    return NextResponse.json({ history: [] });
  }
}

