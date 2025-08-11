// Global request manager to prevent duplicate requests and handle cancellation

interface PendingRequest {
  controller: AbortController;
  promise: Promise<unknown>;
  timestamp: number;
}

class RequestManager {
  private pendingRequests = new Map<string, PendingRequest>();
  private readonly CACHE_DURATION = 5000; // 5 seconds

  // Get or create a request with deduplication
  async getOrCreateRequest<T>(
    key: string,
    requestFn: (signal: AbortSignal) => Promise<T>,
    cacheDuration = this.CACHE_DURATION
  ): Promise<T> {
    const now = Date.now();
    const existing = this.pendingRequests.get(key);

    // Return existing request if it's still fresh
    if (existing && (now - existing.timestamp) < cacheDuration) {
      try {
        return await existing.promise as T;
      } catch (error: unknown) {
        // If the existing request failed, remove it and create a new one
        this.pendingRequests.delete(key);
      }
    }

    // Create new request
    const controller = new AbortController();
    const promise = requestFn(controller.signal);
    
    const pendingRequest: PendingRequest = {
      controller,
      promise,
      timestamp: now
    };

    this.pendingRequests.set(key, pendingRequest);

    try {
      const result = await promise;
      // Keep successful requests in cache briefly
      setTimeout(() => this.pendingRequests.delete(key), cacheDuration);
      return result;
    } catch (error: unknown) {
        // Remove failed requests immediately
        this.pendingRequests.delete(key);
        throw error;
      }
  }

  // Cancel a specific request
  cancelRequest(key: string): void {
    const request = this.pendingRequests.get(key);
    if (request) {
      request.controller.abort();
      this.pendingRequests.delete(key);
    }
  }

  // Cancel all pending requests
  cancelAllRequests(): void {
    Array.from(this.pendingRequests.entries()).forEach(([key, request]) => {
      request.controller.abort();
    });
    this.pendingRequests.clear();
  }

  // Get pending request count
  getPendingCount(): number {
    return this.pendingRequests.size;
  }

  // Clean up expired requests
  cleanup(): void {
    const now = Date.now();
    Array.from(this.pendingRequests.entries()).forEach(([key, request]) => {
      if (now - request.timestamp > this.CACHE_DURATION * 2) {
        request.controller.abort();
        this.pendingRequests.delete(key);
      }
    });
  }
}

// Global instance
export const requestManager = new RequestManager();

// Auto-cleanup on page unload
if (typeof window !== 'undefined') {
  window.addEventListener('beforeunload', () => {
    requestManager.cancelAllRequests();
  });

  // Periodic cleanup
  setInterval(() => {
    requestManager.cleanup();
  }, 30000); // Clean up every 30 seconds
}