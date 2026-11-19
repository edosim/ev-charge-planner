
export type Intensity = {
    forecast: number;
    actual: number | null;
    index: string | null;
};

export type Slot = {
    from: string;
    to: string;
    intensity: Intensity;
};

export type ScheduleResponse = {
    slots: Slot[];
    forecast: Slot[];
    emissions_kg: number;
    charge_now_kg: number;
    saved_kg: number;
    charge_delivered_kwh: number;
    fully_charged: boolean;
}