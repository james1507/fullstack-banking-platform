export const formatVND = (value: number | bigint) =>
  `${new Intl.NumberFormat('en-US').format(value)} ₫`;
export const formatDate = (value: string) =>
  new Intl.DateTimeFormat('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value));
export const shortId = (id: string) => `•••• ${id.slice(-6)}`;
