import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import IntentControlCenterPage from '@/app/(dashboard)/intent-control-center/page'

describe('IntentControlCenterPage', () => {
  it('renders the intent control center heading and v1.3c placeholder state', () => {
    render(<IntentControlCenterPage />)

    expect(
      screen.getByRole('heading', {
        level: 1,
        name: /intent control center/i,
      })
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', {
        level: 2,
        name: /coming in v1.3c/i,
      })
    ).toBeInTheDocument()
  })

  it('renders the current scope description for the placeholder', () => {
    render(<IntentControlCenterPage />)

    expect(
      screen.getByText(
        /intent classification, policy execution, and automated bid management\./i
      )
    ).toBeInTheDocument()
    expect(
      screen.getByText(/full taxonomy versioning and policy rollback capabilities planned for v1\.3c\./i)
    ).toBeInTheDocument()
  })

  it('does not render incident action controls while the page is in placeholder state', () => {
    render(<IntentControlCenterPage />)

    expect(screen.queryByRole('button', { name: /acknowledge incident/i })).toBeNull()
    expect(screen.queryByRole('button', { name: /run rollback/i })).toBeNull()
  })
})
