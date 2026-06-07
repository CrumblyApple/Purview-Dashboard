import { useEffect, useState, useMemo } from "react";

import { useIndicatorState } from "./UseZState";
import { INDICATORS, DEFAULT_COLOURMAP } from "../config/Indicators";

interface CogDataset {
  path: string;
  minzoom: number;
  maxzoom: number;
  rescale: [number, number];
}

interface TilesResult {
  tileUrl: string | null;
  colourmap: string;
  minZoom: number;
  maxZoom: number;
}

export function useTiles(): TilesResult {
  const { activeIndicator, activeYear } = useIndicatorState();
  const [dataset, setDataset] = useState<CogDataset | null>(null);

  const colourmap = INDICATORS[activeIndicator]["colourmap"] ?? DEFAULT_COLOURMAP;

  useEffect(() => {
    setDataset(null);
    fetch(`/api/cog/datasets/${activeIndicator}/${activeYear}`)
      .then((r) => {
        if (!r.ok) throw new Error("dataset not found");
        return r.json() as Promise<CogDataset>;
      })
      .then(setDataset)
      .catch(() => setDataset(null));
  }, [activeIndicator, activeYear]);

  const useLogScale = INDICATORS[activeIndicator].type === "count";

  const tileUrl = useMemo(() => {
    if (!dataset) return null;
    const [rmin, rmax] = dataset.rescale;

    // Log scale parameters that are log-normally distributed (typically counts)
    const expression = useLogScale ? `log1p(b1)` : "";
    const logMin = useLogScale ? Math.log1p(rmin) : rmin;
    const logMax = useLogScale ? Math.log1p(rmax) : rmax;

    return (
      `/api/cog/tiles/WebMercatorQuad/{z}/{x}/{y}` +
      `?url=${encodeURIComponent(dataset.path)}` +
      `&expression=${expression}` +
      `&colormap_name=${activeIndicator}` +
      `&rescale=${logMin},${logMax}` +
      `&return_mask=true`
    );
  }, [dataset, colourmap]);

  return {
    tileUrl,
    colourmap,
    minZoom: dataset?.minzoom ?? 0,
    maxZoom: dataset?.maxzoom ?? 9,
  };
}
