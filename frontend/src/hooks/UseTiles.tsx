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

  const tileUrl = useMemo(() => {
    if (!dataset) return null;
    const [rmin, rmax] = dataset.rescale;

    const base   = `/api/tiles/${activeIndicator}/${activeYear}`;
    const params = `rescale=${rmin},${rmax}`;
  
    return `${base}/{z}/{x}/{y}?${params}`;
  }, [dataset, colourmap]);

  return {
    tileUrl,
    minZoom: dataset?.minzoom ?? 0,
    maxZoom: dataset?.maxzoom ?? 9,
  };
}
