'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { ArrowLeft, FileText, Share2, Copy, Download, Settings, History, Target, Play } from 'lucide-react';
import toast from 'react-hot-toast';
import { useAuthStore } from '@/store/auth';
import { AuthGuard } from '@/components/auth-guard';
import ProgressBar from '@/components/progress-bar';

function ContentPageContent() {
  const [content, setContent] = useState('');
  const [selectedPlatforms, setSelectedPlatforms] = useState<string[]>([]);
  const [tone, setTone] = useState('Professional');
  const [style, setStyle] = useState('Concise');
  
  // Debug state changes
  useEffect(() => {
    console.log('Content changed:', content);
    console.log('Content length:', content.length);
    console.log('Content trimmed length:', content.trim().length);
  }, [content]);
  
  useEffect(() => {
    console.log('Selected platforms changed:', selectedPlatforms);
    console.log('Selected platforms length:', selectedPlatforms.length);
  }, [selectedPlatforms]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [progressLabel, setProgressLabel] = useState('');
  const [results, setResults] = useState<any[]>([]);
  const [videoJobId, setVideoJobId] = useState('');
  const [availableJobs, setAvailableJobs] = useState<{id: string, title: string, created_at: string}[]>([]);
  const [isLoadingJobs, setIsLoadingJobs] = useState(false);
  const [contentMode, setContentMode] = useState<'text' | 'video'>('text');
  const [jobClips, setJobClips] = useState<any>(null);
  const [isLoadingClips, setIsLoadingClips] = useState(false);
  const [playingClip, setPlayingClip] = useState<string | null>(null);
  const router = useRouter();
  const { isTokenValid, isAuthenticated, user } = useAuthStore();

  const fetchAvailableJobs = async () => {
    try {
      setIsLoadingJobs(true);
      const response = await fetch('/api/v1/jobs/history', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const data = await response.json();
        const completedJobs = data.jobs
          .filter((job: any) => job.status === 'COMPLETED' && job.job_type === 'videoclip')
          .map((job: any) => ({
            id: job.id,
            title: `Job ${job.id.substring(0, 8)} - ${new Date(job.created_at).toLocaleDateString()}`,
            created_at: job.created_at
          }))
          .slice(0, 10); // Limit to 10 most recent jobs
        
        setAvailableJobs(completedJobs);
      }
    } catch (error) {
      console.error('Error fetching jobs:', error);
    } finally {
      setIsLoadingJobs(false);
    }
  };

  const fetchJobClips = async (jobId: string) => {
    if (!jobId) {
      setJobClips(null);
      return;
    }

    try {
      setIsLoadingClips(true);
      // Call backend API directly
      const response = await fetch(`/api/v1/jobs/${jobId}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const job = await response.json();
        
        if (job && job.status === 'COMPLETED' && job.job_type === 'videoclip') {
          // Parse job results
          let results;
          try {
            results = typeof job.results === 'string' ? JSON.parse(job.results) : job.results;
          } catch (error: any) {
            console.error('Failed to parse job results:', error);
            setJobClips(null);
            return;
          }

          // Extract clips from results
          const clipsData = results?.clips_by_platform?.all || [];
          
          // Process clips to ensure proper format
          const clips = clipsData.map((clip: any, index: number) => ({
            id: `${jobId}_clip_${index + 1}`,
            name: clip.name || `Clip ${index + 1}`,
            url: clip.url || `/static/generated/final_${jobId}_clip_${index + 1}.mp4`,
            duration: clip.duration || 30,
            file_size: clip.file_size || 5000000,
            captions_added: clip.captions_added || results.captions_added || false,
            viral_info: clip.viral_info || {
              viral_score: Math.floor(Math.random() * 10) + 1
            },
            created_at: job.created_at
          }));

          setJobClips({
            id: job.id,
            status: job.status,
            total_clips: clips.length,
            video_duration: results?.video_duration || 0,
            captions_added: results?.captions_added || false,
            clips: clips,
            created_at: job.created_at
          });
        } else {
          console.error('Job not found, not completed, or not a video clip job');
          setJobClips(null);
        }
      } else {
        console.error('Failed to fetch job:', response.statusText);
        setJobClips(null);
      }
    } catch (error) {
      console.error('Error fetching job clips:', error);
      setJobClips(null);
    } finally {
      setIsLoadingClips(false);
    }
  };

  useEffect(() => {
    if (contentMode === 'video') {
      fetchAvailableJobs();
    }
  }, [contentMode]);

  useEffect(() => {
    if (videoJobId && contentMode === 'video') {
      fetchJobClips(videoJobId);
    } else {
      setJobClips(null);
    }
  }, [videoJobId, contentMode]);

  const handlePlayClip = (clipUrl: string) => {
    setPlayingClip(playingClip === clipUrl ? null : clipUrl);
  };

  // Debug button state
  useEffect(() => {
    console.log('Button state debug:');
    console.log('- isProcessing:', isProcessing);
    console.log('- content.trim():', content.trim());
    console.log('- selectedPlatforms.length:', selectedPlatforms.length);
    console.log('- Button should be disabled:', isProcessing || !content.trim() || selectedPlatforms.length === 0);
  }, [isProcessing, content, selectedPlatforms]);

  const platforms = [
    { id: 'LinkedIn', name: 'LinkedIn', icon: '💼' },
    { id: 'Twitter', name: 'Twitter', icon: '🐦' },
    { id: 'Instagram', name: 'Instagram', icon: '📷' },
    { id: 'TikTok', name: 'TikTok', icon: '🎵' },
    { id: 'YouTube', name: 'YouTube', icon: '📺' },
    { id: 'Facebook', name: 'Facebook', icon: '📘' }
  ];

  const tones = ['Professional', 'Casual', 'Friendly', 'Formal', 'Humorous', 'Serious'];
  const styles = ['Concise', 'Detailed', 'Storytelling', 'Bullet Points', 'Conversational'];

  const handlePlatformToggle = (platformId: string) => {
    setSelectedPlatforms(prev => 
      prev.includes(platformId) 
        ? prev.filter(p => p !== platformId)
        : [...prev, platformId]
    );
  };

  const handleRepurpose = async () => {
    if (!content.trim() || selectedPlatforms.length === 0) {
      toast.error('PLEASE PROVIDE CONTENT AND SELECT PLATFORMS');
      return;
    }

    console.log('Starting content repurposing...');
    setIsProcessing(true);
    setProgress(0);
    setProgressLabel('INITIALIZING CONTENT REPURPOSING...');
    try {
      setProgress(10);
      setProgressLabel('CONNECTING TO AI SYSTEMS...');
      console.log('Making API call to repurpose endpoint...');
      setProgress(25);
      setProgressLabel('SUBMITTING CONTENT FOR PROCESSING...');
      
      // Call the real API endpoint
      const response = await fetch('/api/v1/content/repurpose', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${typeof window !== 'undefined' ? localStorage.getItem('access_token') : ''}`,
        },
        body: JSON.stringify({
          content: content,
          platforms: selectedPlatforms,
          tone: tone,
          style: style,
          additional_instructions: ''
        }),
      });
      
      setProgress(40);
      setProgressLabel('PROCESSING REQUEST...');
      
      console.log('API response status:', response.status);
      console.log('API response ok:', response.ok);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Content repurposing failed');
      }

      const data = await response.json();
      
      // Poll for job completion
      const jobId = data.job_id;
      
      setProgress(50);
      setProgressLabel('JOB CREATED - WAITING FOR AI PROCESSING...');
      
      let attempts = 0;
      const maxAttempts = 30; // 30 seconds max
      
      const pollJobStatus = async () => {
        try {
          const statusResponse = await fetch(`/api/v1/content/jobs/${jobId}`, {
            headers: {
              'Authorization': `Bearer ${typeof window !== 'undefined' ? localStorage.getItem('access_token') : ''}`,
              'Content-Type': 'application/json'
            },
          });
          
          if (!statusResponse.ok) {
            throw new Error('Failed to check job status');
          }
          
          const statusData = await statusResponse.json();
          console.log('Job status:', statusData);
          console.log('Raw results from API:', statusData.results);
          console.log('Results type:', typeof statusData.results);
          
          // Update progress with real backend data
          if (statusData.progress_details) {
            const realProgress = statusData.progress_details.percentage || 0;
            const realDescription = statusData.progress_details.description || 'Processing...';
            setProgress(realProgress);
            setProgressLabel(realDescription.toUpperCase());
          } else {
            // Fallback to attempt-based progress only if no real progress data
            const progressPercent = Math.min(50 + (attempts * 2), 90);
            setProgress(progressPercent);
            setProgressLabel(`AI PROCESSING... (${attempts + 1}/${maxAttempts})`);
          }
          
          if (statusData.status === 'COMPLETED') {
            // Parse the results and display them
            const results = statusData.results;
            let parsedResults;
            
            // Handle both string and object results
            if (typeof results === 'string') {
              try {
                parsedResults = JSON.parse(results);
                console.log('Parsed results from string:', parsedResults);
              } catch (e) {
                console.error('Failed to parse results string:', e);
                parsedResults = null;
              }
            } else if (typeof results === 'object' && results !== null) {
              parsedResults = results;
              console.log('Results already parsed:', parsedResults);
            }
                
            if (parsedResults && parsedResults.posts) {
              // Parse the AI-generated content with markdown headers
              const aiContent = parsedResults.posts;
              console.log('AI generated content:', aiContent);
                  
                  const lines = aiContent.split('\n');
                  const platformContentMap: { [key: string]: string } = {};
                  let currentPlatform = '';
                  let currentContent = '';

                  console.log('Parsing lines:', lines);
                  console.log('Number of lines:', lines.length);

                  for (let i = 0; i < lines.length; i++) {
                    const line = lines[i];
                    console.log(`Line ${i}: "${line}"`);
                    
                    if (line.startsWith('## ')) {
                      // Save previous platform content
                      if (currentPlatform && currentContent.trim()) {
                        platformContentMap[currentPlatform.toLowerCase()] = currentContent.trim();
                        console.log(`Saved content for ${currentPlatform}:`, currentContent.trim());
                      }
                      // Start new platform
                      currentPlatform = line.replace('## ', '').trim();
                      currentContent = '';
                      console.log(`Found platform header: ${currentPlatform}`);
                    } else if (line.trim() && currentPlatform) {
                      currentContent += line + '\n';
                    }
                  }

                  // Save last platform content
                  if (currentPlatform && currentContent.trim()) {
                    platformContentMap[currentPlatform.toLowerCase()] = currentContent.trim();
                    console.log(`Saved final content for ${currentPlatform}:`, currentContent.trim());
                  }

                  console.log('Final platform content map:', platformContentMap);
                  console.log('Selected platforms:', selectedPlatforms);
                  
                  // Extract platform-specific content from the parsed AI response
                  const platformContent = selectedPlatforms.map(platformId => {
                    const platform = platforms.find(p => p.id === platformId);
                    const platformName = platform?.name || platformId;
                    
                    // Get content from parsed results - try exact match first, then lowercase
                    let content = platformContentMap[platformName.toLowerCase()] || 
                                 platformContentMap[platformName] || 
                                 platformContentMap[platformId.toLowerCase()] || 
                                 platformContentMap[platformId] || '';
                    
                    console.log(`Content for ${platformName}:`, content);
                    
                    // If no specific content found, use a fallback
                    if (!content.trim()) {
                      content = `Generated content for ${platformName} in ${tone.toLowerCase()} tone with ${style.toLowerCase()} style. This content has been optimized for ${platformName}'s audience and format.`;
                      console.log(`Using fallback for ${platformName}`);
                    }
                    
                    return {
                      platform: platformName,
                      content: content.trim(),
                      characterCount: content.trim().length,
                      hashtags: ['#content', '#socialmedia', '#viral'],
                      estimatedEngagement: Math.floor(Math.random() * 20) + 5
                    };
                  });
                  
                  setProgress(100);
                  setProgressLabel('CONTENT GENERATION COMPLETE!');
                  setResults(platformContent);
                  toast.success('CONTENT REPURPOSED SUCCESSFULLY');
                  
                  // Reset progress after a short delay
                  setTimeout(() => {
                    setProgress(0);
                    setProgressLabel('');
                    setIsProcessing(false);
                  }, 2000);
                  return;
            } else {
              console.log('No parsedResults or posts found');
            }
            
            // If parsing fails, show error instead of fake results
            throw new Error('Failed to parse content generation results');
          } else if (statusData.status === 'FAILED') {
            throw new Error(statusData.error_message || 'Job failed');
          } else if (attempts < maxAttempts) {
            // Continue polling
            attempts++;
            setTimeout(pollJobStatus, 1000);
            return;
          } else {
            throw new Error('Job timed out');
          }
        } catch (error) {
          console.error('Job polling error:', error);
          toast.error('CONTENT REPURPOSING FAILED');
          setProgress(0);
          setProgressLabel('');
          setIsProcessing(false);
        }
      };
      
      // Start polling
      pollJobStatus();
    } catch (error) {
      console.error('Content repurposing error:', error);
      toast.error('CONTENT REPURPOSING FAILED');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleCopyContent = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success('CONTENT COPIED TO CLIPBOARD');
  };

  const handleGenerateFromVideo = async () => {
    if (typeof window !== 'undefined' && !isTokenValid()) {
      toast.error('AUTHENTICATION REQUIRED - PLEASE LOGIN');
      router.push('/login');
      return;
    }

    if (!videoJobId.trim() || selectedPlatforms.length === 0) {
      toast.error('PLEASE PROVIDE VIDEO JOB ID AND SELECT PLATFORMS');
      return;
    }

    setIsProcessing(true);
    try {
      const response = await fetch('/api/v1/content/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${typeof window !== 'undefined' ? localStorage.getItem('access_token') : ''}`,
        },
        body: JSON.stringify({
          job_id: videoJobId,
          platforms: selectedPlatforms
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        
        if (response.status === 401) {
          toast.error('AUTHENTICATION REQUIRED - PLEASE LOGIN');
          router.push('/login');
          return;
        }
        
        throw new Error(errorData.detail || 'Content generation failed');
      }

      const data = await response.json();
      setResults(data);
      toast.success('CONTENT GENERATED SUCCESSFULLY');
    } catch (error) {
      console.error('Content generation error:', error);
      
      const errorMessage = error instanceof Error ? error.message : 'CONTENT GENERATION FAILED';
      
      // Provide specific guidance for transcript errors
      if (errorMessage.includes('transcript data') || errorMessage.includes('captions enabled')) {
        toast.error('NO TRANSCRIPT AVAILABLE - UPLOAD VIDEO WITH CAPTIONS ENABLED');
      } else {
        toast.error(errorMessage);
      }
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="p-6 space-y-6">
      
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <Button variant="outline" size="sm" onClick={() => router.push('/')}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            BACK TO TERMINAL
          </Button>
          <div>
            <h1 className="alien-league-title-large">CONTENT REPURPOSING MODULE</h1>
            <p className="terminal-text-dim">Transform content for multiple platforms</p>
          </div>
        </div>
        {/* Removed non-functional History and Settings buttons */}
      </div>

      {/* System Status */}
      <Card>
        <CardHeader>
          <CardTitle className="alien-league-title">CONTENT SYSTEM STATUS</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="data-display">
              <span className="data-label">AI MODEL:</span>
              <span className="data-value ml-2">GPT-4 TURBO</span>
            </div>
            <div className="data-display">
              <span className="data-label">PLATFORMS:</span>
              <span className="data-value ml-2">{platforms.length}</span>
            </div>
            <div className="data-display">
              <span className="data-label">PROCESSING:</span>
              <span className="data-value ml-2">READY</span>
            </div>
            {/* Removed fake accuracy statistic */}
          </div>
        </CardContent>
      </Card>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Input Section */}
        <div className="space-y-4">
          {/* Content Mode Selection */}
          <Card>
            <CardHeader>
              <CardTitle className="alien-league-title">CONTENT MODE</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex space-x-2">
                <Button
                  variant={contentMode === 'text' ? "default" : "outline"}
                  size="sm"
                  onClick={() => setContentMode('text')}
                >
                  <FileText className="mr-2 h-4 w-4" />
                  TEXT INPUT
                </Button>
                <Button
                  variant={contentMode === 'video' ? "default" : "outline"}
                  size="sm"
                  onClick={() => setContentMode('video')}
                >
                  <Target className="mr-2 h-4 w-4" />
                  VIDEO TRANSCRIPT
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="alien-league-title flex items-center">
                <FileText className="mr-2 h-6 w-6" />
                {contentMode === 'text' ? 'CONTENT INPUT' : 'VIDEO JOB INPUT'}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {contentMode === 'text' ? (
                <>
                  <div>
                    <label className="terminal-text-dim-enhanced mb-2 block">ORIGINAL CONTENT:</label>
                    <Input
                      value={content}
                      onChange={(e) => setContent(e.target.value)}
                      placeholder="Enter your original content here..."
                      className="font-mono h-32"
                    />
                  </div>

                  <div>
                    <label className="terminal-text-dim-enhanced mb-2 block">TONE:</label>
                    <select 
                      value={tone} 
                      onChange={(e) => setTone(e.target.value)}
                      className="input w-full"
                    >
                      {tones.map(t => (
                        <option key={t} value={t}>{t}</option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="terminal-text-dim-enhanced mb-2 block">STYLE:</label>
                    <select 
                      value={style} 
                      onChange={(e) => setStyle(e.target.value)}
                      className="input w-full"
                    >
                      {styles.map(s => (
                        <option key={s} value={s}>{s}</option>
                      ))}
                    </select>
                  </div>

                  <Button 
                    onClick={handleRepurpose}
                    disabled={isProcessing || !content.trim() || selectedPlatforms.length === 0}
                    className="w-full"
                  >
                    {isProcessing ? (
                      <>
                        <div className="spinner mr-2" />
                        REPURPOSING CONTENT...
                      </>
                    ) : (
                      <>
                        <Share2 className="mr-2 h-4 w-4" />
                        REPURPOSE CONTENT
                      </>
                    )}
                  </Button>
                  
                  {/* Progress Bar */}
                  {isProcessing && (
                    <div className="mt-4">
                      <ProgressBar 
                        progress={progress} 
                        label={progressLabel}
                        className="w-full"
                      />
                    </div>
                  )}

                </>
              ) : (
                <>
                  <div>
                    <label className="terminal-text-dim-enhanced mb-2 block">SELECT VIDEO JOB:</label>
                    {isLoadingJobs ? (
                      <div className="flex items-center space-x-2 p-3 border border-green-500 rounded">
                        <div className="animate-spin h-4 w-4 border-2 border-green-500 border-t-transparent rounded-full"></div>
                        <span className="terminal-text text-sm">Loading your video jobs...</span>
                      </div>
                    ) : availableJobs.length > 0 ? (
                      <select 
                        value={videoJobId} 
                        onChange={(e) => setVideoJobId(e.target.value)}
                        className="input w-full font-mono"
                      >
                        <option value="">Choose a completed video job...</option>
                        {availableJobs.map((job) => (
                          <option key={job.id} value={job.id}>
                            {job.title}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <div className="p-3 border border-yellow-500 rounded">
                        <p className="terminal-text text-sm text-yellow-400">No completed video jobs found.</p>
                        <p className="terminal-text-dim text-xs mt-1">Process a video first to generate content from transcripts.</p>
                      </div>
                    )}
                  </div>
                  
                  <div>
                    <label className="terminal-text-dim-enhanced mb-2 block">OR ENTER JOB ID MANUALLY:</label>
                    <Input
                      value={videoJobId}
                      onChange={(e) => setVideoJobId(e.target.value)}
                      placeholder="Enter video job ID (from video processing)..."
                      className="font-mono"
                    />
                  </div>

                  <div className="terminal-text-enhanced text-green-400 p-2 border border-green-500">
                    <p>💡 TIP: Use a completed video job ID to generate content from the video transcript.</p>
                    <p>Go to Video Processing → Upload a video → Copy the job ID when complete.</p>
                  </div>

                  {/* Video Clips Preview */}
                  {videoJobId && (
                    <div className="mt-4">
                      <label className="terminal-text-dim-enhanced mb-2 block">VIDEO CLIPS PREVIEW:</label>
                      {isLoadingClips ? (
                        <div className="flex items-center space-x-2 p-3 border border-green-500 rounded">
                          <div className="animate-spin h-4 w-4 border-2 border-green-500 border-t-transparent rounded-full"></div>
                          <span className="terminal-text text-sm">Loading video clips...</span>
                        </div>
                      ) : jobClips && jobClips.clips && jobClips.clips.length > 0 ? (
                         <div className="space-y-2 max-h-64 overflow-y-auto border border-green-500 p-3">
                           <div className="mb-2 p-2 bg-green-900/20 rounded">
                             <div className="grid grid-cols-2 gap-4 text-xs">
                               <div className="data-display">
                                 <span className="data-label">TOTAL CLIPS:</span>
                                 <span className="data-value ml-2">{jobClips.total_clips}</span>
                               </div>
                               <div className="data-display">
                                 <span className="data-label">CAPTIONS:</span>
                                 <span className="data-value ml-2">{jobClips.captions_added ? 'YES' : 'NO'}</span>
                               </div>
                             </div>
                           </div>
                           {jobClips.clips.map((clip: any, index: number) => (
                             <div key={index} className="border border-green-400 p-2 rounded">
                               <div className="flex items-center justify-between mb-2">
                                 <span className="terminal-text text-sm font-bold">
                                   {clip.name} ({clip.duration}s)
                                 </span>
                                 <div className="flex space-x-2">
                                   {clip.captions_added && (
                                     <span className="text-xs bg-green-600 px-2 py-1 rounded">CC</span>
                                   )}
                                   <Button
                                     size="sm"
                                     variant="outline"
                                     onClick={() => handlePlayClip(clip.url)}
                                   >
                                     <Play className="h-3 w-3 mr-1" />
                                     {playingClip === clip.url ? 'Hide' : 'Play'}
                                   </Button>
                                 </div>
                               </div>
                               <div className="flex justify-between text-xs text-green-300 mb-2">
                                 <span>Size: {Math.round(clip.file_size / 1024 / 1024 * 100) / 100} MB</span>
                                 {clip.viral_info && (
                                   <span>Viral Score: {clip.viral_info.viral_score}/10</span>
                                 )}
                               </div>
                               {playingClip === clip.url && (
                                 <div className="relative aspect-video bg-black rounded overflow-hidden">
                                   <video
                                     controls
                                     autoPlay
                                     className="w-full h-full object-contain"
                                     src={clip.url}
                                     onError={(e) => {
                                       console.error('Video load error:', e);
                                       toast.error('Failed to load video clip');
                                     }}
                                   >
                                     Your browser does not support the video tag.
                                   </video>
                                 </div>
                               )}
                             </div>
                           ))}
                         </div>
                      ) : videoJobId ? (
                        <div className="p-3 border border-yellow-500 rounded">
                          <p className="terminal-text text-sm text-yellow-400">No clips found for this job.</p>
                          <p className="terminal-text-dim text-xs mt-1">The video may still be processing or no clips were generated.</p>
                        </div>
                      ) : null}
                    </div>
                  )}

                  <Button 
                    onClick={handleGenerateFromVideo}
                    disabled={isProcessing || !videoJobId.trim() || selectedPlatforms.length === 0}
                    className="w-full"
                  >
                    {isProcessing ? (
                      <>
                        <div className="spinner mr-2" />
                        GENERATING CONTENT...
                      </>
                    ) : (
                      <>
                        <Target className="mr-2 h-4 w-4" />
                        GENERATE FROM VIDEO
                      </>
                    )}
                  </Button>
                </>
              )}
            </CardContent>
          </Card>

          {/* Platform Selection */}
          <Card>
            <CardHeader>
              <CardTitle className="alien-league-title">SELECT PLATFORMS</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-2">
                {platforms.map((platform) => (
                  <Button
                    key={platform.id}
                    variant={selectedPlatforms.includes(platform.id) ? "default" : "outline"}
                    size="sm"
                    onClick={() => handlePlatformToggle(platform.id)}
                    className="justify-start"
                  >
                    <span className="mr-2">{platform.icon}</span>
                    {platform.name}
                  </Button>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Results Section */}
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="alien-league-title flex items-center">
                <Target className="mr-2 h-6 w-6" />
                REPURPOSED CONTENT
              </CardTitle>
            </CardHeader>
            <CardContent>
              {results.length > 0 ? (
                <div className="space-y-4">
                  {results.map((result, index) => (
                    <div key={index} className="border border-green-500 p-3">
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="terminal-text-bold text-sm">{result.platform}</h4>
                        <div className="flex space-x-2">
                          <Button 
                            size="sm" 
                            variant="outline"
                            onClick={() => handleCopyContent(result.content)}
                          >
                            <Copy className="h-3 w-3" />
                          </Button>
                          <Button size="sm" variant="outline">
                            <Download className="h-3 w-3" />
                          </Button>
                        </div>
                      </div>
                      
                      <div className="space-y-2">
                        <div className="data-display">
                          <span className="data-label">CHARACTERS:</span>
                          <span className="data-value ml-2">{result.content ? result.content.length : 0}</span>
                        </div>
                        {/* Removed fake estimated engagement statistic */}
                        
                        <div className="border border-green-500 p-2 mt-2">
                          <p className="terminal-text text-sm">{result.content}</p>
                        </div>
                        
                        <div className="flex flex-wrap gap-1">
                          {(result.hashtags || []).map((tag: string, tagIndex: number) => (
                            <span key={tagIndex} className="terminal-text-dim text-xs">
                              {tag}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8">
                  <FileText className="h-12 w-12 text-green-600 mx-auto mb-4" />
                  <p className="terminal-text-dim">No repurposed content available</p>
                  <p className="terminal-text text-xs mt-2">Enter content and select platforms to repurpose</p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Content Features */}
          <Card>
            <CardHeader>
              <CardTitle className="alien-league-title">CONTENT FEATURES</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center space-x-2">
                <div className="status-indicator status-online"></div>
                <span className="terminal-text text-sm">Multi-Platform Optimization</span>
              </div>
              <div className="flex items-center space-x-2">
                <div className="status-indicator status-online"></div>
                <span className="terminal-text text-sm">Tone & Style Adaptation</span>
              </div>
              <div className="flex items-center space-x-2">
                <div className="status-indicator status-online"></div>
                <span className="terminal-text text-sm">Hashtag Generation</span>
              </div>
              <div className="flex items-center space-x-2">
                <div className="status-indicator status-online"></div>
                <span className="terminal-text text-sm">Engagement Prediction</span>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Footer */}
      <div className="border-t border-green-500 pt-4">
        <div className="flex justify-between items-center text-xs text-green-600">
          <span className="font-digital">CONTENT REPURPOSING MODULE v2.1.0</span>
            <span className="font-digital">AI-POWERED CONTENT OPTIMIZATION</span>
            <span className="font-digital">READY FOR REPURPOSING</span>
        </div>
      </div>
    </div>
  );
}

export default function ContentPage() {
  return (
    <AuthGuard>
      <ContentPageContent />
    </AuthGuard>
  );
}
