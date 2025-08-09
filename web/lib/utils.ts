import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 Bytes';
  
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

export function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  
  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }
  return `${minutes}:${secs.toString().padStart(2, '0')}`;
}

export function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function getStatusColor(status: string): string {
  switch (status) {
    case 'PENDING':
      return 'text-yellow-600 bg-yellow-50 border-yellow-200';
    case 'IN_PROGRESS':
      return 'text-blue-600 bg-blue-50 border-blue-200';
    case 'COMPLETED':
      return 'text-green-600 bg-green-50 border-green-200';
    case 'FAILED':
      return 'text-red-600 bg-red-50 border-red-200';
    case 'RETRYING':
      return 'text-orange-600 bg-orange-50 border-orange-200';
    default:
      return 'text-green-400 bg-black border-green-500';
  }
}

export function getStatusIcon(status: string): string {
  switch (status) {
    case 'PENDING':
      return '⏳';
    case 'IN_PROGRESS':
      return '🔄';
    case 'COMPLETED':
      return '✅';
    case 'FAILED':
      return '❌';
    case 'RETRYING':
      return '🔄';
    default:
      return '❓';
  }
}

export function validateVideoFile(file: File): { isValid: boolean; error?: string } {
  const maxSize = 500 * 1024 * 1024; // 500MB
  const allowedTypes = ['video/mp4', 'video/avi', 'video/mov', 'video/wmv', 'video/flv', 'video/webm', 'video/x-matroska'];
  
  if (file.size > maxSize) {
    return { isValid: false, error: 'File size must be less than 500MB' };
  }
  
  if (!allowedTypes.includes(file.type)) {
    return { isValid: false, error: 'Please select a valid video file (MP4, AVI, MOV, WMV, FLV, WebM, MKV)' };
  }
  
  return { isValid: true };
}

export function debounce<T extends (...args: any[]) => any>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: NodeJS.Timeout;
  return (...args: Parameters<T>) => {
    clearTimeout(timeout);
    timeout = setTimeout(() => func(...args), wait);
  };
}

export function generateThumbnailUrl(videoUrl: string): string {
  // This would typically call your backend to generate a thumbnail
  // For now, we'll return a placeholder
  return videoUrl.replace(/\.(mp4|avi|mov|wmv|flv|webm)$/i, '_thumb.jpg');
}
