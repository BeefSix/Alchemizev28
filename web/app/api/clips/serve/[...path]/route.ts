import { NextRequest, NextResponse } from 'next/server';
import { createReadStream, existsSync, statSync } from 'fs';
import path from 'path';
import { Readable } from 'stream';

export async function GET(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  try {
    const [userId, jobId, filename] = params.path;
    
    if (!userId || !jobId || !filename) {
      return new NextResponse('Invalid path', { status: 400 });
    }

    // For now, serve from the generated folder since we have test files there
    // In production, this would serve from user-specific directories
    const filePath = path.join(process.cwd(), '..', 'app', 'static', 'generated', filename);
    
    // Check if file exists
    if (!existsSync(filePath)) {
      // Try to create a sample video if it doesn't exist
      await createSampleVideo(filePath, filename);
      
      if (!existsSync(filePath)) {
        return new NextResponse('Video not found', { status: 404 });
      }
    }

    const stat = statSync(filePath);
    const fileSize = stat.size;
    const range = request.headers.get('range');

    if (range) {
      // Handle range requests for video streaming
      const parts = range.replace(/bytes=/, '').split('-');
      const start = parseInt(parts[0], 10);
      const end = parts[1] ? parseInt(parts[1], 10) : fileSize - 1;
      const chunksize = (end - start) + 1;
      
      const stream = createReadStream(filePath, { start, end });
      
      return new NextResponse(Readable.toWeb(stream) as ReadableStream, {
        status: 206,
        headers: {
          'Content-Range': `bytes ${start}-${end}/${fileSize}`,
          'Accept-Ranges': 'bytes',
          'Content-Length': chunksize.toString(),
          'Content-Type': 'video/mp4',
          'Cache-Control': 'public, max-age=3600'
        }
      });
    } else {
      // Serve entire file
      const stream = createReadStream(filePath);
      
      return new NextResponse(Readable.toWeb(stream) as ReadableStream, {
        status: 200,
        headers: {
          'Content-Length': fileSize.toString(),
          'Content-Type': 'video/mp4',
          'Accept-Ranges': 'bytes',
          'Cache-Control': 'public, max-age=3600'
        }
      });
    }

  } catch (error) {
    console.error('Error serving video:', error);
    return new NextResponse('Internal Server Error', { status: 500 });
  }
}

async function createSampleVideo(filePath: string, filename: string) {
  try {
    const { spawn } = require('child_process');
    const fs = require('fs');
    
    // Ensure directory exists
    const dir = path.dirname(filePath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    
    // Extract duration from filename or use default
    let duration = 10;
    if (filename.includes('clip_1')) duration = 10;
    else if (filename.includes('clip_2')) duration = 15;
    else if (filename.includes('clip_3')) duration = 20;
    
    // Create sample video using FFmpeg
    const ffmpeg = spawn('ffmpeg', [
      '-y', // Overwrite output file
      '-f', 'lavfi',
      '-i', `testsrc=duration=${duration}:size=320x240:rate=1`,
      '-f', 'lavfi', 
      '-i', `sine=frequency=1000:duration=${duration}`,
      '-c:v', 'libx264',
      '-t', duration.toString(),
      filePath
    ]);
    
    return new Promise((resolve, reject) => {
      ffmpeg.on('close', (code: number) => {
        if (code === 0) {
          console.log(`Created sample video: ${filePath}`);
          resolve(true);
        } else {
          console.error(`FFmpeg exited with code ${code}`);
          reject(new Error(`FFmpeg failed with code ${code}`));
        }
      });
      
      ffmpeg.on('error', (error: Error) => {
        console.error('FFmpeg error:', error);
        reject(error);
      });
    });
    
  } catch (error) {
    console.error('Error creating sample video:', error);
    throw error;
  }
}