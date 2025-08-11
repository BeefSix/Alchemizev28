import { NextRequest, NextResponse } from 'next/server';
import sqlite3 from 'sqlite3';
import { open } from 'sqlite';
import path from 'path';

interface JobRow {
  id: string;
  status: string;
  created_at: string;
  results: string;
  progress_details: string;
}

interface JobResult {
  id: string;
  status: string;
  total_clips: number;
  video_duration: number;
  captions_added: boolean;
  clips: any[];
  created_at: string;
}

export async function GET(request: NextRequest) {
  try {
    // Open database connection
    const dbPath = path.join(process.cwd(), '..', 'alchemize.db');
    const db = await open({
      filename: dbPath,
      driver: sqlite3.Database
    });

    // Query for completed jobs with results
    const query = `
      SELECT id, status, created_at, results, progress_details
      FROM jobs 
      WHERE status = 'COMPLETED' 
        AND results IS NOT NULL 
        AND results != '{}' 
        AND results != 'null'
      ORDER BY created_at DESC
      LIMIT 20
    `;

    const rows: JobRow[] = await db.all(query);
    await db.close();

    // Process jobs and extract clip data
    const jobs: JobResult[] = [];

    for (const row of rows) {
      try {
        const results = JSON.parse(row.results);
        const progressDetails = row.progress_details ? JSON.parse(row.progress_details) : {};

        // Extract clips from different possible locations in results
        let clips: any[] = [];
        
        if (results.clips_by_platform) {
          // Extract clips from all platforms
          Object.values(results.clips_by_platform).forEach((platformClips: any) => {
            if (Array.isArray(platformClips)) {
              clips = clips.concat(platformClips);
            }
          });
        } else if (results.clips && Array.isArray(results.clips)) {
          clips = results.clips;
        } else if (results.generated_clips && Array.isArray(results.generated_clips)) {
          clips = results.generated_clips;
        }

        // Only include jobs that have clips
        if (clips.length > 0) {
          // Process clips to ensure they have proper URLs
            const processedClips = clips.map((clip, index) => {
              let clipUrl = clip.url || clip.file_path || clip.path;
              
              // Ensure URL is properly formatted
              if (clipUrl && !clipUrl.startsWith('http')) {
                // Convert relative path to absolute URL
                if (clipUrl.startsWith('/')) {
                  clipUrl = `http://localhost:8001${clipUrl}`;
                } else {
                  clipUrl = `http://localhost:8001/static/clips/${clipUrl}`;
                }
              }

              return {
                id: `${row.id}_clip_${index + 1}`,
                name: clip.name || `Clip ${index + 1}`,
                url: clipUrl,
                duration: clip.duration || 30,
                file_size: clip.file_size || clip.size || 5000000, // Default 5MB
                captions_added: clip.captions_added || results.captions_added || false,
                viral_info: clip.viral_info || {
                  viral_score: Math.floor(Math.random() * 10) + 1 // Random score if not available
                },
                created_at: row.created_at
              };
            });

          jobs.push({
            id: row.id,
            status: row.status,
            total_clips: processedClips.length,
            video_duration: results.video_duration || progressDetails.video_duration || 120,
            captions_added: results.captions_added || false,
            clips: processedClips,
            created_at: row.created_at
          });
        }
      } catch (parseError) {
        console.error(`Error parsing job ${row.id}:`, parseError);
        continue;
      }
    }

    return NextResponse.json({
      success: true,
      jobs: jobs,
      total: jobs.length
    });

  } catch (error) {
    console.error('Error fetching completed jobs:', error);
    return NextResponse.json(
      { 
        success: false, 
        error: 'Failed to fetch completed jobs',
        details: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 500 }
    );
  }
}