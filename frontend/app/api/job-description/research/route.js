// This should be placed in your frontend/app/api/job-description/research/route.js file

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
    console.log('Using backend URL for research:', backendUrl);
    console.log('Research request data:', requestData);
    
    // Forward the request to the backend API
    const response = await fetch(`${backendUrl}/job-description/research`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Cookie': `token=${token}`,
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify(requestData)
    });
    
    // Log response status
    console.log('Research response status:', response.status);
    
    // Get the response data
    let data;
    try {
      data = await response.json();
    } catch (error) {
      console.error('Error parsing JSON from backend:', error);
      // Try to get text response instead
      const textResponse = await response.text();
      console.log('Raw research response:', textResponse);
      return NextResponse.json(
        { error: 'Failed to parse backend response', details: textResponse },
        { status: 500 }
      );
    }
    
    // If the response is not OK, return the error
    if (!response.ok) {
      return NextResponse.json(
        { error: data.detail || 'Failed to research job role' },
        { status: response.status }
      );
    }
    
    // Return the data
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error in job research API route:', error);
    return NextResponse.json(
      { error: 'Internal server error', details: error.message },
      { status: 500 }
    );
  }
}