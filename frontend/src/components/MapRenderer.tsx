import { useState, useCallback, useMemo } from "react";
import DeckGL from "@deck.gl/react";
import { TileLayer } from "@deck.gl/geo-layers";
import type { GeoBoundingBox } from "@deck.gl/geo-layers/";
import { BitmapLayer } from "@deck.gl/layers";
import type { MapViewState, PickingInfo } from "@deck.gl/core";
import "maplibre-gl/dist/maplibre-gl.css";

import { IndicatorSlug } from "../config/Indicators";

export interface PixelClickInfo {
  lat: number;
  lon: number;
  x: number;
  y: number;
}

interface MapViewProps {
  tileUrl: string | null;
  minZoom?: number;
  maxZoom?: number;
  indicator?: IndicatorSlug;
  opacity?: number;
  onPixelClick?: (info: PixelClickInfo) => void;
}

const INIT_VIEW = {
  longitude: 133.0,
  latitude: -27.0,
  zoom: 4,
  pitch: 0,
  bearing: 0,
};

const BASEMAP_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-nolabels-gl-style/style.json";
const LABELS_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

export default function MapView({
  tileUrl,
  minZoom = 0,
  maxZoom = 9,
  indicator = "erp",
  opacity = 0.85,
  onPixelClick,
}: MapViewProps) {
  const [viewState, setViewState] = useState<MapViewState>(INIT_VIEW);

  const tileLayer = useMemo(() => {
    if (!tileUrl) return null;

    return new TileLayer({
      id: `indicator-tiles-${indicator}`,
      data: tileUrl,

      extent: [112.9, -43.7, 153.7, -9.9],

      tileSize: 256,
      minZoom,
      maxZoom,

      renderSubLayers: (props) => {
        const { west, south, east, north } = props.tile.bbox as GeoBoundingBox;
        return new BitmapLayer(props, {
          data: undefined,
          image: props.data,
          bounds: [west, south, east, north],
          opacity,
          transparentColor: [0, 0, 0, 0],
          textureParameters: {
            minFilter:  "nearest",
            magFilter:  "nearest",
          },
        });
      },

      refinementStrategy: "best-available",

      onTileError: (err) => {
        console.warn("Tile load error:", err);
      },
    });
  }, [tileUrl, indicator, opacity, minZoom, maxZoom]);

  const handleClick = useCallback(
    (info: PickingInfo) => {
      if (!info.coordinate || !onPixelClick) return;
      const [lon, lat] = info.coordinate as [number, number];
      onPixelClick({ lat, lon, x: info.x, y: info.y });
    },
    [onPixelClick],
  );

  const getCursor = useCallback(
    ({ isDragging }: { isDragging: boolean }): string =>
      isDragging ? "grabbing" : "crosshair",
    [],
  );

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
        {/*<Map
          reuseMaps
          mapStyle={BASEMAP_STYLE}
          attributionControl={false}
        />*/}
      </DeckGL>

      <div
        style={{
          position: "absolute",
          inset: 0,
          pointerEvents: "none",
        }}
      >
        {/*<Map
          reuseMaps
          mapStyle={LABELS_STYLE}
          viewState={viewState}
          attributionControl={false}
          style={{ width: "100%", height: "100%" }}
        />*/}
      </div>
    </div>
  );
}
