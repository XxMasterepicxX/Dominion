import { render, screen } from '@testing-library/react';
import App from './App';

test('renders landing hero headline', () => {
  render(<App />);
  expect(screen.getByText(/Anticipate real estate moves before they materialise/i)).toBeInTheDocument();
});
