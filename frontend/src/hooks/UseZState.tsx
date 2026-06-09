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
  
  clickedPixel: PixelClickInfo | null;
  
  // Actions
  setIndicator: (indicator: IndicatorSlug) => void;
  setYear: (year: Year) => void;
  setClickedPixel: (pixel: PixelClickInfo | null) => void;
  clearPixel: () => void;
}

export const useIndicatorState = create<State>((set) => ({
  activeIndicator: Object.keys(INDICATORS)[0] as IndicatorSlug,
  activeYear: '2025',
  clickedPixel: null,
 
  setIndicator: (indicator) =>
    set((state) => ({
      activeIndicator: indicator,
      clickedPixel: state.clickedPixel ? null : state.clickedPixel,
    })),
 
  setYear: (year) => set({ activeYear: year }),
 
  setClickedPixel: (pixel) => set({ clickedPixel: pixel }),
  clearPixel: () => set({ clickedPixel: null }),
}));