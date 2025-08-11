import { create } from 'zustand';
import { Job, VideoClipJob, JobEvent } from '@/types';
import apiClient from '@/lib/api';

interface JobsState {
  jobs: Job[];
  currentJob: VideoClipJob | null;
  isLoading: boolean;
  error: string | null;
  uploadProgress: number;
  isUploading: boolean;
}

interface JobsActions {
  fetchJobs: () => Promise<void>;
  fetchJob: (jobId: string) => Promise<void>;
  createVideoJob: (uploadData: {
    file: File;
    add_captions: boolean;
    aspect_ratio: '9:16' | '1:1' | '16:9';
  }) => Promise<string>;
  subscribeToJobEvents: (jobId: string) => void;
  unsubscribeFromJobEvents: () => void;
  clearError: () => void;
  setUploadProgress: (progress: number) => void;
  setIsUploading: (isUploading: boolean) => void;
}

type JobsStore = JobsState & JobsActions;

export const useJobsStore = create<JobsStore>((set, get) => ({
  // State
  jobs: [],
  currentJob: null,
  isLoading: false,
  error: null,
  uploadProgress: 0,
  isUploading: false,

  // Actions
  fetchJobs: async () => {
    set({ isLoading: true, error: null });
    try {
      const jobs = await apiClient.getJobs();
      set({ jobs, isLoading: false });
    } catch (error) {
      set({
        isLoading: false,
        error: error instanceof Error ? error.message : 'Failed to fetch jobs',
      });
    }
  },

  fetchJob: async (jobId: string) => {
    console.log('🔍 JobsStore: Fetching job with ID:', jobId);
    set({ isLoading: true, error: null });
    try {
      const job = await apiClient.getJob(jobId);
      console.log('🔍 JobsStore: Received job data:', job);
      console.log('🔍 JobsStore: Job status:', job?.status);
      console.log('🔍 JobsStore: Has results:', !!job?.results);
      if (job?.results) {
        console.log('🔍 JobsStore: Results structure:', Object.keys(job.results));
        const clips = job.results.clips_by_platform?.all || [];
        console.log('🔍 JobsStore: Number of clips found:', clips.length);
      }
      set({ currentJob: job, isLoading: false });
    } catch (error) {
      console.error('🔍 JobsStore: Error fetching job:', error);
      set({
        isLoading: false,
        error: error instanceof Error ? error.message : 'Failed to fetch job',
      });
    }
  },

  createVideoJob: async (uploadData) => {
    set({ isUploading: true, uploadProgress: 0, error: null });
    
    try {
      // Upload file in chunks with progress tracking
      const filePath = await apiClient.uploadFileInChunks(uploadData.file, (progress) => {
        set({ uploadProgress: progress });
      });

      // Create video job
      const { job_id } = await apiClient.createVideoJob(uploadData);

      set({ isUploading: false, uploadProgress: 100 });
      
      // Subscribe to job events
      get().subscribeToJobEvents(job_id);
      
      return job_id;
    } catch (error) {
      set({
        isUploading: false,
        uploadProgress: 0,
        error: error instanceof Error ? error.message : 'Failed to create video job',
      });
      throw error;
    }
  },

  subscribeToJobEvents: (jobId: string) => {
    const unsubscribe = apiClient.subscribeToJobEvents(jobId, (event: JobEvent) => {
      const { currentJob, jobs } = get();
      
      // Update current job if it matches
      if (currentJob?.id === jobId) {
        set({
          currentJob: {
            ...currentJob,
            status: event.status === 'queued' ? 'PENDING' : 
                   event.status === 'processing' ? 'IN_PROGRESS' : 
                   event.status === 'completed' ? 'COMPLETED' : 'FAILED',
            progress_details: event.status === 'processing' ? {
              description: `Processing ${event.stage || 'video'}...`,
              percentage: event.percent || 0,
              stage: event.stage,
            } : undefined,
            error_message: event.status === 'failed' ? event.error : undefined,
          },
        });
      }

      // Update job in jobs list
      const updatedJobs = jobs.map(job => 
        job.id === jobId 
          ? {
              ...job,
              status: (event.status === 'queued' ? 'PENDING' : 
                     event.status === 'processing' ? 'IN_PROGRESS' : 
                     event.status === 'completed' ? 'COMPLETED' : 'FAILED') as Job['status'],
              progress_details: event.status === 'processing' ? {
                description: `Processing ${event.stage || 'video'}...`,
                percentage: event.percent || 0,
                stage: event.stage,
              } : undefined,
              error_message: event.status === 'failed' ? event.error : undefined,
            } as Job
          : job
      );
      
      set({ jobs: updatedJobs });

      // If job is completed or failed, fetch the full job data
      if (event.status === 'completed' || event.status === 'failed') {
        get().fetchJob(jobId);
      }
    });

    // Store unsubscribe function (you might want to store this in a ref or state)
    // For now, we'll just call it when needed
    return unsubscribe;
  },

  unsubscribeFromJobEvents: () => {
    // This would be called when component unmounts
    // The actual cleanup is handled by the EventSource
  },

  clearError: () => {
    set({ error: null });
  },

  setUploadProgress: (progress: number) => {
    set({ uploadProgress: progress });
  },

  setIsUploading: (isUploading: boolean) => {
    set({ isUploading });
  },
}));
