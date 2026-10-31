export type IntensityIndex = 'very low'| 'low'| 'moderate'| 'high'| 'very high';

export type Intensity = {
    forecast: number;
    actual: number | null;
    index: IntensityIndex;
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
    fully_charged: boolean;
}