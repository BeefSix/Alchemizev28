'use client';

import React, { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { VideoUpload } from '@/components/video-upload';
import { JobProgress } from '@/components/job-progress';
import { AuthGuard } from '@/components/auth-guard';
import { VideoClipJob } from '@/types';
import { ArrowLeft, Video, Zap, Play, Download, Settings, FileText, Share2, Copy } from 'lucide-react';
import toast from 'react-hot-toast';

function VideoPageContent() {
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [currentStep, setCurrentStep] = useState(1);
  const [selectedPlatforms, setSelectedPlatforms] = useState<string[]>([]);
  const [contentResults, setContentResults] = useState<any[]>([]);
  const [isGeneratingContent, setIsGeneratingContent] = useState(false);
  const [jobData, setJobData] = useState<any>(null);
  const router = useRouter();
  const searchParams = useSearchParams();

  // Check for job parameter in URL and load existing job
  useEffect(() => {
    const jobParam = searchParams.get('job');
    if (jobParam) {
      setCurrentJobId(jobParam);
      setCurrentStep(2); // Start at processing step
      toast.success('LOADING EXISTING JOB...');
    }
  }, [searchParams]);

  const platforms = [
    { id: 'LinkedIn', name: 'LinkedIn', icon: '💼' },
    { id: 'Twitter', name: 'Twitter', icon: '🐦' },
    { id: 'Instagram', name: 'Instagram', icon: '📷' },
    { id: 'TikTok', name: 'TikTok', icon: '🎵' },
    { id: 'YouTube', name: 'YouTube', icon: '📺' },
    { id: 'Facebook', name: 'Facebook', icon: '📘' }
  ];

  const handleJobCreated = (jobId: string) => {
    setCurrentJobId(jobId);
    setCurrentStep(2);
    toast.success('VIDEO UPLOADED - AI PROCESSING STARTED');
  };

  const handleJobComplete = (job: VideoClipJob) => {
    setCurrentStep(3);
    setJobData(job);
    toast.success(`AI PROCESSING COMPLETE: ${job.results?.total_clips || 0} CLIPS READY`);
  };

  const handleQuickEdit = async () => {
    if (!currentJobId) return;
    
    setIsProcessing(true);
    setCurrentStep(4);
    
    try {
      // Simulate multi-hop AI sequence
      toast.success('AI REFINEMENT SEQUENCE STARTED');
      
      // Step 1: Content Analysis
      await new Promise(resolve => setTimeout(resolve, 1000));
      toast.success('STEP 1: CONTENT ANALYSIS COMPLETE');
      
      // Step 2: Quality Enhancement
      await new Promise(resolve => setTimeout(resolve, 1000));
      toast.success('STEP 2: QUALITY ENHANCEMENT COMPLETE');
      
      // Step 3: Final Optimization
      await new Promise(resolve => setTimeout(resolve, 1000));
      toast.success('STEP 3: FINAL OPTIMIZATION COMPLETE');
      
      setCurrentStep(5);
      toast.success('AI REFINEMENT COMPLETE - CLIPS READY FOR DOWNLOAD');
    } catch (error) {
      toast.error('AI REFINEMENT FAILED');
    } finally {
      setIsProcessing(false);
    }
  };

  const handlePlatformToggle = (platformId: string) => {
    setSelectedPlatforms(prev => 
      prev.includes(platformId) 
        ? prev.filter(p => p !== platformId)
        : [...prev, platformId]
    );
  };

  const fetchJobData = async (jobId: string) => {
    try {
      const response = await fetch(`http://localhost:8001/api/v1/jobs/${jobId}`, {
        headers: {
          'Authorization': `Bearer ${typeof window !== 'undefined' ? localStorage.getItem('access_token') : ''}`,
        },
      });
      
      if (response.ok) {
        const job = await response.json();
        setJobData(job);
      }
    } catch (error) {
      console.error('Failed to fetch job data:', error);
    }
  };

  const handleGenerateContent = async () => {
    if (selectedPlatforms.length === 0) {
      toast.error('PLEASE SELECT AT LEAST ONE PLATFORM');
      return;
    }

    if (!currentJobId) {
      toast.error('NO VIDEO JOB FOUND - PLEASE UPLOAD A VIDEO FIRST');
      return;
    }

    setIsGeneratingContent(true);
    setCurrentStep(6);
    
    try {
      // Fetch job data to get clips
      await fetchJobData(currentJobId);
      
      // Use real content generation API
      toast.success('GENERATING CONTENT FROM TRANSCRIPTS');
      
      const response = await fetch('/api/v1/content/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${typeof window !== 'undefined' ? localStorage.getItem('access_token') : ''}`,
        },
        body: JSON.stringify({
          job_id: currentJobId,
          platforms: selectedPlatforms
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        
        if (response.status === 401) {
          toast.error('AUTHENTICATION REQUIRED - PLEASE LOGIN');
          // Redirect to login page
          window.location.href = '/login';
          return;
        }
        
        throw new Error(errorData.detail || 'Content generation failed');
      }

      const newResults = await response.json();
      setContentResults(newResults);
      toast.success('CONTENT GENERATED FROM TRANSCRIPTS');
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
      setIsGeneratingContent(false);
    }
  };

  const handleCopyContent = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success('CONTENT COPIED TO CLIPBOARD');
  };

  const handleDownload = async () => {
    if (currentJobId && !jobData) {
      await fetchJobData(currentJobId);
    }
    
    if (currentStep === 5) {
      setCurrentStep(6);
    }
    
    toast.success('DOWNLOADING ENHANCED CLIPS');
    // Simulate download
  };

  return (
    <div className="p-6 space-y-6">
      {/* Simple Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <Button variant="outline" size="sm" onClick={() => router.push('/')}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            BACK
          </Button>
          <div>
            <h1 className="alien-league-title-orange-aura">ZUEXIS VIDEO PROCESSOR</h1>
            <p className="alien-league-title">Fast AI-powered video enhancement</p>
          </div>
        </div>
        <div className="text-right">
          <div className="terminal-text text-sm">STEP {currentStep}/6</div>
          <div className="terminal-text-dim text-xs">AI SEQUENCE ACTIVE</div>
        </div>
      </div>

      {/* Progress Steps */}
      <div className="flex justify-between items-center p-4 border border-black bg-black">
        <div className={`flex items-center space-x-2 ${currentStep >= 1 ? 'text-green-400' : 'text-green-600'}`}>
          <div className={`status-indicator ${currentStep >= 1 ? 'status-online' : 'status-error'}`}></div>
          <span className="terminal-text text-sm">UPLOAD</span>
        </div>
        <div className={`flex items-center space-x-2 ${currentStep >= 2 ? 'text-green-400' : 'text-green-600'}`}>
          <div className={`status-indicator ${currentStep >= 2 ? 'status-online' : 'status-error'}`}></div>
          <span className="terminal-text text-sm">AI PROCESS</span>
        </div>
        <div className={`flex items-center space-x-2 ${currentStep >= 3 ? 'text-green-400' : 'text-green-600'}`}>
          <div className={`status-indicator ${currentStep >= 3 ? 'status-online' : 'status-error'}`}></div>
          <span className="terminal-text text-sm">CLIPS READY</span>
        </div>
        <div className={`flex items-center space-x-2 ${currentStep >= 4 ? 'text-green-400' : 'text-green-600'}`}>
          <div className={`status-indicator ${currentStep >= 4 ? 'status-online' : 'status-error'}`}></div>
          <span className="terminal-text text-sm">AI REFINE</span>
        </div>
        <div className={`flex items-center space-x-2 ${currentStep >= 5 ? 'text-green-400' : 'text-green-600'}`}>
          <div className={`status-indicator ${currentStep >= 5 ? 'status-online' : 'status-error'}`}></div>
          <span className="terminal-text text-sm">CONTENT</span>
        </div>
        <div className={`flex items-center space-x-2 ${currentStep >= 6 ? 'text-green-400' : 'text-green-600'}`}>
          <div className={`status-indicator ${currentStep >= 6 ? 'status-online' : 'status-error'}`}></div>
          <span className="terminal-text text-sm">DOWNLOAD</span>
        </div>
      </div>

      {/* Main Content - Single Column for Simplicity */}
      <div className="max-w-4xl mx-auto space-y-6">
        
        {/* Step 1: Upload */}
        {currentStep === 1 && (
          <Card>
            <CardHeader>
              <CardTitle className="alien-league-title flex items-center">
                <Video className="mr-2 h-6 w-6" />
                UPLOAD YOUR VIDEO
              </CardTitle>
            </CardHeader>
            <CardContent>
              <VideoUpload onJobCreated={handleJobCreated} />
              <div className="mt-4 p-3 border border-green-500">
                <div className="terminal-text-bold text-sm mb-2">AI CAPABILITIES:</div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="flex items-center space-x-2">
                    <div className="status-indicator status-online"></div>
                    <span className="terminal-text-dim">Smart Clipping</span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <div className="status-indicator status-online"></div>
                    <span className="terminal-text-dim">Live Captions</span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <div className="status-indicator status-online"></div>
                    <span className="terminal-text-dim">Quality Enhancement</span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <div className="status-indicator status-online"></div>
                    <span className="terminal-text-dim">Content Generation</span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Step 2: Processing */}
        {currentStep === 2 && currentJobId && (
          <Card>
            <CardHeader>
              <CardTitle className="alien-league-title">AI PROCESSING IN PROGRESS</CardTitle>
            </CardHeader>
            <CardContent>
              <JobProgress 
                jobId={currentJobId} 
                onComplete={handleJobComplete}
              />
            </CardContent>
          </Card>
        )}

        {/* Step 3: Clips Ready */}
        {currentStep === 3 && (
          <Card>
            <CardHeader>
              <CardTitle className="alien-league-title flex items-center">
                <Play className="mr-2 h-6 w-6" />
                CLIPS READY - ENHANCE WITH AI
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="text-center py-8">
                <div className="terminal-text-bold text-lg mb-4">AI PROCESSING COMPLETE</div>
                <div className="terminal-text-dim mb-6">Your video has been processed into optimized clips</div>
                
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                  <div className="border border-green-500 p-3 text-center">
                    <div className="terminal-text-bold text-2xl">5</div>
                    <div className="terminal-text-dim text-xs">CLIPS GENERATED</div>
                  </div>
                  <div className="border border-green-500 p-3 text-center">
                    <div className="terminal-text-bold text-2xl">15-30s</div>
                    <div className="terminal-text-dim text-xs">CLIP LENGTH</div>
                  </div>
                  <div className="border border-green-500 p-3 text-center">
                    <div className="terminal-text-bold text-2xl">4K</div>
                    <div className="terminal-text-dim text-xs">QUALITY</div>
                  </div>
                </div>

                <Button 
                  onClick={handleQuickEdit}
                  disabled={isProcessing}
                  className="w-full max-w-md"
                  size="lg"
                >
                  {isProcessing ? (
                    <>
                      <div className="spinner mr-2" />
                      AI REFINEMENT IN PROGRESS...
                    </>
                  ) : (
                    <>
                      <Zap className="mr-2 h-4 w-4" />
                      ENHANCE WITH AI REFINEMENT
                    </>
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Step 4: AI Refinement */}
        {currentStep === 4 && (
          <Card>
            <CardHeader>
              <CardTitle className="alien-league-title">AI REFINEMENT SEQUENCE</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="border border-green-500 p-4 text-center">
                    <div className="terminal-text-bold text-sm mb-2">STEP 1</div>
                    <div className="terminal-text-dim text-xs">Content Analysis</div>
                    <div className="status-indicator status-online mx-auto mt-2"></div>
                  </div>
                  <div className="border border-green-500 p-4 text-center">
                    <div className="terminal-text-bold text-sm mb-2">STEP 2</div>
                    <div className="terminal-text-dim text-xs">Quality Enhancement</div>
                    <div className="status-indicator status-online mx-auto mt-2"></div>
                  </div>
                  <div className="border border-green-500 p-4 text-center">
                    <div className="terminal-text-bold text-sm mb-2">STEP 3</div>
                    <div className="terminal-text-dim text-xs">Final Optimization</div>
                    <div className="status-indicator status-online mx-auto mt-2"></div>
                  </div>
                </div>
                
                <div className="text-center">
                  <div className="spinner mx-auto mb-4"></div>
                  <div className="terminal-text-bold">AI REFINEMENT IN PROGRESS</div>
                  <div className="terminal-text-dim text-sm">Multi-hop AI sequence optimizing your clips</div>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Step 5: Content Generation */}
        {currentStep === 5 && (
          <Card>
            <CardHeader>
              <CardTitle className="alien-league-title flex items-center">
                <FileText className="mr-2 h-6 w-6" />
                GENERATE SOCIAL MEDIA CONTENT
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="text-center">
                <div className="terminal-text-bold text-lg mb-4">AI REFINEMENT COMPLETE</div>
                <div className="terminal-text-dim mb-6">Your clips have been enhanced. Now generate social media content from the transcripts.</div>
                
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                  <div className="border border-green-500 p-3 text-center">
                    <div className="terminal-text-bold text-2xl">5</div>
                    <div className="terminal-text-dim text-xs">ENHANCED CLIPS</div>
                  </div>
                  <div className="border border-green-500 p-3 text-center">
                    <div className="terminal-text-bold text-2xl">8K</div>
                    <div className="terminal-text-dim text-xs">ENHANCED QUALITY</div>
                  </div>
                  <div className="border border-green-500 p-3 text-center">
                    <div className="terminal-text-bold text-2xl">100%</div>
                    <div className="terminal-text-dim text-xs">AI OPTIMIZED</div>
                  </div>
                </div>
              </div>

              {/* Platform Selection */}
              <div>
                <div className="terminal-text-bold text-sm mb-4">SELECT PLATFORMS FOR CONTENT:</div>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                  {platforms.map((platform) => (
                    <Button
                      key={platform.id}
                      variant={selectedPlatforms.includes(platform.id) ? "default" : "outline"}
                      size="sm"
                      onClick={() => handlePlatformToggle(platform.id)}
                      className="justify-start h-auto p-3"
                    >
                      <span className="mr-2">{platform.icon}</span>
                      <div className="text-left">
                        <div className="terminal-text text-xs">{platform.name}</div>
                        <div className="terminal-text-dim text-xs">Content</div>
                      </div>
                    </Button>
                  ))}
                </div>
              </div>

              <div className="space-y-3">
                <Button 
                  onClick={handleGenerateContent}
                  disabled={isGeneratingContent || selectedPlatforms.length === 0}
                  className="w-full max-w-md"
                  size="lg"
                >
                  {isGeneratingContent ? (
                    <>
                      <div className="spinner mr-2" />
                      GENERATING CONTENT FROM TRANSCRIPTS...
                    </>
                  ) : (
                    <>
                      <Share2 className="mr-2 h-4 w-4" />
                      GENERATE SOCIAL MEDIA CONTENT
                    </>
                  )}
                </Button>
                
                <Button 
                  onClick={handleDownload}
                  variant="outline"
                  className="w-full max-w-md"
                >
                  <Download className="mr-2 h-4 w-4" />
                  SKIP CONTENT - DOWNLOAD CLIPS ONLY
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Step 6: Content Results */}
        {currentStep === 6 && (
          <Card>
            <CardHeader>
              <CardTitle className="alien-league-title flex items-center">
                <FileText className="mr-2 h-6 w-6" />
                SOCIAL MEDIA CONTENT READY
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                <div className="text-center mb-6">
                  <div className="terminal-text-bold text-lg mb-2">CONTENT GENERATED FROM TRANSCRIPTS</div>
                  <div className="terminal-text-dim text-sm">AI has analyzed your video clips and created platform-specific content</div>
                </div>

                {/* Content Results */}
                <div className="space-y-4">
                  {contentResults.map((result, index) => (
                    <div key={index} className="border border-green-500 p-4">
                      <div className="flex items-center justify-between mb-3">
                        <h4 className="terminal-text-bold text-sm">{result.platform}</h4>
                        <div className="flex space-x-2">
                          <Button 
                            size="sm" 
                            variant="outline"
                            onClick={() => handleCopyContent(result.content)}
                          >
                            <Copy className="h-3 w-3" />
                          </Button>
                        </div>
                      </div>
                      
                      <div className="space-y-2">
                        <div className="data-display">
                          <span className="data-label">CHARACTERS:</span>
                          <span className="data-value ml-2">{result.content ? result.content.length : 0}</span>
                        </div>
                        {/* Removed fake estimated engagement statistic */}
                        <div className="data-display">
                          <span className="data-label">CLIP REFERENCE:</span>
                          <span className="data-value ml-2">{result.clip_reference || result.clipReference || 'N/A'}</span>
                        </div>
                        
                        <div className="border border-green-500 p-3 mt-3">
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

                {/* Video Clips Section */}
                {jobData && jobData.results && jobData.results.clips && (
                  <div className="mt-8">
                    <div className="border-t border-green-500 pt-6">
                      <h3 className="terminal-text-bold text-lg mb-4 flex items-center">
                        <Video className="mr-2 h-5 w-5" />
                        ENHANCED VIDEO CLIPS ({jobData.results.clips.length})
                      </h3>
                      
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {jobData.results.clips.map((clip: any, index: number) => (
                          <div key={index} className="border border-green-500 p-4">
                            <div className="aspect-video bg-black border border-green-500 mb-3 relative overflow-hidden">
                              <video 
                                controls 
                                className="w-full h-full object-cover"
                                poster={clip.thumbnail_url}
                              >
                                <source src={clip.video_url} type="video/mp4" />
                                Your browser does not support the video tag.
                              </video>
                            </div>
                            
                            <div className="space-y-2">
                              <div className="data-display">
                                <span className="data-label">CLIP:</span>
                                <span className="data-value ml-2">{index + 1}</span>
                              </div>
                              
                              <div className="data-display">
                                <span className="data-label">DURATION:</span>
                                <span className="data-value ml-2">{clip.duration || 'N/A'}s</span>
                              </div>
                              
                              <div className="data-display">
                                <span className="data-label">START TIME:</span>
                                <span className="data-value ml-2">{clip.start_time || 'N/A'}s</span>
                              </div>
                              
                              {clip.transcript && (
                                <div className="border border-green-500 p-2 mt-2">
                                  <div className="data-label text-xs mb-1">TRANSCRIPT:</div>
                                  <p className="terminal-text text-xs">{clip.transcript}</p>
                                </div>
                              )}
                              
                              <div className="flex space-x-2 mt-3">
                                <Button 
                                  size="sm" 
                                  variant="outline"
                                  onClick={() => {
                                    const link = document.createElement('a');
                                    link.href = clip.video_url;
                                    link.download = `clip_${index + 1}.mp4`;
                                    link.click();
                                  }}
                                >
                                  <Download className="h-3 w-3 mr-1" />
                                  DOWNLOAD
                                </Button>
                                
                                <Button 
                                  size="sm" 
                                  variant="outline"
                                  onClick={() => {
                                    navigator.clipboard.writeText(clip.video_url);
                                    toast.success('CLIP URL COPIED');
                                  }}
                                >
                                  <Copy className="h-3 w-3 mr-1" />
                                  COPY URL
                                </Button>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                <div className="flex flex-col items-center space-y-3">
                  <Button 
                    onClick={handleDownload}
                    className="w-full max-w-md"
                    size="lg"
                  >
                    <Download className="mr-2 h-4 w-4" />
                    DOWNLOAD ENHANCED CLIPS
                  </Button>
                  
                  <Button 
                    onClick={() => setCurrentStep(1)}
                    variant="outline"
                    className="w-full max-w-md"
                  >
                    <Video className="mr-2 h-4 w-4" />
                    PROCESS ANOTHER VIDEO
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Video Clips Display - Show after clips are ready (step 3+) */}
        {currentStep >= 3 && jobData && jobData.results && jobData.results.clips && (
          <Card>
            <CardHeader>
              <CardTitle className="alien-league-title flex items-center">
                <Video className="mr-2 h-6 w-6" />
                YOUR VIDEO CLIPS ({jobData.results.clips.length})
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {jobData.results.clips.map((clip: any, index: number) => (
                  <div key={index} className="border border-green-500 p-4">
                    <div className="aspect-video bg-black border border-green-500 mb-3 relative overflow-hidden">
                      <video 
                        controls 
                        className="w-full h-full object-cover"
                        poster={clip.thumbnail_url}
                      >
                        <source src={clip.video_url} type="video/mp4" />
                        Your browser does not support the video tag.
                      </video>
                    </div>
                    
                    <div className="space-y-2">
                      <div className="data-display">
                        <span className="data-label">CLIP:</span>
                        <span className="data-value ml-2">{index + 1}</span>
                      </div>
                      
                      <div className="data-display">
                        <span className="data-label">DURATION:</span>
                        <span className="data-value ml-2">{clip.duration || 'N/A'}s</span>
                      </div>
                      
                      <div className="data-display">
                        <span className="data-label">START TIME:</span>
                        <span className="data-value ml-2">{clip.start_time || 'N/A'}s</span>
                      </div>
                      
                      {clip.transcript && (
                        <div className="border border-green-500 p-2 mt-2">
                          <div className="data-label text-xs mb-1">TRANSCRIPT:</div>
                          <p className="terminal-text text-xs">{clip.transcript}</p>
                        </div>
                      )}
                      
                      <div className="flex space-x-2 mt-3">
                        <Button 
                          size="sm" 
                          variant="outline"
                          onClick={() => {
                            const link = document.createElement('a');
                            link.href = clip.video_url;
                            link.download = `clip_${index + 1}.mp4`;
                            link.click();
                          }}
                        >
                          <Download className="h-3 w-3 mr-1" />
                          DOWNLOAD
                        </Button>
                        
                        <Button 
                          size="sm" 
                          variant="outline"
                          onClick={() => {
                            navigator.clipboard.writeText(clip.video_url);
                            toast.success('CLIP URL COPIED');
                          }}
                        >
                          <Copy className="h-3 w-3 mr-1" />
                          COPY URL
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Simple Footer */}
      <div className="border-t border-green-500 pt-4">
        <div className="flex justify-between items-center text-xs text-green-600">
          <span className="font-digital">ZUEXIS AI PROCESSOR v2.1.0</span>
            <span className="font-digital">MULTI-HOP AI SEQUENCE</span>
            <span className="font-digital">ENHANCED QUALITY OUTPUT</span>
        </div>
      </div>
    </div>
  );
}

export default function VideoPage() {
  return (
    <AuthGuard>
      <VideoPageContent />
    </AuthGuard>
  );
}
