'use client';

import React, { useState, useEffect } from 'react';
import { CheckCircle, XCircle, AlertCircle } from 'lucide-react';

interface HealthStatus {
  status: 'healthy' | 'unhealthy' | 'checking' | 'error';
  message: string;
  timestamp?: string;
}

export function HealthCheck() {
  const [health, setHealth] = useState<HealthStatus>({
    status: 'checking',
    message: 'Checking backend connection...'
  });

  const checkHealth = async () => {
    try {
      setHealth({ status: 'checking', message: 'Checking backend connection...' });
      
      const response = await fetch('/healthz', {
        method: 'GET',
        credentials: 'include',
        headers: {
          'Accept': 'application/json',
        },
      });

      if (response.ok) {
        const data = await response.json();
        setHealth({
          status: 'healthy',
          message: 'Backend connected successfully',
          timestamp: data.timestamp
        });
      } else {
        setHealth({
          status: 'unhealthy',
          message: `Backend returned ${response.status}: ${response.statusText}`
        });
      }
    } catch (error) {
      setHealth({
        status: 'error',
        message: error instanceof Error ? error.message : 'Failed to connect to backend'
      });
    }
  };

  useEffect(() => {
    checkHealth();
    // Check health every 30 seconds
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  const getIcon = () => {
    switch (health.status) {
      case 'healthy':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'unhealthy':
      case 'error':
        return <XCircle className="w-4 h-4 text-red-500" />;
      case 'checking':
        return <AlertCircle className="w-4 h-4 text-yellow-500 animate-pulse" />;
      default:
        return <AlertCircle className="w-4 h-4 text-gray-500" />;
    }
  };

  const getStatusColor = () => {
    switch (health.status) {
      case 'healthy':
        return 'text-green-600';
      case 'unhealthy':
      case 'error':
        return 'text-red-600';
      case 'checking':
        return 'text-yellow-600';
      default:
        return 'text-gray-600';
    }
  };

  return (
    <div className="fixed bottom-4 right-4 z-50">
      <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-3 max-w-sm">
        <div className="flex items-center space-x-2">
          {getIcon()}
          <div className="flex-1">
            <div className={`text-sm font-medium ${getStatusColor()}`}>
              Backend: {health.status === 'checking' ? 'Checking...' : health.status}
            </div>
            <div className="text-xs text-gray-500 truncate">
              {health.message}
            </div>
            {health.timestamp && (
              <div className="text-xs text-gray-400">
                Last check: {new Date(health.timestamp).toLocaleTimeString()}
              </div>
            )}
          </div>
          <button
            onClick={checkHealth}
            className="text-xs text-blue-600 hover:text-blue-800 px-2 py-1 rounded"
            disabled={health.status === 'checking'}
          >
            Refresh
          </button>
        </div>
      </div>
    </div>
  );
}