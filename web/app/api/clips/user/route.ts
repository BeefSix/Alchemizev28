import { NextRequest, NextResponse } from 'next/server';
import sqlite3 from 'sqlite3';
import { open } from 'sqlite';
import path from 'path';

export async function GET(request: NextRequest) {
  try {
    // Get the authorization header
    const authHeader = request.headers.get('authorization');
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return NextResponse.json(
        { success: false, error: 'Authentication required' },
        { status: 401 }
      );
    }

    const token = authHeader.substring(7);
    
    // Verify token and get user info by calling the backend
    const userResponse = await fetch('http://localhost:8001/api/v1/auth/me', {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!userResponse.ok) {
      return NextResponse.json(
        { success: false, error: 'Invalid authentication token' },
        { status: 401 }
      );
    }

    const userData = await userResponse.json();
    const userId = userData.id;
    
    // Open database connection
    const dbPath = path.join(process.cwd(), '..', 'alchemize.db');
    const db = await open({
      filename: dbPath,
      driver: sqlite3.Database
    });

    // Get completed jobs for the authenticated user
    const jobs = await db.all(
      `SELECT id, status, created_at, results, progress_details 
       FROM jobs 
       WHERE user_id = ? AND status = 'COMPLETED' AND results IS NOT NULL AND results != '{}' 
       ORDER BY created_at DESC`,
      [userId]
    );

    await db.close();

    if (jobs.length === 0) {
      return NextResponse.json({
        success: true,
        jobs: [],
        message: 'No completed jobs found'
      });
    }

    // Process jobs and create user-specific clips
    const processedJobs = [];
    
    for (const job of jobs) {
      try {
        const results = typeof job.results === 'string' ? JSON.parse(job.results) : job.results;
        
        // Create clips with proper user-specific URLs
        const clips = [];
        const jobId = job.id;
        
        // Generate 3 sample clips for each job
        for (let i = 1; i <= 3; i++) {
          const clipId = `${jobId}_clip_${i}`;
          const clipName = `Clip ${i}`;
          
          clips.push({
            id: clipId,
            name: clipName,
            url: `/api/clips/serve/${userId}/${jobId}/${clipId}.mp4`,
            duration: 10 + (i * 5), // 15, 20, 25 seconds
            file_size: 1000000 + (i * 500000), // Varying file sizes
            captions_added: i <= 2, // First two clips have captions
            viral_info: {
              viral_score: Math.max(1, 10 - i) // Decreasing viral scores
            },
            created_at: job.created_at,
            job_id: jobId,
            user_id: userId
          });
        }

        if (clips.length > 0) {
          processedJobs.push({
            id: job.id,
            title: `Job ${job.id.substring(0, 8)}`,
            status: job.status,
            created_at: job.created_at,
            clips: clips
          });
        }
      } catch (error) {
        console.error(`Error processing job ${job.id}:`, error);
      }
    }

    return NextResponse.json({
      success: true,
      jobs: processedJobs
    });

  } catch (error) {
    console.error('Error fetching user clips:', error);
    return NextResponse.json(
      { 
        success: false, 
        error: 'Failed to fetch clips',
        details: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 500 }
    );
  }
}

export async function PUT(request: NextRequest) {
  try {
    const { clipId, name } = await request.json();
    const defaultUserId = 'user_1';
    
    if (!clipId || !name) {
      return NextResponse.json(
        { success: false, error: 'Clip ID and name are required' },
        { status: 400 }
      );
    }

    // For now, we'll just return success since we're using mock data
    // In a real implementation, this would update the user storage
    
    return NextResponse.json({
      success: true,
      message: 'Clip name updated successfully'
    });

  } catch (error) {
    console.error('Error updating clip name:', error);
    return NextResponse.json(
      { 
        success: false, 
        error: 'Failed to update clip name',
        details: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 500 }
    );
  }
}

export async function DELETE(request: NextRequest) {
  try {
    const { clipId } = await request.json();
    const defaultUserId = 'user_1';
    
    if (!clipId) {
      return NextResponse.json(
        { success: false, error: 'Clip ID is required' },
        { status: 400 }
      );
    }

    // For now, we'll just return success since we're using mock data
    // In a real implementation, this would delete from user storage
    
    return NextResponse.json({
      success: true,
      message: 'Clip deleted successfully'
    });

  } catch (error) {
    console.error('Error deleting clip:', error);
    return NextResponse.json(
      { 
        success: false, 
        error: 'Failed to delete clip',
        details: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 500 }
    );
  }
}