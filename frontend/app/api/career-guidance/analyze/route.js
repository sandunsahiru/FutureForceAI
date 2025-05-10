import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';

export async function POST(request) {
  try {
    // Get auth token from cookies
    const cookieStore = cookies();
    const token = cookieStore.get('token')?.value;

    if (!token) {
      return NextResponse.json(
        { detail: 'Authentication required' },
        { status: 401 }
      );
    }

    // Get request body
    const requestData = await request.json();
    
    // Validate request data
    if (!requestData.cv_id) {
      return NextResponse.json(
        { detail: 'CV ID is required' },
        { status: 400 }
      );
    }
    
    if (!requestData.career_interests || !requestData.career_interests.length) {
      return NextResponse.json(
        { detail: 'At least one career interest is required' },
        { status: 400 }
      );
    }

    // Use the FASTAPI_URL environment variable
    const apiUrl = `${process.env.FASTAPI_URL}/api/career-guidance/analyze`;
    console.log(`Sending analyze request to: ${apiUrl}`);

    // Send request to backend API
    const response = await fetch(apiUrl, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestData),
      credentials: 'include',
    });

    // Handle API response
    if (!response.ok) {
      const errorText = await response.text();
      let errorData;
      try {
        errorData = JSON.parse(errorText);
      } catch (e) {
        errorData = { detail: `Server error: ${response.status}` };
      }
      
      console.error('API error response:', response.status, errorData);
      
      return NextResponse.json(
        { detail: errorData.detail || 'Failed to analyze career path' },
        { status: response.status }
      );
    }

    const data = await response.json();
    console.log('Analyze API successful response received');

    // Return successful response with career analysis data
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error analyzing career path:', error);
    return NextResponse.json(
      { detail: `Internal server error: ${error.message || 'Unknown error'}` },
      { status: 500 }
    );
  }
}