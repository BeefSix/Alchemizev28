'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/store/auth';

interface AuthGuardProps {
  children: React.ReactNode;
}

export function AuthGuard({ children }: AuthGuardProps) {
  const { isAuthenticated, isLoading, checkAuth } = useAuthStore();
  const router = useRouter();
  const [hasCheckedAuth, setHasCheckedAuth] = useState(false);

  useEffect(() => {
    let isMounted = true;

    const performAuthCheck = async () => {
      try {
        await checkAuth();
        if (isMounted) {
          setHasCheckedAuth(true);
        }
      } catch (error) {
        console.error('Auth check failed:', error);
        if (isMounted) {
          setHasCheckedAuth(true);
        }
      }
    };

    // Only perform auth check once on mount
    if (!hasCheckedAuth) {
      performAuthCheck();
    }

    return () => {
      isMounted = false;
    };
  }, [checkAuth, hasCheckedAuth]);

  useEffect(() => {
    // Only redirect after we've completed the initial auth check
    if (hasCheckedAuth && !isLoading && !isAuthenticated) {
      router.push('/login');
    }
  }, [hasCheckedAuth, isAuthenticated, isLoading, router]);

  // Show loading state while checking authentication
  if (isLoading || !hasCheckedAuth) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-black">
        <div className="text-center">
          <div className="text-green-500 text-xl mb-4">AUTHENTICATING...</div>
          <div className="text-green-600 text-sm">Please wait while we verify your credentials</div>
        </div>
      </div>
    );
  }

  // If not authenticated after check, don't render children (will redirect)
  if (!isAuthenticated) {
    return null;
  }

  // If authenticated, render the protected content
  return <>{children}</>;
}
