import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import App from './App';

describe('App', () => {
  it('renders landing hero headline', () => {
    render(<App />);
    expect(
      screen.getByText(/Anticipate real estate moves before they materialise/i)
    ).toBeInTheDocument();
  });
});
