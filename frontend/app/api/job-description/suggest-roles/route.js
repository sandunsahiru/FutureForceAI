// This should be placed in your frontend/app/api/job-description/suggest-roles/route.js file

import { NextResponse } from 'next/server';

export async function POST(request) {
  try {
    // Get the request data
    const requestData = await request.json();
    
    // Get cookies for authentication
    const cookies = request.cookies.getAll();
    const tokenCookie = cookies.find(cookie => cookie.name === 'token');
    const token = tokenCookie ? tokenCookie.value : null;
    
    if (!token) {
      return NextResponse.json(
        { error: 'Authentication required' },
        { status: 401 }
      );
    }
    
    // Hard-code the backend URL if environment variable isn't set
    const backendUrl = process.env.BACKEND_API_URL || 'http://fastapi:8000/api';
    console.log('Using backend URL:', backendUrl);
    
    // Forward the request to the backend API
    const response = await fetch(`${backendUrl}/job-description/suggest-roles`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Cookie': `token=${token}`,
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify(requestData)
    });
    
    // Get the response data
    let data;
    try {
      data = await response.json();
    } catch (error) {
      console.error('Error parsing JSON from backend:', error);
      // Try to get text response instead
      const textResponse = await response.text();
      console.log('Raw backend response:', textResponse);
      return NextResponse.json(
        { error: 'Failed to parse backend response', details: textResponse },
        { status: 500 }
      );
    }
    
    // If the response is not OK, return the error
    if (!response.ok) {
      return NextResponse.json(
        { error: data.detail || 'Failed to suggest roles' },
        { status: response.status }
      );
    }
    
    // Return the data
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error in suggest-roles API route:', error);
    return NextResponse.json(
      { error: 'Internal server error', details: error.message },
      { status: 500 }
    );
  }
}