import { useState, useCallback, useMemo, useEffect, useRef } from "react";
import DeckGL from "@deck.gl/react";
import { TileLayer } from "@deck.gl/geo-layers";
import type { GeoBoundingBox } from "@deck.gl/geo-layers/";
import { BitmapLayer } from "@deck.gl/layers";
import type { MapViewState, PickingInfo } from "@deck.gl/core";
import "maplibre-gl/dist/maplibre-gl.css";
import { WebMercatorViewport } from '@deck.gl/core';

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

const BOUNDS = {
  minLat: -45,
  maxLat: -5,
  minLng: 95,
  maxLng: 170,
};
const MIN_ZOOM      = 3.5;
const MAX_ZOOM      = 9;
const HOME_LONGITUDE = 132.5;
const HOME_LATITUDE  = -27.5;


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
  const prevLngRef = useRef<number>(HOME_LONGITUDE);

  useEffect(() => {
    if (!tileUrl) return;

    // Australia bounds at Z4 map to x: 13-14, y: 8-9
    const cacheCoordinates = [
      { z: 4, x: 13, y: 8 },
      { z: 4, x: 14, y: 8 },
      { z: 4, x: 13, y: 9 },
      { z: 4, x: 14, y: 9 },
    ];

    cacheCoordinates.forEach(({ z, x, y }) => {
      // Replace deck.gl format variables with actual numbers
      const targetUrl = tileUrl
        .replace("{z}", z.toString())
        .replace("{x}", x.toString())
        .replace("{y}", y.toString());

      // Silently pre-fetch and cache via browser image handling
      const img = new Image();
      img.src = targetUrl;
    });
  }, [tileUrl]);

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

  const clampViewState = (vs: MapViewState) => {
    const viewport = new WebMercatorViewport(vs);

    // Get current viewport edges
    const [minLng, minLat, maxLng, maxLat] = viewport.getBounds();
  
    // Calculate overshoot on each side
    const lngOvershootMin = Math.max(0, BOUNDS.minLng - minLng);
    const lngOvershootMax = Math.max(0, maxLng - BOUNDS.maxLng);
    const latOvershootMin = Math.max(0, BOUNDS.minLat - minLat);
    const latOvershootMax = Math.max(0, maxLat - BOUNDS.maxLat);

    return {
      ...vs,
      longitude: vs.longitude + lngOvershootMin - lngOvershootMax,
      latitude:  vs.latitude  + latOvershootMin - latOvershootMax,
    };
  };

  return (
    <div style={{ position: "relative", width: "100%", height: "100%" }}>
      <DeckGL
        viewState={viewState}
        onViewStateChange={({ viewState: vs }) => {
          const newVs = vs as MapViewState;
          const clampedZoom = Math.max(newVs.zoom ?? 4, MIN_ZOOM);
          const atMinZoom = clampedZoom <= MIN_ZOOM;
        
          if (atMinZoom) {
            prevLngRef.current = HOME_LONGITUDE;
            setViewState({ ...newVs, zoom: clampedZoom, longitude: HOME_LONGITUDE, latitude: HOME_LATITUDE });
            return;
          }
        
          // Detect and undo antimeridian wrap
          let lng = newVs.longitude;
          const delta = lng - prevLngRef.current;
          if (delta > 180)  lng -= 360;
          if (delta < -180) lng += 360;
          prevLngRef.current = lng;
        
          const unwrappedVs = { ...newVs, longitude: lng };
          const clamped = clampViewState(unwrappedVs);
          setViewState({ ...clamped, zoom: clampedZoom });
        }}
        controller={{
          scrollZoom: {
            smooth: false,
            speed: 0.005
          },
          dragPan: true,
          inertia: 250
        }}
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
