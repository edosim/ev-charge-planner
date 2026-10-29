// create constant with instructions for the browser on how to
// display time

const ukTime = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'Europe/London',
  weekday: 'short',
  hour: '2-digit',
  minute: '2-digit',
})

export function formatUk(iso: string): string {
  return ukTime.format(new Date(iso))
}