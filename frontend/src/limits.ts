// Must match backend/constants.py. The backend is the real check.
// These guide the form.
export const MAX_CHARGE_KWH = 250
export const MAX_CHARGE_RATE_KW = 22

// Smallest values of the form
export const MIN_CHARGE_KWH = 0.1
export const MIN_CHARGE_RATE_KW = 0.1

// Steps of the form (the backend does not discriminate)
export const STEP_CHARGE_KWH = 0.1
export const STEP_CHARGE_RATE_KW = 0.1
