// app/api/job-apply/route.js
import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';

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
    console.log(`Using backend URL for job apply: ${backendUrl}`);
    
    const apiUrl = `${backendUrl}/api/job-apply`;

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
        { detail: errorData.detail || `Failed to apply for job (Status: ${response.status})` },
        { status: response.status }
      );
    }

    const result = await response.json();
    return NextResponse.json(result);
  } catch (error) {
    console.error('Error in job apply API route:', error);
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