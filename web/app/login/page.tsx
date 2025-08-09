'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useAuthStore } from '@/store/auth';
import { Lock, Eye, EyeOff, Mail, Terminal, ArrowLeft } from 'lucide-react';
import toast from 'react-hot-toast';
import Link from 'next/link';

export default function LoginPage() {
  const [formData, setFormData] = useState({
    email: '',
    password: '',
  });
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  
  const { login, error, clearError } = useAuthStore();
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    console.log('Form submitted with data:', formData);
    setIsLoading(true);
    clearError();

    try {
      console.log('Attempting login...');
      await login(formData.email, formData.password);
      console.log('Login successful!');
      toast.success('ACCESS GRANTED - WELCOME TO ALCHEMIZE');
      router.push('/');
    } catch (error) {
      console.error('Login error:', error);
      toast.error(error instanceof Error ? error.message : 'ACCESS DENIED');
    } finally {
      setIsLoading(false);
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData(prev => ({
      ...prev,
      [e.target.name]: e.target.value,
    }));
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Back Button */}
        <Button 
          variant="outline" 
          size="sm" 
          onClick={() => router.push('/')}
          className="mb-4"
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          BACK TO TERMINAL
        </Button>

        <Card>
          <CardHeader className="text-center">
            <CardTitle className="alien-league-title-large text-center mb-2">
              SYSTEM ACCESS
            </CardTitle>
            <p className="terminal-text-dim">
              Enter credentials to access Alchemize terminal
            </p>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <label htmlFor="email" className="terminal-text-dim text-sm">
                  USER IDENTIFIER:
                </label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-green-600" />
                  <Input
                    id="email"
                    name="email"
                    type="email"
                    placeholder="Enter your email address"
                    value={formData.email}
                    onChange={handleInputChange}
                    required
                    className="pl-10 font-mono"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <label htmlFor="password" className="terminal-text-dim text-sm">
                  ACCESS CODE:
                </label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-green-600" />
                  <Input
                    id="password"
                    name="password"
                    type={showPassword ? 'text' : 'password'}
                    placeholder="Enter your password"
                    value={formData.password}
                    onChange={handleInputChange}
                    required
                    className="pl-10 pr-10 font-mono"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 transform -translate-y-1/2 text-green-600 hover:text-green-400"
                  >
                    {showPassword ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </button>
                </div>
              </div>

              <Button
                type="submit"
                className="w-full"
                size="lg"
                disabled={isLoading}
              >
                {isLoading ? (
                  <>
                    <div className="spinner mr-2" />
                    AUTHENTICATING...
                  </>
                ) : (
                  <>
                    <Terminal className="mr-2 h-4 w-4" />
                    ACCESS SYSTEM
                  </>
                )}
              </Button>
            </form>

            <div className="mt-6 text-center">
              <p className="terminal-text-dim text-sm">
                No access credentials?{' '}
                <Link
                  href="/register"
                  className="terminal-text hover:text-green-400 font-medium"
                >
                  CREATE ACCOUNT
                </Link>
              </p>
            </div>

            {/* System Status */}
            <div className="mt-6 p-3 border border-green-500">
              <div className="text-center">
                <div className="status-indicator status-online mx-auto mb-2"></div>
                <p className="terminal-text text-xs">SYSTEM STATUS: ONLINE</p>
                <p className="terminal-text-dim text-xs">SECURE CONNECTION ESTABLISHED</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
