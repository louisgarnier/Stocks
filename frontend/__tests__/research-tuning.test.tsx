import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { TuningPanel } from '../components/research/TuningPanel'
import { SyncToolbar } from '../components/research/SyncToolbar'

jest.mock('../lib/research', () => ({
  ...jest.requireActual('../lib/research'),
  getConsolidationParams: jest.fn(),
  putConsolidationParams: jest.fn(),
}))

// eslint-disable-next-line @typescript-eslint/no-var-requires
const research = require('../lib/research')

jest.mock('sonner', () => ({ toast: Object.assign(jest.fn(), { success: jest.fn(), error: jest.fn() }) }))

const PARAMS = {
  key: 'consolidation_params',
  params: { max_consolidation_range_pct: 8, min_pct_in_channel: 70, timeframes: [15, 30, 60] },
  defaults: { max_consolidation_range_pct: 5, min_pct_in_channel: 70, timeframes: [15, 30, 60] },
}

beforeEach(() => {
  jest.clearAllMocks()
  research.getConsolidationParams.mockResolvedValue(PARAMS)
  research.putConsolidationParams.mockResolvedValue({ ...PARAMS, params: PARAMS.params })
})

describe('TuningPanel', () => {
  test('shows stored values and skips array-valued params', async () => {
    render(<TuningPanel onRerun={() => {}} />)
    await waitFor(() => expect(screen.getByDisplayValue('8')).toBeInTheDocument())
    // no input rendered for the array-valued `timeframes`
    expect(screen.queryByLabelText(/timeframes/i)).not.toBeInTheDocument()
  })

  test('Reset to recommended restores default value', async () => {
    render(<TuningPanel onRerun={() => {}} />)
    const input = (await screen.findByDisplayValue('8')) as HTMLInputElement
    fireEvent.change(input, { target: { value: '15' } })
    expect(input.value).toBe('15')
    fireEvent.click(screen.getByRole('button', { name: /Reset to recommended/i }))
    await waitFor(() => expect((input as HTMLInputElement).value).toBe('5'))
  })

  test('Save & re-run persists params, runs screen, and calls onRerun', async () => {
    global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => ({}) }) as unknown as typeof fetch
    const onRerun = jest.fn()
    render(<TuningPanel onRerun={onRerun} />)
    await screen.findByDisplayValue('8')
    fireEvent.click(screen.getByRole('button', { name: /Save & re-run/i }))
    await waitFor(() => expect(research.putConsolidationParams).toHaveBeenCalled())
    await waitFor(() =>
      expect(global.fetch).toHaveBeenCalledWith('/api/proxy/api/sync/screen', expect.objectContaining({ method: 'POST' })),
    )
    await waitFor(() => expect(onRerun).toHaveBeenCalled())
  })
})

describe('SyncToolbar', () => {
  test('Fundamentals button posts to the fundamentals sync endpoint', async () => {
    global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => ({}) }) as unknown as typeof fetch
    render(<SyncToolbar />)
    fireEvent.click(screen.getByRole('button', { name: /Fundamentals/i }))
    await waitFor(() =>
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/proxy/api/sync/fundamentals',
        expect.objectContaining({ method: 'POST' }),
      ),
    )
  })
})
