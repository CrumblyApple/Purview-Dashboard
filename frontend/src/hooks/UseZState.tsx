/**
 * Zustand state management
 */

import { create } from "zustand";
import { INDICATORS, YEARS } from "../config/Indicators";
import type { IndicatorSlug, Year } from "../config/Indicators";
import type { PixelClickInfo } from "../components/MapRenderer";

interface State {
  // Active selections
  activeIndicator: IndicatorSlug;
  activeYear: Year;
  opacity: number;
  
  clickedPixel: PixelClickInfo | null;
  
  // Actions
  setIndicator: (indicator: IndicatorSlug) => void;
  setYear: (year: Year) => void;
  setOpacity: (opacity: number) => void;
  setClickedPixel: (pixel: PixelClickInfo | null) => void;
  clearPixel: () => void;
}

export const useIndicatorState = create<State>((set) => ({
  activeIndicator: Object.keys(INDICATORS)[0] as IndicatorSlug,
  activeYear: YEARS[YEARS.length - 1],
  opacity: 0.85,
  clickedPixel: null,
 
  setIndicator: (indicator) =>
    set((state) => ({
      activeIndicator: indicator,
      clickedPixel: state.clickedPixel ? null : state.clickedPixel,
    })),
 
  setYear: (year) => set({ activeYear: year }),
  setOpacity: (opacity) => set({ opacity: Math.max(0, Math.min(1, opacity)) }),
 
  setClickedPixel: (pixel) => set({ clickedPixel: pixel }),
  clearPixel: () => set({ clickedPixel: null }),
}));