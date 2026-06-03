export const INDICATORS = {
    erp:               { label: "Population",      colourmap: "ylorrd",   unit: "people" },
    unemployment_rate: { label: "Unemployment",    colourmap: "rdylgn_r", unit: "%" },
    seifa:             { label: "Socio-economic",  colourmap: "rdylgn",   unit: "score" },
    housing_price:     { label: "Housing Price",   colourmap: "purples",  unit: "AUD" },
    liveability:       { label: "Liveability",     colourmap: "viridis",  unit: "score" },
  } as const;
  
export type IndicatorSlug = keyof typeof INDICATORS;
const START_YEAR = 2021;
const CURRENT_YEAR = new Date().getFullYear();

export const YEARS: string[] = Array.from(
    { length: CURRENT_YEAR - START_YEAR + 1 },
    (_, i) => `${START_YEAR + i}`,
);

export type Year = typeof YEARS[number];