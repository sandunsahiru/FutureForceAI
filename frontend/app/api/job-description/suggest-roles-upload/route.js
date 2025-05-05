// This should go in your frontend/app/api/job-description/suggest-roles-upload/route.js file

import { NextResponse } from 'next/server';

export async function POST(request) {
  try {
    console.log("Starting CV upload process");
    
    // Get cookies for authentication
    const cookies = request.cookies.getAll();
    const tokenCookie = cookies.find(cookie => cookie.name === 'token');
    const token = tokenCookie ? tokenCookie.value : null;
    
    if (!token) {
      console.log('No authentication token found');
      return NextResponse.json(
        { error: 'Authentication required' },
        { status: 401 }
      );
    }
    
    // Debug client's request headers
    const userAgent = request.headers.get('user-agent');
    console.log('User agent:', userAgent);
    
    // Simulate a more realistic browser with more headers
    const randomHeaders = {
      'Accept-Language': 'en-US,en;q=0.9',
      'Accept-Encoding': 'gzip, deflate, br',
      'Referer': 'https://yourwebsite.com/job-description',
      'Connection': 'keep-alive',
      'X-Requested-With': 'XMLHttpRequest',
      'Sec-Fetch-Dest': 'empty',
      'Sec-Fetch-Mode': 'cors',
      'Sec-Fetch-Site': 'same-origin',
      'Pragma': 'no-cache',
      'Cache-Control': 'no-cache'
    };
    
    // Get the backend URL from environment variable or use the default
    const backendUrl = process.env.BACKEND_API_URL || 'http://fastapi:8000/api';
    console.log('Using backend URL for CV upload:', backendUrl);
    
    // Get the request content type and log it
    const contentType = request.headers.get('content-type');
    console.log('Request content type:', contentType);
    
    try {
      // Parse the FormData from the request
      const formData = await request.formData();
      console.log('Form data keys:', [...formData.keys()]);
      
      // Get the file from the form data with detailed error handling
      const fileEntry = formData.get('cv_file');
      console.log('File entry type:', fileEntry ? typeof fileEntry : 'null');
      console.log('File entry properties:', fileEntry ? Object.keys(fileEntry) : 'N/A');
      
      // Check if file exists and has the right properties
      if (!fileEntry) {
        console.warn('No file found in form data');
        return NextResponse.json(
          { error: 'No file uploaded or invalid file' },
          { status: 400 }
        );
      }
      
      // Check if it's a valid file (has arrayBuffer method)
      if (typeof fileEntry.arrayBuffer !== 'function') {
        console.warn('Invalid file object - missing arrayBuffer method');
        return NextResponse.json(
          { error: 'Invalid file format' },
          { status: 400 }
        );
      }
      
      // Log file information if available
      if (fileEntry.name) {
        console.log('File received:', {
          name: fileEntry.name,
          size: fileEntry.size,
          type: fileEntry.type
        });
      }
      
      // Create new FormData to forward to backend
      const newFormData = new FormData();
      
      // Add the file to the FormData with the expected field name
      newFormData.append('cv_file', fileEntry);
      
      // Get captcha token if available
      const captchaToken = formData.get('captcha_token');
      if (captchaToken) {
        newFormData.append('captcha_token', captchaToken);
      }
      
      // Add browser details to help avoid bot detection
      const browserInfo = JSON.stringify({
        userAgent: userAgent || 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
        screenWidth: 1920,
        screenHeight: 1080,
        colorDepth: 24,
        platform: 'Windows',
        doNotTrack: 'unspecified',
        cookies: 'enabled',
        language: 'en-US',
        webdriver: false,
        plugins: ['PDF Viewer', 'Chrome PDF Viewer', 'Chromium PDF Viewer'],
        timeZone: 'Asia/Colombo',
        timestamp: new Date().getTime()
      });
      
      // Add the browser info to the FormData
      newFormData.append('browser_info', browserInfo);
      
      // Set up request headers with realistic browser headers
      const headers = {
        // Don't set Content-Type for FormData
        'Cookie': `token=${token}`,
        'Authorization': `Bearer ${token}`,
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'X-Requested-With': 'XMLHttpRequest',
        'User-Agent': userAgent || 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
        'Referer': 'https://yourdomain.com/job-description',
        ...randomHeaders
      };
      
      console.log('Sending request to backend with headers:', Object.keys(headers));
      
      // Forward the request to the backend API
      const response = await fetch(`${backendUrl}/job-description/suggest-roles-upload`, {
        method: 'POST',
        headers: headers,
        body: newFormData
      });
      
      console.log('Backend response status:', response.status);
      
      // Handle different response types
      const responseContentType = response.headers.get('content-type');
      console.log('Response content type:', responseContentType);
      
      let responseData;
      
      if (responseContentType && responseContentType.includes('application/json')) {
        // Parse JSON response
        responseData = await response.json();
      } else {
        // Handle non-JSON response (text)
        const textResponse = await response.text();
        console.log('Text response (first 100 chars):', textResponse.substring(0, 100));
        
        try {
          // Try to parse it as JSON anyway
          responseData = JSON.parse(textResponse);
        } catch (parseError) {
          // If it's not valid JSON, create a simple error object
          responseData = { detail: textResponse || 'Unknown error occurred' };
        }
      }
      
      // Check if the response contains CAPTCHA challenge
      if (responseData.captcha_required || 
          (responseData.detail && typeof responseData.detail === 'string' && 
           (responseData.detail.includes('captcha') || responseData.detail.includes('CAPTCHA')))) {
        console.log('CAPTCHA challenge detected in the response. Solving with 2Captcha...');
        
        const captchaSiteKey = responseData.captcha_site_key || '';
        const captchaPageUrl = `${backendUrl}/job-description/suggest-roles-upload`;
        
        // Call 2Captcha solving service
        try {
          const captchaSolverResponse = await fetch(`${backendUrl}/job-description/solve-captcha`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${token}`,
              'Cookie': `token=${token}`
            },
            body: JSON.stringify({
              site_key: captchaSiteKey,
              page_url: captchaPageUrl,
              is_invisible: false
            })
          });
          
          if (captchaSolverResponse.ok) {
            const solverData = await captchaSolverResponse.json();
            const captchaToken = solverData.captcha_token;
            
            if (captchaToken) {
              console.log('CAPTCHA solved successfully. Resubmitting request with token...');
              
              // Create new FormData with the CAPTCHA token
              const formDataWithCaptcha = new FormData();
              formDataWithCaptcha.append('cv_file', fileEntry);
              formDataWithCaptcha.append('captcha_token', captchaToken);
              formDataWithCaptcha.append('browser_info', browserInfo);
              
              // Resubmit the request
              const resubmitResponse = await fetch(`${backendUrl}/job-description/suggest-roles-upload`, {
                method: 'POST',
                headers: headers,
                body: formDataWithCaptcha
              });
              
              if (resubmitResponse.ok) {
                const finalData = await resubmitResponse.json();
                console.log('Resubmission successful');
                return NextResponse.json(finalData);
              } else {
                console.error('Resubmission failed even after CAPTCHA solution');
                const errorData = await resubmitResponse.json();
                return NextResponse.json(
                  { error: errorData.detail || 'Failed to upload CV after CAPTCHA verification' },
                  { status: resubmitResponse.status }
                );
              }
            } else {
              console.error('No CAPTCHA token received from solver');
            }
          } else {
            console.error('Failed to solve CAPTCHA');
          }
        } catch (captchaError) {
          console.error('Error solving CAPTCHA:', captchaError);
        }
        
        // If we reach here, the CAPTCHA solving process failed
        return NextResponse.json(
          { 
            error: 'CAPTCHA verification required',
            captcha_required: true,
            captcha_site_key: captchaSiteKey || '',
            detail: 'Please try again in a few moments'
          },
          { status: 403 }
        );
      }
      
      // If the response is not OK, return the error
      if (!response.ok) {
        console.error('Error response from backend:', responseData);
        return NextResponse.json(
          { 
            error: responseData.detail || 'Failed to analyze CV',
            detail: responseData.detail || 'Unknown error occurred'
          },
          { status: response.status }
        );
      }
      
      // Return the successful response data
      console.log('Successful response, returning data to client');
      return NextResponse.json(responseData);
      
    } catch (formError) {
      console.error('Error handling form data:', formError);
      return NextResponse.json(
        { error: 'Failed to process file upload. Please check your file format and try again.' },
        { status: 500 }
      );
    }
  } catch (error) {
    console.error('Fatal error in suggest-roles-upload API route:', error);
    return NextResponse.json(
      { error: 'Failed to upload CV. Please try again later.' },
      { status: 500 }
    );
  }
}