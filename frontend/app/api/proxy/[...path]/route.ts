/**
 * API Proxy Route - forwards requests to backend and logs to terminal
 * 
 * This allows frontend API calls to be logged in the Next.js terminal
 */

import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

const formatTimestamp = () => {
  return new Date().toISOString().replace('T', ' ').substring(0, 23);
};

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const endpoint = '/' + path.join('/');
  const searchParams = request.nextUrl.searchParams.toString();
  const fullPath = searchParams ? `${endpoint}?${searchParams}` : endpoint;
  
  console.log(`${formatTimestamp()} 📡 [Frontend->API] GET ${fullPath}`);
  
  try {
    const response = await fetch(`${BACKEND_URL}${fullPath}`, {
      headers: {
        'Content-Type': 'application/json',
      },
    });
    
    const data = await response.json();
    
    console.log(`${formatTimestamp()} ✅ [Frontend->API] GET ${fullPath} - ${response.status}`);
    
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error(`${formatTimestamp()} ❌ [Frontend->API] GET ${fullPath} - Error:`, error);
    return NextResponse.json({ error: 'Backend unavailable' }, { status: 503 });
  }
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const endpoint = '/' + path.join('/');
  
  console.log(`${formatTimestamp()} 📡 [Frontend->API] POST ${endpoint}`);
  
  try {
    const contentType = request.headers.get('content-type') || '';
    
    let fetchOptions: RequestInit = {
      method: 'POST',
    };
    
    // Handle multipart/form-data (file uploads)
    if (contentType.includes('multipart/form-data')) {
      const formData = await request.formData();
      fetchOptions.body = formData;
      // Don't set Content-Type header - let fetch set it with boundary
    } else {
      // Handle JSON
      let body = null;
      try {
        body = await request.json();
      } catch {
        // No body or invalid JSON
      }
      fetchOptions.headers = {
        'Content-Type': 'application/json',
      };
      fetchOptions.body = body ? JSON.stringify(body) : undefined;
    }
    
    const response = await fetch(`${BACKEND_URL}${endpoint}`, fetchOptions);
    
    const data = await response.json();
    
    console.log(`${formatTimestamp()} ✅ [Frontend->API] POST ${endpoint} - ${response.status}`);
    
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error(`${formatTimestamp()} ❌ [Frontend->API] POST ${endpoint} - Error:`, error);
    return NextResponse.json({ error: 'Backend unavailable' }, { status: 503 });
  }
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const endpoint = '/' + path.join('/');
  
  console.log(`${formatTimestamp()} 📡 [Frontend->API] DELETE ${endpoint}`);
  
  try {
    const response = await fetch(`${BACKEND_URL}${endpoint}`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
      },
    });
    
    const data = await response.json();
    
    console.log(`${formatTimestamp()} ✅ [Frontend->API] DELETE ${endpoint} - ${response.status}`);
    
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error(`${formatTimestamp()} ❌ [Frontend->API] DELETE ${endpoint} - Error:`, error);
    return NextResponse.json({ error: 'Backend unavailable' }, { status: 503 });
  }
}
