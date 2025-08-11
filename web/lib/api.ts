import { 
  User, 
  Job, 
  VideoClipJob, 
  VideoUploadForm, 
  JobEvent, 
  ApiResponse, 
  AuthResponse, 
  LoginForm, 
  RegisterForm,
  UploadInitResponse,
  UploadCompleteResponse
} from '@/types';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8001';

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    
    // Get the access token from localStorage (only on client side)
    const accessToken = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
    
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string> || {}),
    };
    
    // Add authorization header if token exists
    if (accessToken) {
      headers['Authorization'] = `Bearer ${accessToken}`;
    }
    
    const config: RequestInit = {
      headers,
      credentials: 'include', // Include cookies for JWT auth
      ...options,
    };

    const response = await fetch(url, config);
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }

  // Authentication
  async login(credentials: LoginForm): Promise<AuthResponse> {
    // Convert to form data for OAuth2 compatibility
    const formData = new URLSearchParams();
    formData.append('username', credentials.email);
    formData.append('password', credentials.password);
    
    const response = await fetch(`${this.baseUrl}/api/v1/auth/token`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `Login failed: ${response.statusText}`);
    }

    const data = await response.json();
    
    // Store the access token in localStorage for future requests (only on client side)
    if (data.access_token && typeof window !== 'undefined') {
      localStorage.setItem('access_token', data.access_token);
    }
    
    return {
      user: { 
        email: data.user_email, 
        id: 0, 
        username: data.user_email.split('@')[0], 
        credits: 0, 
        subscription_plan: 'free',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      },
      access_token: data.access_token,
      token_type: 'bearer',
    };
  }

  async register(userData: RegisterForm): Promise<AuthResponse> {
    // Backend expects email, password, full_name (not username)
    const registerData = {
      email: userData.email,
      password: userData.password,
      full_name: userData.username, // Use username as full_name
    };
    
    const response = await fetch(`${this.baseUrl}/api/v1/auth/register`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(registerData),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `Registration failed: ${response.statusText}`);
    }

    const data = await response.json();
    return {
      user: data,
      access_token: '', // Registration doesn't return a token
      token_type: 'bearer',
    };
  }

  async logout(): Promise<void> {
    // Clear the access token from localStorage (only on client side)
    if (typeof window !== 'undefined') {
      localStorage.removeItem('access_token');
    }
    
    return this.request<void>('/api/v1/auth/logout', {
      method: 'POST',
    });
  }

  async getCurrentUser(): Promise<User> {
    return this.request<User>('/api/v1/auth/me');
  }

  // Jobs
  async getJobs(): Promise<Job[]> {
    const response = await this.request<{jobs: Job[]}>('/api/v1/jobs/history');
    return response.jobs;
  }

  async getJob(jobId: string): Promise<VideoClipJob> {
    return this.request<VideoClipJob>(`/api/v1/jobs/${jobId}`);
  }

  async getJobStats(): Promise<any> {
    return this.request<any>('/api/v1/jobs/stats');
  }

  // Content Generation
  async generateContent(jobId: string, platforms: string[]): Promise<any[]> {
    return this.request<any[]>('/api/v1/content/generate', {
      method: 'POST',
      body: JSON.stringify({
        job_id: jobId,
        platforms: platforms
      })
    });
  }

  async getContentHistory(): Promise<any[]> {
    return this.request<any[]>('/api/v1/content/history');
  }

  // Magic Commands
  async processMagicCommand(jobId: string, command: string): Promise<any> {
    return this.request<any>('/api/v1/magic/magic-edit', {
      method: 'POST',
      body: JSON.stringify({
        original_video_job_id: jobId,
        magic_command: command
      })
    });
  }

  // File Upload (Chunked)
  async initUpload(file: File): Promise<UploadInitResponse> {
    return this.request<UploadInitResponse>('/api/v1/file-upload/init', {
      method: 'POST',
      body: JSON.stringify({
        filename: file.name,
        file_size: file.size,
        content_type: file.type,
      }),
    });
  }

  async uploadChunk(
    uploadId: string,
    chunkIndex: number,
    chunkData: ArrayBuffer
  ): Promise<void> {
    const formData = new FormData();
    formData.append('chunk_number', chunkIndex.toString());
    formData.append('chunk', new Blob([chunkData]));

    // Get token for authentication
    const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
    const headers: Record<string, string> = {};
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${this.baseUrl}/api/v1/file-upload/chunk/${uploadId}`, {
      method: 'POST',
      credentials: 'include',
      headers,
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `Chunk upload failed: ${response.statusText}`);
    }
  }

  async completeUpload(uploadId: string): Promise<UploadCompleteResponse> {
    return this.request<UploadCompleteResponse>(`/api/v1/file-upload/complete/${uploadId}`, {
      method: 'POST',
    });
  }

  // Video Processing
  async createVideoJob(uploadData: VideoUploadForm): Promise<{ job_id: string }> {
    const formData = new FormData();
    formData.append('file', uploadData.file);
    formData.append('add_captions', uploadData.add_captions.toString());
    formData.append('aspect_ratio', uploadData.aspect_ratio);
    formData.append('platforms', 'TikTok,Instagram,YouTube');

    // Get the access token from localStorage
    const accessToken = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
    
    const headers: Record<string, string> = {};
    
    // Add authorization header if token exists
    if (accessToken) {
      headers['Authorization'] = `Bearer ${accessToken}`;
    }

    const response = await fetch(`${this.baseUrl}/api/v1/video/upload-and-clip`, {
      method: 'POST',
      credentials: 'include',
      headers,
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `Video job creation failed: ${response.statusText}`);
    }

    return response.json();
  }

  // Server-Sent Events for Job Progress
  subscribeToJobEvents(jobId: string, onEvent: (event: JobEvent) => void): () => void {
    const eventSource = new EventSource(`${this.baseUrl}/api/v1/jobs/${jobId}/events`, {
      withCredentials: true,
    });

    eventSource.onmessage = (event) => {
      try {
        const jobEvent: JobEvent = JSON.parse(event.data);
        onEvent(jobEvent);
      } catch (error) {
        console.error('Failed to parse SSE event:', error);
      }
    };

    eventSource.onerror = (error) => {
      console.error('SSE connection error:', error);
      eventSource.close();
    };

    // Return cleanup function
    return () => {
      eventSource.close();
    };
  }

  // Utility method for chunked file upload
  async uploadFileInChunks(file: File, onProgress?: (percent: number) => void): Promise<string> {
    const chunkSize = 1024 * 1024; // 1MB chunks
    const totalChunks = Math.ceil(file.size / chunkSize);

    // Initialize upload
    const initResponse = await this.initUpload(file);
    const { upload_id } = initResponse;

    // Upload chunks
    for (let i = 0; i < totalChunks; i++) {
      const start = i * chunkSize;
      const end = Math.min(start + chunkSize, file.size);
      const chunk = file.slice(start, end);
      const chunkBuffer = await chunk.arrayBuffer();

      await this.uploadChunk(upload_id, i, chunkBuffer);

      if (onProgress) {
        const percent = Math.round(((i + 1) / totalChunks) * 100);
        onProgress(percent);
      }
    }

    // Complete upload
    const completeResponse = await this.completeUpload(upload_id);
    return completeResponse.file_path;
  }
}

export const apiClient = new ApiClient();
export default apiClient;
