/**
 * Frontend logging utility for IBKR Portfolio Tracker
 * 
 * Based on: docs/workflow/LOGGING_SETUP.md
 */

const isDev = process.env.NODE_ENV === 'development';

type LogLevel = 'info' | 'warn' | 'error' | 'debug';

interface LogOptions {
  component?: string;
  data?: unknown;
}

const log = (level: LogLevel, message: string, options?: LogOptions) => {
  if (!isDev && level === 'debug') return;
  
  const prefix = options?.component ? `[${options.component}]` : '';
  const emoji = {
    info: '📘',
    warn: '⚠️',
    error: '❌',
    debug: '🔍'
  }[level];
  
  const logFn = {
    info: console.log,
    warn: console.warn,
    error: console.error,
    debug: console.debug
  }[level];
  
  if (options?.data) {
    logFn(`${emoji} ${prefix} ${message}`, options.data);
  } else {
    logFn(`${emoji} ${prefix} ${message}`);
  }
};

export const logger = {
  info: (msg: string, opts?: LogOptions) => log('info', msg, opts),
  warn: (msg: string, opts?: LogOptions) => log('warn', msg, opts),
  error: (msg: string, opts?: LogOptions) => log('error', msg, opts),
  debug: (msg: string, opts?: LogOptions) => log('debug', msg, opts),
};

/**
 * Log an API call
 */
export const logAPI = {
  request: (method: string, endpoint: string) => {
    console.log(`📡 [API] ${method} ${endpoint}`);
  },
  success: (endpoint: string) => {
    console.log(`✅ [API] ${endpoint} - Success`);
  },
  error: (endpoint: string, error: unknown) => {
    console.error(`❌ [API] ${endpoint} - Error:`, error);
  }
};

/**
 * Log a user event
 */
export const logEvent = (eventName: string, detail?: unknown) => {
  console.log(`🎯 [Event] ${eventName}`, detail || '');
};
