import { NextRequest, NextResponse } from 'next/server';
import sqlite3 from 'sqlite3';
import { open } from 'sqlite';
import path from 'path';
import fs from 'fs';

export async function DELETE(request: NextRequest) {
  try {
    const { clipId } = await request.json();
    
    if (!clipId) {
      return NextResponse.json(
        { success: false, error: 'Clip ID is required' },
        { status: 400 }
      );
    }

    // Extract job ID from clip ID
    const jobId = clipId.split('_clip_')[0];
    const clipIndex = parseInt(clipId.split('_clip_')[1]) - 1;
    
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

    // Parse results
    const results = JSON.parse(job.results);
    let clipUrl = null;
    
    // Get clip URL before deletion for file cleanup
    if (results.clips_by_platform) {
      Object.keys(results.clips_by_platform).forEach(platform => {
        if (results.clips_by_platform[platform][clipIndex]) {
          clipUrl = results.clips_by_platform[platform][clipIndex].url;
        }
      });
    }

    // Remove clip from all platforms
    if (results.clips_by_platform) {
      Object.keys(results.clips_by_platform).forEach(platform => {
        if (results.clips_by_platform[platform][clipIndex]) {
          results.clips_by_platform[platform].splice(clipIndex, 1);
        }
      });
    }

    // Update total clips count
    if (results.total_clips) {
      results.total_clips = Math.max(0, results.total_clips - 1);
    }

    // Update job results in database
    await db.run(
      'UPDATE jobs SET results = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
      [JSON.stringify(results), jobId]
    );

    await db.close();

    // Try to delete the physical file if it exists
    if (clipUrl) {
      try {
        // Convert URL to file path
        const fileName = path.basename(clipUrl);
        const filePath = path.join(process.cwd(), '..', 'app', 'static', 'generated', fileName);
        
        if (fs.existsSync(filePath)) {
          fs.unlinkSync(filePath);
          console.log(`Deleted file: ${filePath}`);
        }
      } catch (fileError) {
        console.warn('Could not delete physical file:', fileError);
        // Continue anyway - database update was successful
      }
    }

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