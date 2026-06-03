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
    activeYear:      Year;
    opacity:         number;
   
    // Currently clicked pixel — null when inspect panel is closed
    clickedPixel: PixelClickInfo | null;
   
    // Actions
    setIndicator:    (indicator: IndicatorSlug) => void;
    setYear:         (year: Year) => void;
    setOpacity:      (opacity: number) => void;
    setClickedPixel: (pixel: PixelClickInfo | null) => void;
    clearPixel:      () => void;
  }