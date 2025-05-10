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

    // Get form data with CV file
    const formData = await request.formData();
    
    // Copy the CV file from the request
    const cvFile = formData.get('cv_file');
    if (!cvFile) {
      return NextResponse.json(
        { detail: 'No CV file provided' },
        { status: 400 }
      );
    }
    
    // Clone the formData to send to API
    const formDataForAPI = new FormData();
    formDataForAPI.append('cv_file', cvFile);
    
    // Use the FASTAPI_URL environment variable for consistency
    const apiUrl = `${process.env.FASTAPI_URL}/api/career-guidance/upload-cv`;
    console.log(`Sending CV upload request to: ${apiUrl}`);

    // Send request to backend API
    const response = await fetch(apiUrl, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
      body: formDataForAPI,
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
        { detail: errorData.detail || 'Failed to upload CV' },
        { status: response.status }
      );
    }

    const data = await response.json();
    console.log('CV upload API successful response received');

    // Return successful response
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error uploading CV:', error);
    return NextResponse.json(
      { detail: `Internal server error: ${error.message || 'Unknown error'}` },
      { status: 500 }
    );
  }
}