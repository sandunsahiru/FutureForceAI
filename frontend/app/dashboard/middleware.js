import { NextResponse } from 'next/server';

export function middleware(request) {
  // Get the pathname of the request
  const path = request.nextUrl.pathname;
  
  // Paths that don't require authentication
  const publicPaths = ['/login', '/register', '/', '/api/login', '/api/register'];
  
  // Check if the requested path is public
  const isPublicPath = publicPaths.some(publicPath => 
    path === publicPath || path.startsWith(publicPath + '/')
  );
  
  // If it's a public path, allow access
  if (isPublicPath) {
    return NextResponse.next();
  }
  
  // Check if the auth token exists in cookies
  const token = request.cookies.get('token');
  
  // If no token exists and trying to access protected route, redirect to login
  if (!token) {
    // Get the URL of the current request
    const url = request.nextUrl.clone();
    url.pathname = '/login';
    
    // Add the original URL as a query parameter so we can redirect back after login
    url.searchParams.set('from', request.nextUrl.pathname);
    
    console.log(`No auth token found, redirecting to: ${url.pathname}`);
    return NextResponse.redirect(url);
  }
  
  // Allow the request to continue
  return NextResponse.next();
}

// This middleware will run on all routes except those with static files
export const config = {
  matcher: [
    /*
     * Match all request paths except:
     * 1. Public assets (e.g. files in the public folder)
     * 2. Static files (e.g. favicon.ico)
     * 3. API routes that handle authentication
     */
    '/((?!_next/static|_next/image|favicon.ico).*)',
  ],
};