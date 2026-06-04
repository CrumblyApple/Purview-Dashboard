import { useIndicatorState } from "./UseZState";
import { IndicatorSlug, Year, INDICATORS, DEFAULT_COLOURMAP } from "../config/Indicators";

const buildCogUrl = (indicator: IndicatorSlug, year: Year): string =>
    `/data/rasters/dasymetric/${indicator}_weighted_${year}.tif`;

interface TilesResult {
  cogUrl: string;
  tileUrl: string;
  colourmap: string;
}

export function useTiles(): TilesResult {
  const { activeIndicator, activeYear } = useIndicatorState();
  
  const cogUrl = buildCogUrl(activeIndicator, activeYear);
  const colourmap = INDICATORS[activeIndicator]["colourmap"] ?? DEFAULT_COLOURMAP;
  const tileUrl =
    `/api/cog/tiles/{z}/{x}/{y}` +
    `?url=${encodeURIComponent(cogUrl)}` +
    `&colormap_name=${colourmap}` +
    `&rescale=0,100` +
    `&return_mask=true`;
  
  return { cogUrl, tileUrl, colourmap };
}