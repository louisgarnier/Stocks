/**
 * Example frontend test
 * 
 * ⚠️ Before making changes, read: ../../docs/workflow/BEST_PRACTICES.md
 */

import { render, screen } from '@testing-library/react';
import HomePage from '../app/page';

// Mock the API client
jest.mock('../src/api/client', () => ({
  healthAPI: {
    check: jest.fn().mockResolvedValue({ status: 'healthy' }),
  },
}));

describe('HomePage', () => {
  it('renders the title', () => {
    render(<HomePage />);
    const title = screen.getByText('Template Project');
    expect(title).toBeInTheDocument();
  });

  it('displays API status', async () => {
    render(<HomePage />);
    // Wait for API check to complete
    const apiStatus = await screen.findByText(/Backend API:/);
    expect(apiStatus).toBeInTheDocument();
  });
});




