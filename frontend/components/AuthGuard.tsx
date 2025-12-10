'use client';

import { useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useAuthStore } from '@/lib/store';
import { api } from '@/lib/api';
import { Loader2 } from 'lucide-react';

const PUBLIC_PATHS = ['/login', '/signup', '/forgot-password'];

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [isChecking, setIsChecking] = useState(true);
  const [mounted, setMounted] = useState(false);

  // Handle hydration
  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted) return;

    const checkAuth = async () => {
      // Get auth state after hydration
      const { isAuthenticated, token, logout, setAuth } = useAuthStore.getState();

      // Public paths don't need auth check
      if (PUBLIC_PATHS.includes(pathname)) {
        setIsChecking(false);
        return;
      }

      // If not authenticated, redirect to login
      if (!isAuthenticated || !token) {
        router.replace('/login');
        setIsChecking(false);
        return;
      }

      // Verify token is still valid
      try {
        api.setToken(token);
        const user = await api.getMe();
        setAuth(token, user);
        setIsChecking(false);
      } catch (error) {
        // Token invalid, logout and redirect
        logout();
        router.replace('/login');
        setIsChecking(false);
      }
    };

    checkAuth();
  }, [pathname, mounted]);

  // Show loading while mounting or checking auth
  if (!mounted) {
    return null;
  }

  if (isChecking && !PUBLIC_PATHS.includes(pathname)) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <Loader2 className="w-10 h-10 animate-spin text-blue-600 mx-auto mb-4" />
          <p className="text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  // Redirect authenticated users away from login page
  if (mounted && PUBLIC_PATHS.includes(pathname)) {
    const { isAuthenticated } = useAuthStore.getState();
    if (isAuthenticated) {
      router.replace('/dashboard');
      return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50">
          <div className="text-center">
            <Loader2 className="w-10 h-10 animate-spin text-blue-600 mx-auto mb-4" />
            <p className="text-gray-600">Redirecting...</p>
          </div>
        </div>
      );
    }
  }

  return <>{children}</>;
}
