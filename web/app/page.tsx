'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useAuthStore } from '@/store/auth';
import { useJobsStore } from '@/store/jobs';
import { 
  Video, 
  FileText, 
  CreditCard, 
  User, 
  LogOut, 
  Upload,
  Play,
  Download,
  Terminal,
  Activity,
  Zap
} from 'lucide-react';
import toast from 'react-hot-toast';
import Link from 'next/link';

export default function HomePage() {
  const { user, isAuthenticated, logout, checkAuth } = useAuthStore();
  const { jobs, fetchJobs, isLoading } = useJobsStore();
  const router = useRouter();

  useEffect(() => {
    if (!isAuthenticated) {
      checkAuth();
    }
    if (isAuthenticated) {
      fetchJobs();
    }
  }, [isAuthenticated, checkAuth, fetchJobs]);

  const handleLogout = async () => {
    try {
      await logout();
      router.push('/login');
      toast.success('Logged out successfully');
    } catch (error) {
      toast.error('Logout failed');
    }
  };

  if (!isAuthenticated) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <CardTitle className="alien-league-title">ACCESS DENIED</CardTitle>
            <p className="terminal-text-dim">Authentication required</p>
          </CardHeader>
          <CardContent className="space-y-4">
            <Button onClick={() => router.push('/login')} className="w-full">
              <Terminal className="mr-2 h-4 w-4" />
              LOGIN TO SYSTEM
            </Button>
            <Button onClick={() => router.push('/register')} variant="outline" className="w-full">
              <User className="mr-2 h-4 w-4" />
              CREATE ACCOUNT
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const quickActions = [
    {
      id: 'video',
      title: 'VIDEO PROCESSOR',
      description: 'Fast AI video enhancement',
      icon: Video,
      color: 'text-green-400',
      href: '/video',
      primary: true
    },
    {
      id: 'content',
      title: 'CONTENT REPURPOSE',
      description: 'Multi-platform optimization',
      icon: FileText,
      color: 'text-blue-400',
      href: '/content'
    },
    {
      id: 'payment',
      title: 'BILLING',
      description: 'Manage subscription',
      icon: CreditCard,
      color: 'text-purple-400',
      href: '/payment'
    }
  ];

  const recentJobs = jobs.slice(0, 3);

  return (
    <div className="p-6 space-y-6">
      {/* Simple Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="terminal-text-bold text-3xl">ZUEXIS</h1>
          <p className="alien-league-title">AI-Powered Video Enhancement</p>
        </div>
        <div className="flex items-center space-x-4">
          <div className="text-right">
            <div className="terminal-text text-sm">{user?.email}</div>
            <div className="terminal-text-dim text-xs">ACTIVE SESSION</div>
          </div>
          <Button variant="outline" size="sm" onClick={handleLogout}>
            <LogOut className="mr-2 h-4 w-4" />
            LOGOUT
          </Button>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {quickActions.map((action) => (
          <Link key={action.id} href={action.href}>
            <Card className={`cursor-pointer hover:border-green-400 transition-colors ${action.primary ? 'border-green-400' : ''}`}>
              <CardContent className="p-6 text-center">
                <action.icon className={`h-12 w-12 mx-auto mb-4 ${action.color}`} />
                <h3 className="alien-league-title text-lg mb-2">{action.title}</h3>
                <p className="terminal-text-dim text-sm">{action.description}</p>
                {action.primary && (
                  <div className="mt-4">
                    <div className="status-indicator status-online mx-auto"></div>
                    <span className="terminal-text text-xs ml-2">READY</span>
                  </div>
                )}
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>

      {/* Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Jobs */}
        <Card>
          <CardHeader>
            <CardTitle className="alien-league-title">RECENT JOBS</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex items-center justify-center py-8">
                <div className="spinner mr-2" />
                <span className="terminal-text">LOADING...</span>
              </div>
            ) : recentJobs.length > 0 ? (
              <div className="space-y-3">
                {recentJobs.map((job, index) => (
                  <div key={job.id || `job-${index}`} className="border border-green-500 p-3">
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="font-digital text-sm text-green-400">JOB-{job.id ? job.id.slice(0, 8) : 'UNKNOWN'}</div>
                        <div className="text-xs text-green-600 mt-1">
                          {job.status || 'UNKNOWN'} | {job.created_at ? new Date(job.created_at).toLocaleDateString() : 'N/A'}
                        </div>
                      </div>
                      <div className="flex space-x-2">
                        <Button size="sm" variant="outline">
                          <Play className="h-3 w-3" />
                        </Button>
                        <Button size="sm" variant="outline">
                          <Download className="h-3 w-3" />
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8">
                <Video className="h-12 w-12 text-green-600 mx-auto mb-4" />
                <p className="terminal-text-dim">No jobs yet</p>
                <Button className="mt-4" onClick={() => router.push('/video')}>
                  <Upload className="mr-2 h-4 w-4" />
                  START FIRST JOB
                </Button>
              </div>
            )}
          </CardContent>
        </Card>

        {/* System Status */}
        <Card>
          <CardHeader>
            <CardTitle className="alien-league-title">SYSTEM STATUS</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="text-center p-3 border border-green-500">
                <div className="terminal-text-bold text-2xl">5</div>
                <div className="terminal-text-dim text-xs">ACTIVE JOBS</div>
              </div>
              <div className="text-center p-3 border border-green-500">
                <div className="terminal-text-bold text-2xl">100%</div>
                <div className="terminal-text-dim text-xs">AI READY</div>
              </div>
            </div>
            
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="terminal-text-dim">AI PROCESSOR:</span>
                <div className="flex items-center">
                  <div className="status-indicator status-online mr-2"></div>
                  <span className="terminal-text">ONLINE</span>
                </div>
              </div>
              <div className="flex items-center justify-between">
                <span className="terminal-text-dim">GPU ACCELERATION:</span>
                <div className="flex items-center">
                  <div className="status-indicator status-online mr-2"></div>
                  <span className="terminal-text">ACTIVE</span>
                </div>
              </div>
              <div className="flex items-center justify-between">
                <span className="terminal-text-dim">STORAGE:</span>
                <div className="flex items-center">
                  <div className="status-indicator status-online mr-2"></div>
                  <span className="terminal-text">READY</span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="border border-green-500 p-4 text-center">
          <div className="terminal-text-bold text-2xl">24</div>
          <div className="terminal-text-dim text-xs">TOTAL JOBS</div>
        </div>
        <div className="border border-green-500 p-4 text-center">
          <div className="terminal-text-bold text-2xl">120</div>
          <div className="terminal-text-dim text-xs">CLIPS GENERATED</div>
        </div>
        <div className="border border-green-500 p-4 text-center">
          <div className="terminal-text-bold text-2xl">8K</div>
          <div className="terminal-text-dim text-xs">MAX QUALITY</div>
        </div>
        <div className="border border-green-500 p-4 text-center">
          <div className="terminal-text-bold text-2xl">99.9%</div>
          <div className="terminal-text-dim text-xs">UPTIME</div>
        </div>
      </div>

      {/* Footer */}
      <div className="border-t border-green-500 pt-4">
        <div className="flex justify-between items-center text-xs text-green-600">
          <span className="font-digital">ZUEXIS v2.1.0</span>
            <span className="font-digital">MULTI-HOP AI SEQUENCE</span>
            <span className="font-digital">ENHANCED QUALITY OUTPUT</span>
        </div>
      </div>
    </div>
  );
}
