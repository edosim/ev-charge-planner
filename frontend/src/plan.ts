import type { Slot } from './types'


// make helper function with text for output
export function describePlan(slots: Slot[]): string {
  const count = slots.length
  const hours = count / 2
  const slotWord = count === 1 ? 'slot' : 'slots'
  const hourWord = hours === 1 ? 'hour' : 'hours'
  return `Charging during ${count} half-hour ${slotWord} (${hours} ${hourWord}).`
}


const HALF_HOUR = 30 * 60 * 1000; // 1,800,000 ms, easier to read than 1.8e+6

export function groupSlots(slots: Slot[]): Slot[] {
  if (slots.length === 0) return [];

  const groups: Slot[] = [];
  let groupStart = slots[0]; // first slot of the group
  let previous = slots[0];

  for (let i = 1; i < slots.length; i++) {
    const current = slots[i];
    const gap = new Date(current.from).getTime() - new Date(previous.from).getTime();

    if (gap !== HALF_HOUR) {
      // There's a break: close the current group using the previous slot's end
      groups.push({
        from: groupStart.from,
        to: previous.to,
        intensity: groupStart.intensity, //placeholder to reuse slot 
      });
      groupStart = current; // start a new group here
    }

    previous = current;
  }

  // close last group
  groups.push({
    from: groupStart.from,
    to: previous.to,
    intensity: groupStart.intensity,
  });

  return groups;
}
