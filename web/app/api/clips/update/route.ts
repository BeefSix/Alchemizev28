import { NextRequest, NextResponse } from 'next/server';
import sqlite3 from 'sqlite3';
import { open } from 'sqlite';
import path from 'path';

export async function PUT(request: NextRequest) {
  try {
    const { clipId, name } = await request.json();
    
    if (!clipId || !name) {
      return NextResponse.json(
        { success: false, error: 'Clip ID and name are required' },
        { status: 400 }
      );
    }

    // Extract job ID from clip ID
    const jobId = clipId.split('_clip_')[0];
    
    // Open database connection
    const dbPath = path.join(process.cwd(), '..', 'alchemize.db');
    const db = await open({
      filename: dbPath,
      driver: sqlite3.Database
    });

    // Get current job results
    const job = await db.get(
      'SELECT results FROM jobs WHERE id = ?',
      [jobId]
    );

    if (!job) {
      await db.close();
      return NextResponse.json(
        { success: false, error: 'Job not found' },
        { status: 404 }
      );
    }

    // Parse and update results
    const results = JSON.parse(job.results);
    const clipIndex = parseInt(clipId.split('_clip_')[1]) - 1;
    
    // Update clip name in all platforms
    if (results.clips_by_platform) {
      Object.keys(results.clips_by_platform).forEach(platform => {
        if (results.clips_by_platform[platform][clipIndex]) {
          results.clips_by_platform[platform][clipIndex].name = name;
        }
      });
    }

    // Update job results in database
    await db.run(
      'UPDATE jobs SET results = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
      [JSON.stringify(results), jobId]
    );

    await db.close();

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