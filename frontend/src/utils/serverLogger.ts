/**
 * Server-side logger for Next.js - logs to terminal
 * 
 * This logger outputs to the terminal (server-side) instead of browser console
 */

type LogLevel = 'info' | 'warn' | 'error' | 'debug';

const emoji = {
  info: '📘',
  warn: '⚠️',
  error: '❌',
  debug: '🔍',
  api_request: '📡',
  api_success: '✅',
  api_error: '❌',
};

const formatTimestamp = () => {
  return new Date().toISOString().replace('T', ' ').substring(0, 23);
};

export const serverLog = {
  info: (component: string, message: string, data?: unknown) => {
    console.log(`${formatTimestamp()} ${emoji.info} [${component}] ${message}`, data ?? '');
  },
  warn: (component: string, message: string, data?: unknown) => {
    console.warn(`${formatTimestamp()} ${emoji.warn} [${component}] ${message}`, data ?? '');
  },
  error: (component: string, message: string, data?: unknown) => {
    console.error(`${formatTimestamp()} ${emoji.error} [${component}] ${message}`, data ?? '');
  },
  debug: (component: string, message: string, data?: unknown) => {
    if (process.env.NODE_ENV === 'development') {
      console.debug(`${formatTimestamp()} ${emoji.debug} [${component}] ${message}`, data ?? '');
    }
  },
  apiRequest: (method: string, endpoint: string) => {
    console.log(`${formatTimestamp()} ${emoji.api_request} [API] ${method} ${endpoint}`);
  },
  apiSuccess: (endpoint: string, data?: unknown) => {
    console.log(`${formatTimestamp()} ${emoji.api_success} [API] ${endpoint} - Success`, data ?? '');
  },
  apiError: (endpoint: string, error: unknown) => {
    console.error(`${formatTimestamp()} ${emoji.api_error} [API] ${endpoint} - Error:`, error);
  },
};
