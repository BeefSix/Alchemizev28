'use client';

import React, { useState, useEffect } from 'react';

const API_BASE = '';
const NODE_ENV = process.env.NODE_ENV || 'development';

interface HealthStatus {
  status: 'healthy' | 'unhealthy' | 'checking' | 'error';
  lastChecked?: Date;
}

export function ApiBaseBanner() {
  const [healthStatus, setHealthStatus] = useState<HealthStatus>({ status: 'checking' });

  const checkHealth = async () => {
    try {
      setHealthStatus({ status: 'checking' });
      const response = await fetch(`${API_BASE}/healthz`, {
        method: 'GET',
        headers: {
          'Accept': 'application/json',
        },
        // Don't include credentials for health check
      });
      
      if (response.ok) {
        setHealthStatus({ status: 'healthy', lastChecked: new Date() });
      } else {
        setHealthStatus({ status: 'unhealthy', lastChecked: new Date() });
      }
    } catch (error) {
      console.error('Health check failed:', error);
      setHealthStatus({ status: 'error', lastChecked: new Date() });
    }
  };

  useEffect(() => {
    // Initial health check
    checkHealth();
    
    // Set up periodic health checks every 30 seconds
    const interval = setInterval(checkHealth, 30000);
    
    return () => clearInterval(interval);
  }, []);

  // Only show in development
  if (NODE_ENV !== 'development') {
    return null;
  }

  const getStatusColor = () => {
    switch (healthStatus.status) {
      case 'healthy': return 'bg-green-500';
      case 'unhealthy': return 'bg-red-500';
      case 'checking': return 'bg-yellow-500 animate-pulse';
      case 'error': return 'bg-red-600';
      default: return 'bg-gray-500';
    }
  };

  const getStatusText = () => {
    switch (healthStatus.status) {
      case 'healthy': return 'API Healthy';
      case 'unhealthy': return 'API Unhealthy';
      case 'checking': return 'Checking...';
      case 'error': return 'API Error';
      default: return 'Unknown';
    }
  };

  return (
    <div 
      className="fixed top-0 left-0 right-0 z-50 bg-black/80 backdrop-blur-sm border-b border-green-500/30 px-4 py-2"
      style={{ '--api-banner-height': '48px' } as React.CSSProperties}
    >
      <div className="flex items-center justify-between max-w-7xl mx-auto">
        <div className="flex items-center space-x-4 text-sm">
          <div className="flex items-center space-x-2">
            <span className="text-green-400 font-mono">API BASE:</span>
            <span className="text-white font-mono bg-gray-800 px-2 py-1 rounded">
              {API_BASE || 'http://localhost:8001'}
            </span>
          </div>
          
          <div className="flex items-center space-x-2">
            <div className={`w-3 h-3 rounded-full ${getStatusColor()}`}></div>
            <span className="text-gray-300">{getStatusText()}</span>
            {healthStatus.lastChecked && (
              <span className="text-gray-500 text-xs">
                ({healthStatus.lastChecked.toLocaleTimeString()})
              </span>
            )}
          </div>
        </div>
        
        <button
          onClick={checkHealth}
          className="text-green-400 hover:text-green-300 text-xs px-2 py-1 border border-green-500/30 rounded hover:border-green-400/50 transition-colors"
          disabled={healthStatus.status === 'checking'}
        >
          Refresh
        </button>
      </div>
    </div>
  );
}

export default ApiBaseBanner;