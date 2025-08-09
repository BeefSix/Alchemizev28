'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useAuthStore } from '@/store/auth';
import { User, Lock, Eye, EyeOff, Mail, Terminal, ArrowLeft, Shield } from 'lucide-react';
import toast from 'react-hot-toast';
import Link from 'next/link';

export default function RegisterPage() {
  const [formData, setFormData] = useState({
    email: '',
    username: '',
    password: '',
    confirmPassword: '',
  });
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  
  const { register, error, clearError } = useAuthStore();
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    clearError();

    // Validate passwords match
    if (formData.password !== formData.confirmPassword) {
      toast.error('ACCESS CODES DO NOT MATCH');
      setIsLoading(false);
      return;
    }

    // Validate password strength
    if (formData.password.length < 8) {
      toast.error('ACCESS CODE MUST BE AT LEAST 8 CHARACTERS');
      setIsLoading(false);
      return;
    }

    try {
      await register(formData.email, formData.username, formData.password);
      toast.success('ACCOUNT CREATED - PLEASE AUTHENTICATE');
      router.push('/login');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'ACCOUNT CREATION FAILED');
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
              USER REGISTRATION
            </CardTitle>
            <p className="terminal-text-dim">
              Register for Alchemize terminal access
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
                <label htmlFor="username" className="terminal-text-dim text-sm">
                  USER DESIGNATION:
                </label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-green-600" />
                  <Input
                    id="username"
                    name="username"
                    type="text"
                    placeholder="Choose a username"
                    value={formData.username}
                    onChange={handleInputChange}
                    required
                    className="pl-10 font-mono"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <label htmlFor="password" className="terminal-text-dim text-sm">
                  PRIMARY ACCESS CODE:
                </label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-green-600" />
                  <Input
                    id="password"
                    name="password"
                    type={showPassword ? 'text' : 'password'}
                    placeholder="Create a secure password"
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
                <p className="terminal-text-dim text-xs">
                  Must be at least 8 characters long
                </p>
              </div>

              <div className="space-y-2">
                <label htmlFor="confirmPassword" className="terminal-text-dim text-sm">
                  CONFIRM ACCESS CODE:
                </label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-green-600" />
                  <Input
                    id="confirmPassword"
                    name="confirmPassword"
                    type={showConfirmPassword ? 'text' : 'password'}
                    placeholder="Confirm your password"
                    value={formData.confirmPassword}
                    onChange={handleInputChange}
                    required
                    className="pl-10 pr-10 font-mono"
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    className="absolute right-3 top-1/2 transform -translate-y-1/2 text-green-600 hover:text-green-400"
                  >
                    {showConfirmPassword ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </button>
                </div>
              </div>

              {/* Security Requirements */}
              <div className="p-3 border border-green-500">
                <div className="flex items-center mb-2">
                  <Shield className="h-4 w-4 text-green-600 mr-2" />
                  <span className="terminal-text-bold text-sm">SECURITY REQUIREMENTS</span>
                </div>
                <div className="space-y-1 text-xs">
                  <div className="flex items-center space-x-2">
                    <div className="status-indicator status-online"></div>
                    <span className="terminal-text-dim">Minimum 8 characters</span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <div className="status-indicator status-online"></div>
                    <span className="terminal-text-dim">Uppercase and lowercase letters</span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <div className="status-indicator status-online"></div>
                    <span className="terminal-text-dim">Numbers and special characters</span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <div className="status-indicator status-online"></div>
                    <span className="terminal-text-dim">No sequential patterns</span>
                  </div>
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
                    CREATING ACCOUNT...
                  </>
                ) : (
                  <>
                    <Terminal className="mr-2 h-4 w-4" />
                    CREATE ACCESS CREDENTIALS
                  </>
                )}
              </Button>
            </form>

            <div className="mt-6 text-center">
              <p className="terminal-text-dim text-sm">
                Already have access?{' '}
                <Link
                  href="/login"
                  className="terminal-text hover:text-green-400 font-medium"
                >
                  AUTHENTICATE HERE
                </Link>
              </p>
            </div>

            {/* System Status */}
            <div className="mt-6 p-3 border border-green-500">
              <div className="text-center">
                <div className="status-indicator status-online mx-auto mb-2"></div>
                <p className="terminal-text text-xs">SYSTEM STATUS: ONLINE</p>
                <p className="terminal-text-dim text-xs">SECURE REGISTRATION ENABLED</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
