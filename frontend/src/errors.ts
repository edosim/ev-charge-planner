const LABELS: Record<string, string> = {
    charge_needed_kwh: 'Charge needed',
    charge_rate_kw: 'Charger power',
    deadline_date: 'Ready by (UK date)',
    deadline_time: 'Ready by (UK time)',
}

type ValidationErrorItem = {
    loc: (string | number)[]
    msg: string
    type: string
}

export function describeError(detail: unknown): string | null {
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
        const items = detail as ValidationErrorItem[]
        return items.map((d) => {
            const field = String(d.loc?.at(-1));
            return `${LABELS[field] ?? field}: ${d.msg}`
        }).join('; ') + '.'
    }
    return null
}