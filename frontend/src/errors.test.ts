import { describeError } from "./errors";

import { describe, expect, it } from 'vitest'



describe('describeError', () => {
    it.each([
        {
            name: 'a plain string',
            detail: 'Deadline is too soon.',
            expected: 'Deadline is too soon.',
        },
        {
            name: 'one validation error',
            detail: [{
                loc: ['query', 'charge_needed_kwh'],
                msg: 'Input should be greater than 0',
                type: 'greater_than'
            }],
            expected: 'Charge needed: Input should be greater than 0.',
        },
        {
            name: 'two validation errors',
            detail: [
                {
                    loc: ['query', 'charge_needed_kwh'],
                    msg: 'Input should be greater than 0',
                    type: 'greater_than'
                },
                {
                    loc: ['query', 'deadline_time'],
                    msg: 'Field required',
                    type: 'missing'
                },

            ],
            expected: 'Charge needed: Input should be greater than 0; Ready by (UK time): Field required.',
        },
        { name: 'null', detail: null, expected: null },
        { name: 'unexpected shape', detail: 42, expected: null },
    ])('handles $name', ({ detail, expected }) => {
        expect(describeError(detail)).toBe(expected)
    })
})