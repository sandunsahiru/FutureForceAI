import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';

export async function GET(request) {
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

    // Use the FASTAPI_URL environment variable for consistency
    const apiUrl = `${process.env.FASTAPI_URL}/api/career-guidance/history`;
    console.log(`Sending history request to: ${apiUrl}`);

    // Send request to backend API
    const response = await fetch(apiUrl, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
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
        { detail: errorData.detail || 'Failed to fetch career guidance history' },
        { status: response.status }
      );
    }

    const data = await response.json();
    console.log('History API successful response received');

    // Return successful response with history data
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching career guidance history:', error);
    return NextResponse.json(
      { detail: `Internal server error: ${error.message || 'Unknown error'}` },
      { status: 500 }
    );
  }
}