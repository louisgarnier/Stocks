import { render, screen, fireEvent } from '@testing-library/react'
import { SignalPill } from '../components/positions/SignalPill'

describe('SignalPill', () => {
  it('renders "All clear" when 0 fired and has data', () => {
    render(<SignalPill firedCount={0} hasData expanded={false} />)
    expect(screen.getByText(/all clear/i)).toBeInTheDocument()
  })

  it('renders "N fired" with collapsed chevron when fired > 0', () => {
    render(<SignalPill firedCount={3} hasData expanded={false} onToggle={() => {}} />)
    expect(screen.getByText(/3 fired/i)).toBeInTheDocument()
    expect(screen.getByRole('button')).toBeInTheDocument()
  })

  it('renders N/A when no data', () => {
    render(<SignalPill firedCount={0} hasData={false} expanded={false} />)
    expect(screen.getByText(/n\/a/i)).toBeInTheDocument()
  })

  it('calls onToggle and stops propagation when clicked', () => {
    const onToggle = jest.fn()
    const onRowClick = jest.fn()
    render(
      <table><tbody>
        <tr onClick={onRowClick}>
          <td><SignalPill firedCount={2} hasData expanded={false} onToggle={onToggle} /></td>
        </tr>
      </tbody></table>,
    )
    fireEvent.click(screen.getByRole('button'))
    expect(onToggle).toHaveBeenCalledTimes(1)
    expect(onRowClick).not.toHaveBeenCalled()
  })

  it('does not render a button when 0 fired (nothing to expand)', () => {
    render(<SignalPill firedCount={0} hasData expanded={false} />)
    expect(screen.queryByRole('button')).toBeNull()
  })
})
