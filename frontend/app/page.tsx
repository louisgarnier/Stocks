/**
 * Home page
 * 
 * ⚠️ Before making changes, read: ../../docs/workflow/BEST_PRACTICES.md
 * Always check with the user before modifying this file.
 */

'use client';

import { useEffect, useState } from 'react';
import { healthAPI } from '@/src/api/client';

export default function HomePage() {
  const [apiStatus, setApiStatus] = useState<string>('checking...');

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const response = await healthAPI.check();
        setApiStatus(response.status);
      } catch (error) {
        setApiStatus('error');
        console.error('API health check failed:', error);
      }
    };

    checkHealth();
  }, []);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gray-50 dark:bg-gray-900">
      <main className="max-w-4xl w-full px-4 sm:px-6 lg:px-8 py-8">
        <h1 className="text-4xl font-bold text-gray-900 dark:text-gray-100 mb-4">
          Template Project
        </h1>
        <p className="text-lg text-gray-600 dark:text-gray-400 mb-8">
          Welcome to your new project template!
        </p>
        
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
          <h2 className="text-xl font-semibold mb-4">API Status</h2>
          <p className="text-gray-700 dark:text-gray-300">
            Backend API: <span className="font-mono">{apiStatus}</span>
          </p>
        </div>

        <div className="mt-8 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
          <p className="text-sm text-blue-800 dark:text-blue-200">
            ⚠️ <strong>Remember:</strong> Always check{' '}
            <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded">
              docs/workflow/BEST_PRACTICES.md
            </code>{' '}
            before making code changes!
          </p>
        </div>
      </main>
    </div>
  );
}




