/**
 * TypeScript type definitions
 * 
 * ⚠️ Before making changes, read: ../../docs/workflow/BEST_PRACTICES.md
 * Always check with the user before modifying this file.
 */

// Example types - customize for your project

export interface Example {
  id: number;
  name: string;
  description?: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateExampleRequest {
  name: string;
  description?: string | null;
}

export interface UpdateExampleRequest {
  name?: string;
  description?: string | null;
}

// Add more types as needed for your project




