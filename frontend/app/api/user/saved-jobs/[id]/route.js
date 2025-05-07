// app/api/user/saved-jobs/[id]/route.js
import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';

export async function DELETE(request, { params }) {
  try {
    const jobId = params.id;
    const token = cookies().get('token')?.value;

    if (!token) {
      return NextResponse.json(
        { error: 'Authentication required' },
        { status: 401 }
      );
    }

    // Use the environment variables that match your structure
    const backendUrl = process.env.FASTAPI_URL || 'http://fastapi:8000';
    console.log(`Using backend URL for delete saved job: ${backendUrl}`);
    
    const apiUrl = `${backendUrl}/api/user/saved-jobs/${jobId}`;

    const response = await fetch(apiUrl, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${token}`
      },
      cache: 'no-store',
      next: { revalidate: 0 },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return NextResponse.json(
        { detail: errorData.detail || `Failed to remove saved job (Status: ${response.status})` },
        { status: response.status }
      );
    }

    const result = await response.json();
    return NextResponse.json(result);
  } catch (error) {
    console.error('Error in removing saved job API route:', error);
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