'use client';

import React from 'react';
import { useAuthStore } from '../../store/auth';
import { AuthGuard } from '@/components/auth-guard';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

function DebugPageContent() {
  const { user, isAuthenticated } = useAuthStore();

  return (
    <div className="container mx-auto p-4">
      <Card>
        <CardHeader>
          <CardTitle>Debug Information</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div>
              <h3 className="font-semibold">Authentication Status</h3>
              <p>Authenticated: {isAuthenticated ? 'Yes' : 'No'}</p>
            </div>
            {user && (
              <div>
                <h3 className="font-semibold">User Information</h3>
                <pre className="bg-gray-100 p-2 rounded text-sm">
                  {JSON.stringify(user, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default function DebugPage() {
  return (
    <AuthGuard>
      <DebugPageContent />
    </AuthGuard>
  );
}