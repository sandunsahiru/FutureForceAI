// app/api/user/saved-jobs/route.js
import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';

export async function GET(request) {
  try {
    const token = cookies().get('token')?.value;

    if (!token) {
      return NextResponse.json(
        { error: 'Authentication required' },
        { status: 401 }
      );
    }

    // Use the environment variables that match your structure
    const backendUrl = process.env.FASTAPI_URL || 'http://fastapi:8000';
    console.log(`Using backend URL for saved jobs (GET): ${backendUrl}`);
    
    const apiUrl = `${backendUrl}/api/user/saved-jobs`;

    const response = await fetch(apiUrl, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`
      },
      cache: 'no-store',
      next: { revalidate: 0 },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return NextResponse.json(
        { detail: errorData.detail || `Failed to fetch saved jobs (Status: ${response.status})` },
        { status: response.status }
      );
    }

    const result = await response.json();
    return NextResponse.json(result);
  } catch (error) {
    console.error('Error in fetching saved jobs API route:', error);
    // Return a more detailed error for troubleshooting
    return NextResponse.json(
      { 
        detail: 'Internal server error',
        error: error.toString(),
        cause: error.cause ? error.cause.toString() : undefined
      },
      { status: 500 }
    );
  }
}

export async function POST(request) {
  try {
    const data = await request.json();
    const token = cookies().get('token')?.value;

    if (!token) {
      return NextResponse.json(
        { error: 'Authentication required' },
        { status: 401 }
      );
    }

    // Use the environment variables that match your structure
    const backendUrl = process.env.FASTAPI_URL || 'http://fastapi:8000';
    console.log(`Using backend URL for saved jobs (POST): ${backendUrl}`);
    
    const apiUrl = `${backendUrl}/api/user/saved-jobs`;

    const response = await fetch(apiUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify(data),
      cache: 'no-store',
      next: { revalidate: 0 },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return NextResponse.json(
        { detail: errorData.detail || `Failed to save job (Status: ${response.status})` },
        { status: response.status }
      );
    }

    const result = await response.json();
    return NextResponse.json(result);
  } catch (error) {
    console.error('Error in saving job API route:', error);
    // Return a more detailed error for troubleshooting
    return NextResponse.json(
      { 
        detail: 'Internal server error',
        error: error.toString(),
        cause: error.cause ? error.cause.toString() : undefined
      },
      { status: 500 }
    );
  }
}