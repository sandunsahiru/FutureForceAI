// This should go in your frontend/app/api/job-description/solve-captcha/route.js file

import { NextResponse } from 'next/server';

export async function POST(request) {
  try {
    // Get request data
    const requestData = await request.json();
    const { site_key, page_url } = requestData;
    
    if (!site_key || !page_url) {
      return NextResponse.json(
        { error: 'Missing required parameters: site_key or page_url' },
        { status: 400 }
      );
    }
    
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
    
    // Get the backend URL from environment variable or use the default
    const backendUrl = process.env.BACKEND_API_URL || 'http://fastapi:8000/api';
    console.log('Using backend URL for CAPTCHA solving:', backendUrl);
    
    // Forward the request to solve CAPTCHA using 2Captcha
    const response = await fetch(`${backendUrl}/job-description/solve-captcha`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Cookie': `token=${token}`,
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        site_key: site_key,
        page_url: page_url
      })
    });
    
    if (!response.ok) {
      const errorData = await response.json();
      return NextResponse.json(
        { error: errorData.detail || 'Failed to solve CAPTCHA' },
        { status: response.status }
      );
    }
    
    const data = await response.json();
    return NextResponse.json(data);
    
  } catch (error) {
    console.error('Error in solve-captcha API route:', error);
    return NextResponse.json(
      { error: 'Internal server error', details: error.message },
      { status: 500 }
    );
  }
}