/**
 * Fetch per-pixel values via fast-api endpoint (based on selected pixel)
 */

import { useState, useEffect, use } from "react";
import { useIndicatorState } from "./UseZState";
import type { IndicatorSlug } from "../config/Indicators";

export interface PixelStats {
    // One value per indicator — null if nodata at this location
    erp:               number | null;
    unemployment_rate: number | null;
    seifa:             number | null;
    housing_price:     number | null;
    liveability:       number | null;

    // Geographic context
    lat:      number;
    lon:      number;
    sa2_code: string | null;
    sa2_name: string | null;
}
   
type FetchState =
| { status: "idle" }
| { status: "loading" }
| { status: "success"; data: PixelStats }
| { status: "error";   message: string };

export function usePixelStats(): FetchState {
    const { clickedPixel, activeYear } = useIndicatorState();
    const [state, setState] = useState<FetchState>({ status: "idle" });
   
    useEffect(() => {
      // Nothing clicked — reset to idle
      if (!clickedPixel) {
        setState({ status: "idle" });
        return;
      }
   
      const { lat, lon } = clickedPixel;
      const controller   = new AbortController();
   
      setState({ status: "loading" });
   
      const url = `/api/stats?lat=${lat}&lon=${lon}&year=${activeYear}`;
   
      fetch(url, { signal: controller.signal })
        .then((res) => {
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          return res.json() as Promise<PixelStats>;
        })
        .then((data) => setState({ status: "success", data }))
        .catch((err: Error) => {
          if (err.name === "AbortError") return;
          setState({ status: "error", message: err.message });
        });
   
      // Cancel in-flight request if the user clicks elsewhere before
      // the previous fetch resolves
      return () => controller.abort();
    }, [clickedPixel, activeYear]);
   
    return state;
}

export function useActivePixelValue(): number | null {
    const stats          = usePixelStats();
    const activeIndicator = useIndicatorState((s) => s.activeIndicator);
   
    if (stats.status !== "success") return null;
    return stats.data[activeIndicator as keyof PixelStats] as number | null;
}