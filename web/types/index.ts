export interface User {
  id: number;
  email: string;
  username: string;
  credits: number;
  subscription_plan: string;
  created_at: string;
  updated_at: string;
}

export interface Job {
  id: string;
  user_id: number;
  status: 'PENDING' | 'IN_PROGRESS' | 'COMPLETED' | 'FAILED' | 'RETRYING';
  job_type: 'VIDEOCLIP' | 'CONTENT' | 'MAGIC';
  progress_details?: {
    description: string;
    percentage: number;
    stage?: string;
  };
  error_message?: string;
  results?: any;
  created_at: string;
  updated_at: string;
}

export interface VideoClipJob extends Job {
  job_type: 'VIDEOCLIP';
  results?: {
    clips_by_platform: {
      all: VideoClip[];
      TikTok: VideoClip[];
      Instagram: VideoClip[];
      YouTube: VideoClip[];
    };
    total_clips: number;
    video_duration: number;
    captions_added: boolean;
    processing_details: {
      aspect_ratio: string;
      clip_duration: number;
      karaoke_words: number;
      caption_type: string;
      original_file_size: number;
      audio_extracted: boolean;
      processing_method: string;
      clip_selection_method: string;
      viral_moments_detected: number;
      transcript_available: boolean;
    };
  };
}

export interface VideoClip {
  success: boolean;
  url: string;
  file_size: number;
  captions_added: boolean;
  duration: number;
  processing_method: string;
  viral_info?: {
    source: string;
    viral_score: string;
    start_time: number;
    duration: number;
  };
  error?: string;
}

export interface UploadChunk {
  chunk_index: number;
  total_chunks: number;
  chunk_data: string; // base64 encoded
  file_id: string;
}

export interface UploadInitResponse {
  upload_id: string;
  chunk_size: number;
  total_chunks: number;
  expires_at: string;
}

export interface UploadCompleteResponse {
  upload_id: string;
  filename: string;
  file_path: string;
  file_size: number;
  checksum: string;
  message: string;
}

export interface JobEvent {
  status: 'queued' | 'processing' | 'completed' | 'failed';
  stage?: 'transcribe' | 'score' | 'clip' | 'subtitle';
  percent?: number;
  error?: string;
}

export interface VideoUploadForm {
  file: File;
  add_captions: boolean;
  aspect_ratio: '9:16' | '1:1' | '16:9';
}

export interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface LoginForm {
  email: string;
  password: string;
}

export interface RegisterForm {
  email: string;
  username: string;
  password: string;
}
