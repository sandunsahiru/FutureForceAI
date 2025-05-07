// app/api/job-salary/route.js
import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';

export async function GET(request) {
  try {
    const token = cookies().get('token')?.value;
    const { searchParams } = new URL(request.url);
    const jobTitle = searchParams.get('job_title');
    const location = searchParams.get('location');
    const experience = searchParams.get('experience');

    if (!token) {
      return NextResponse.json(
        { error: 'Authentication required' },
        { status: 401 }
      );
    }

    if (!jobTitle) {
      return NextResponse.json(
        { error: 'Job title is required' },
        { status: 400 }
      );
    }

    // Use the environment variables that match your structure
    const backendUrl = process.env.FASTAPI_URL || 'http://fastapi:8000';
    console.log(`Using backend URL for job salary: ${backendUrl}`);
    
    const apiUrl = `${backendUrl}/api/job-salary?job_title=${encodeURIComponent(jobTitle)}${
      location ? `&location=${encodeURIComponent(location)}` : ''
    }${experience ? `&experience=${encodeURIComponent(experience)}` : ''}`;

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
        { detail: errorData.detail || `Failed to get salary information (Status: ${response.status})` },
        { status: response.status }
      );
    }

    const result = await response.json();
    return NextResponse.json(result);
  } catch (error) {
    console.error('Error in job salary API route:', error);
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