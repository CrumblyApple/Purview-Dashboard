import { useState, useCallback, useMemo } from "react";
import DeckGL from "@deck.gl/react";
import { TileLayer } from "@deck.gl/geo-layers";
import type { GeoBoundingBox } from "@deck.gl/geo-layers/";
import { BitmapLayer } from "@deck.gl/layers";
import type { MapViewState, PickingInfo } from "@deck.gl/core";
import { Map } from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";

export interface PixelClickInfo {
  lat: number;
  lon: number;
  x: number;
  y: number;
}

export type IndicatorSlug = "erp" | "housing_price"

interface MapViewProps {
  cogUrl: string | null;
  indicator?: IndicatorSlug;
  opacity?: number;
  onPixelClick?: (info: PixelClickInfo) => void;
}

const INIT_VIEW = {
    longitude: 134.5,
    latitude: -25.5,
    zoom: 4,
    pitch: 0,
    bearing: 0,
  };

const BASEMAP_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-nolabels-gl-style/style.json";
const LABELS_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

const TILE_URL_TEMPLATE = (cogUrl: string, colourmap: string) =>
    `/api/cog/tiles/{z}/{x}/{y}?url=${encodeURIComponent(cogUrl)}`
    + `&colormap_name=${colourmap}`
    + `&rescale=0,100`
    + `&return_mask=true`;

const INDICATOR_COLOURMAPS = {
    erp:                "ylorrd",       // yellow → red, population density
    unemployment_rate:  "rdylgn_r",     // red → green reversed (high = bad)
    seifa:              "rdylgn",       // red → green (high = good)
    housing_price:      "purples",      // light → dark purple
    liveability:        "viridis",      // perceptually uniform
    };

export default function MapView({
  cogUrl,
  indicator = "erp",
  opacity = 0.85,
  onPixelClick
}: MapViewProps) {
  const [viewState, setViewState] = useState<MapViewState>(INIT_VIEW);
 
  const tileLayer = useMemo(() => {
    if (!cogUrl) return null;
 
    const colourmap = INDICATOR_COLOURMAPS[indicator as keyof typeof INDICATOR_COLOURMAPS] ?? "viridis";
    const tileUrl   = TILE_URL_TEMPLATE(cogUrl, colourmap);
 
    return new TileLayer({
      id: `indicator-tiles-${indicator}`,
      data: tileUrl,
 
      tileSize: 256,
      minZoom: 0,
      maxZoom: 14,
 
      // Render each tile as a bitmap
      renderSubLayers: (props) => {
        const { west, south, east, north } = props.tile.bbox as GeoBoundingBox;
        return new BitmapLayer(props, {
          data: undefined,
          image: props.data,
          bounds: [west, south, east, north],
          opacity,
          transparentColor: [0, 0, 0, 0]
        });
      },
 
      // Show previous tiles while new ones load to prevent flickering
      refinementStrategy: "best-available",
 
      onTileError: (err) => {
        console.warn("Tile load error:", err);
      },
    });
  }, [cogUrl, indicator, opacity]);

  const handleClick = useCallback(
    (info: PickingInfo) => {
      if (!info.coordinate || !onPixelClick) return;
      const [lon, lat] = info.coordinate as [number, number];
      onPixelClick({ lat, lon, x: info.x, y: info.y });
    },
  [onPixelClick]);

  const getCursor = useCallback(
    ({ isDragging }: { isDragging: boolean }): string =>
      isDragging ? "grabbing" : "crosshair",
  []);

  return (
    <div style={{ position: "relative", width: "100%", height: "100%" }}>
      <DeckGL
        viewState={viewState}
        onViewStateChange={({ viewState: vs }) =>
          setViewState(vs as MapViewState)
        }
        controller={true}
        layers={tileLayer ? [tileLayer] : []}
        onClick={handleClick}
        getCursor={getCursor}
        style={{ position: "absolute", inset: "0" }}
      >
        <Map
          reuseMaps
          mapStyle={BASEMAP_STYLE}
          attributionControl={false}
        />
      </DeckGL>
 
      {/* Labels overlay — pointer events disabled so clicks pass through */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          pointerEvents: "none",
        }}
      >
        <Map
          reuseMaps
          mapStyle={LABELS_STYLE}
          viewState={viewState}
          attributionControl={false}
          style={{ width: "100%", height: "100%" }}
        />
      </div>
    </div>
  );
}