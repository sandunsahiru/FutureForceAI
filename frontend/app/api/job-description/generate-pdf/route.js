// This should be placed in your frontend/app/api/job-description/generate-pdf/route.js file

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
    console.log('Using backend URL for PDF generation:', backendUrl);
    
    // Forward the request to the backend API
    const backendResponse = await fetch(`${backendUrl}/job-description/generate-pdf`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Cookie': `token=${token}`,
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify(requestData)
    });
    
    // Log response status
    console.log('PDF generation response status:', backendResponse.status);
    
    // If the response is not OK, return the error
    if (!backendResponse.ok) {
      // Try to parse error JSON
      try {
        const errorData = await backendResponse.json();
        console.error('PDF generation error:', errorData);
        return NextResponse.json(
          { error: errorData.detail || 'Failed to generate PDF' },
          { status: backendResponse.status }
        );
      } catch (jsonError) {
        // If JSON parsing fails, try to get text response
        try {
          const textError = await backendResponse.text();
          console.error('PDF generation error text:', textError);
          return NextResponse.json(
            { error: 'Failed to generate PDF', details: textError },
            { status: backendResponse.status }
          );
        } catch (textError) {
          // If all else fails, return generic error
          return NextResponse.json(
            { error: 'Failed to generate PDF' },
            { status: backendResponse.status }
          );
        }
      }
    }
    
    // Get the PDF as binary data
    try {
      const pdfBuffer = await backendResponse.arrayBuffer();
      
      // Create a response with the PDF data
      const response = new NextResponse(pdfBuffer, {
        status: 200,
        headers: {
          'Content-Type': 'application/pdf',
          'Content-Disposition': `attachment; filename="${requestData.job_role.replace(/\s+/g, '_')}_Job_Description.pdf"`
        }
      });
      
      return response;
    } catch (pdfError) {
      console.error('Error processing PDF data:', pdfError);
      return NextResponse.json(
        { error: 'Error processing PDF data', details: pdfError.message },
        { status: 500 }
      );
    }
  } catch (error) {
    console.error('Error in generate-pdf API route:', error);
    return NextResponse.json(
      { error: 'Internal server error', details: error.message },
      { status: 500 }
    );
  }
}