import { NextRequest, NextResponse } from 'next/server';

interface Clip {
  id: string;
  name: string;
  url: string;
  duration: number;
  file_size: number;
  captions_added: boolean;
  viral_info?: {
    viral_score: number;
  };
  created_at: string;
}

interface JobClipsResponse {
  success: boolean;
  job: {
    id: string;
    status: string;
    total_clips: number;
    video_duration: number;
    captions_added: boolean;
    clips: Clip[];
    created_at: string;
  } | null;
  message?: string;
}

export async function GET(
  request: NextRequest,
  { params }: { params: { jobId: string } }
): Promise<NextResponse<JobClipsResponse>> {
  try {
    const { jobId } = params;

    if (!jobId) {
      return NextResponse.json({
        success: false,
        job: null,
        message: 'Job ID is required'
      }, { status: 400 });
    }

    // Check authentication
    const authHeader = request.headers.get('authorization');
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return NextResponse.json({
        success: false,
        job: null,
        message: 'Authentication required'
      }, { status: 401 });
    }

    const token = authHeader.split(' ')[1];
    
    // Verify token with backend
    const backendResponse = await fetch('http://localhost:8001/api/v1/auth/me', {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!backendResponse.ok) {
      return NextResponse.json({
        success: false,
        job: null,
        message: 'Invalid authentication token'
      }, { status: 401 });
    }

    const userData = await backendResponse.json();
    const userId = userData.id;

    // Get job details from backend API
    const jobResponse = await fetch(`http://localhost:8001/api/v1/jobs/${jobId}`, {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!jobResponse.ok) {
      return NextResponse.json({
        success: false,
        job: null,
        message: 'Job not found or not accessible'
      }, { status: 404 });
    }

    const job = await jobResponse.json();

    if (!job || job.status !== 'COMPLETED' || job.job_type !== 'videoclip') {
      return NextResponse.json({
        success: false,
        job: null,
        message: 'Job not found, not completed, or not a video clip job'
      }, { status: 404 });
    }

    // Parse job results
    let results;
    try {
      results = typeof job.results === 'string' ? JSON.parse(job.results) : job.results;
    } catch (error) {
      return NextResponse.json({
        success: false,
        job: null,
        message: 'Invalid job results data'
      }, { status: 500 });
    }

    // Extract clips from results
    const clipsData = results?.clips_by_platform?.all || [];
    
    // Process clips to ensure proper format
    const clips: Clip[] = clipsData.map((clip: any, index: number) => ({
      id: `${jobId}_clip_${index + 1}`,
      name: clip.name || `Clip ${index + 1}`,
      url: clip.url || `/api/clips/serve/${userId}/${jobId}/clip_${index + 1}.mp4`,
      duration: clip.duration || 30,
      file_size: clip.file_size || 5000000,
      captions_added: clip.captions_added || results.captions_added || false,
      viral_info: clip.viral_info || {
        viral_score: Math.floor(Math.random() * 10) + 1
      },
      created_at: job.created_at
    }));

    return NextResponse.json({
      success: true,
      job: {
        id: job.id,
        status: job.status,
        total_clips: clips.length,
        video_duration: results?.video_duration || 0,
        captions_added: results?.captions_added || false,
        clips: clips,
        created_at: job.created_at
      }
    });

  } catch (error) {
    console.error('Error fetching job clips:', error);
    return NextResponse.json({
      success: false,
      job: null,
      message: 'Internal server error'
    }, { status: 500 });
  }
}