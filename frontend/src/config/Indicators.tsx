import { ERP_RAMP } from "./ColourRamps";
import type { ColourRamp } from "./ColourRamps";

export interface IndicatorMeta {
  label: string;
  colourmap: string;
  unit: string;
  type: string;
}

export const INDICATORS: Record<string, IndicatorMeta> = {
  erp: { label: "Population", colourmap: "ylorrd", unit: "people", type: "count" },
  unemployment_rate: { label: "Unemployment", colourmap: "ylorrd", unit: "%", type: "rate" },
  seifa: { label: "Socio-economic", colourmap: "ylorrd", unit: "score", type: "rate" },
  housing_price: { label: "Housing Price", colourmap: "ylorrd", unit: "AUD", type: "count" },
  liveability: { label: "Liveability", colourmap: "ylorrd", unit: "score", type: "rate" },
} as const;

export type IndicatorSlug = keyof typeof INDICATORS;
const START_YEAR = 2021;
const CURRENT_YEAR = new Date().getFullYear();
export const DEFAULT_COLOURMAP = "ylorrd";

export const YEARS: string[] = Array.from(
    { length: CURRENT_YEAR - START_YEAR + 1 },
    (_, i) => `${START_YEAR + i}`,
);

export type Year = typeof YEARS[number];