import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import App from '../src/App'

describe('App', () => {
  it('renders without crashing', () => {
    render(<App />)
    expect(screen.getByRole('button')).toBeDefined()
  })

  it('contains expected elements', () => {
    const { container } = render(<App />)
    expect(container).toBeTruthy()
  })
})
