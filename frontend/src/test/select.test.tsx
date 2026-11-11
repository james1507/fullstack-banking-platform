import { useState } from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, it, vi } from 'vitest';
import { Select } from '../components/Select';

const options = [
  { value: '', label: 'All directions', description: 'Incoming and outgoing transfers' },
  { value: 'OUTGOING', label: 'Money out', description: 'Sent from your accounts' },
  { value: 'INCOMING', label: 'Money in', description: 'Received by your accounts' },
];
function Example() {
  const [value, setValue] = useState('');
  return (
    <>
      <Select aria-label="Direction" options={options} value={value} onChange={setValue} />
      <button>Next field</button>
    </>
  );
}
it('opens selected state and commits a clicked option without submitting a form', async () => {
  const user = userEvent.setup();
  const submit = vi.fn((event) => event.preventDefault());
  render(
    <form onSubmit={submit}>
      <Example />
    </form>,
  );
  const trigger = screen.getByRole('combobox', { name: 'Direction' });
  await user.click(trigger);
  expect(trigger).toHaveAttribute('aria-expanded', 'true');
  expect(screen.getByRole('option', { name: /All directions/ })).toHaveAttribute(
    'aria-selected',
    'true',
  );
  await user.click(screen.getByRole('option', { name: /Money in/ }));
  expect(trigger).toHaveTextContent('Money in');
  expect(trigger).toHaveFocus();
  expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
  expect(submit).not.toHaveBeenCalled();
});
it('supports arrow, Home, End and Enter navigation', async () => {
  const user = userEvent.setup();
  render(<Example />);
  const trigger = screen.getByRole('combobox');
  trigger.focus();
  await user.keyboard('{ArrowDown}{End}');
  const incoming = screen.getByRole('option', { name: /Money in/ });
  expect(trigger).toHaveAttribute('aria-activedescendant', incoming.id);
  await user.keyboard('{Home}{ArrowDown}{Enter}');
  expect(trigger).toHaveTextContent('Money out');
});
it('Escape cancels pending keyboard choice and preserves committed value', async () => {
  const user = userEvent.setup();
  render(<Example />);
  const trigger = screen.getByRole('combobox');
  await user.click(trigger);
  await user.keyboard('{End}{Escape}');
  expect(trigger).toHaveTextContent('All directions');
  expect(trigger).toHaveFocus();
  expect(trigger).toHaveAttribute('aria-expanded', 'false');
});
it('typeahead finds matching labels and Space commits', async () => {
  const user = userEvent.setup();
  render(<Example />);
  const trigger = screen.getByRole('combobox');
  trigger.focus();
  await user.keyboard('mo');
  expect(trigger).toHaveAttribute(
    'aria-activedescendant',
    screen.getByRole('option', { name: /Money out/ }).id,
  );
  await user.keyboard('{ArrowDown} ');
  expect(trigger).toHaveTextContent('Money in');
});
it('outside click dismisses and Tab moves focus without trapping it', async () => {
  const user = userEvent.setup();
  render(<Example />);
  const trigger = screen.getByRole('combobox');
  await user.click(trigger);
  await user.click(screen.getByRole('button', { name: 'Next field' }));
  expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
  await user.click(trigger);
  await user.tab();
  expect(screen.getByRole('button', { name: 'Next field' })).toHaveFocus();
  expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
});
it('respects disabled fieldsets and announces invalid state and description', async () => {
  const user = userEvent.setup();
  render(
    <fieldset disabled>
      <Select
        aria-label="Source"
        aria-invalid="true"
        aria-describedby="error"
        options={options}
        value=""
        onChange={vi.fn()}
      />
      <p id="error">Choose an account.</p>
    </fieldset>,
  );
  const trigger = screen.getByRole('combobox');
  expect(trigger).toBeDisabled();
  expect(trigger).toHaveAccessibleDescription('Choose an account.');
  await user.click(trigger);
  expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
});
