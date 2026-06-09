import { useCallback } from "react";
import { usePixelStats, useActivePixelValue } from "../hooks/UsePixel";
import { useIndicatorState } from "../hooks/UseZState";
import { INDICATORS } from "../config/Indicators";
import type { IndicatorSlug } from "../config/Indicators";
import type { PixelStats } from "../hooks/UsePixel";
 
// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------
 
function formatValue(
  value: number | null,
  slug:  IndicatorSlug,
): string {
  if (value === null || !isFinite(value)) return "—";
  const { unit } = INDICATORS[slug];
 
  switch (slug) {
    case "erp":
      // Population — no decimals, thousands separator
      return `${Math.round(value).toLocaleString("en-AU")} ${unit}`;
    case "unemployment_rate":
      return `${value.toFixed(1)} ${unit}`;
    case "housing_price":
      // AUD — currency format
      return new Intl.NumberFormat("en-AU", {
        style:    "currency",
        currency: "AUD",
        maximumFractionDigits: 0,
      }).format(value);
    case "seifa":
    case "liveability":
      return `${value.toFixed(1)}`;
    default:
      return `${value.toFixed(2)} ${unit}`;
  }
}
 
function formatCoord(v: number, decimals = 4): string {
  return v.toFixed(decimals);
}
 
// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------
 
const styles = {
  panel: {
    position:            "absolute" as const,
    bottom:              20,
    right:               20,
    width:               "12vw",
    background:          "rgba(10, 12, 16, 0.6)",
    backdropFilter:      "blur(12px)",
    WebkitBackdropFilter: "blur(12px)",
    borderRadius:        4,
    fontFamily:          "'DM Mono', 'Fira Mono', monospace",
    color:               "#c8cdd6",
    overflow:            "hidden" as const,
  },
 
  header: {
    display:         "flex",
    alignItems:      "center",
    justifyContent:  "space-between",
    padding:         "10px 12px 8px",
    borderBottom:    "1px solid rgba(255,255,255,0.06)",
  },
 
  headerLabel: {
    fontSize:      9,
    fontWeight:    600,
    letterSpacing: "0.14em",
    textTransform: "uppercase" as const,
    color:         "rgba(255, 255, 255, 0.4)",
  },
 
  closeBtn: {
    background:  "none",
    border:      "none",
    color:       "rgba(255, 255, 255, 0.35)",
    cursor:      "pointer",
    fontSize:    14,
    lineHeight:  1,
    padding:     "0 2px",
    transition:  "color 120ms",
  },
 
  coords: {
    padding:     "6px 12px",
    fontSize:    9,
    color:       "rgba(200,205,214,0.35)",
    letterSpacing: "0.06em",
    borderBottom: "1px solid rgba(255,255,255,0.04)",
    fontVariantNumeric: "tabular-nums" as const,
  },
 
  sa2: {
    padding:     "6px 12px 2px",
    fontSize:    10,
    color:       "rgba(200,205,214,0.55)",
    letterSpacing: "0.02em",
  },
 
  // Primary metric — large display
  primaryBlock: {
    padding:     "10px 12px 12px",
    borderBottom: "1px solid rgba(255,255,255,0.06)",
  },
 
  primarySlug: {
    fontSize:      8,
    fontWeight:    600,
    letterSpacing: "0.16em",
    textTransform: "uppercase" as const,
    color:         "rgba(200,205,214,0.35)",
    marginBottom:  4,
    display:       "block",
  },
 
  primaryValue: {
    fontSize:      24,
    fontWeight:    600,
    color:         "#e8eaf0",
    letterSpacing: "-0.02em",
    lineHeight:    1,
    fontVariantNumeric: "tabular-nums" as const,
  },
 
  // Secondary metrics list
  metricsList: {
    padding: "8px 0 4px",
  },
 
  metricRow: (active: boolean) => ({
    display:        "flex",
    alignItems:     "center",
    padding:        "5px 12px",
    background:     active ? "rgba(255,255,255,0.04)" : "transparent",
  }),
 
  metricDot: (colourmap: string) => ({
    width:        5,
    height:       5,
    borderRadius: "50%",
    background:   COLOURMAP_ACCENTS[colourmap] ?? "#555",
    marginRight:  8,
    flexShrink:   0,
  }),
 
  metricLabel: (active: boolean) => ({
    fontSize:    10,
    color:       active ? "rgba(200,205,214,0.8)" : "rgba(200,205,214,0.4)",
    flex:        1,
    letterSpacing: "0.02em",
  }),
 
  metricValue: (active: boolean) => ({
    fontSize:    10,
    color:       active ? "#e8eaf0" : "rgba(200,205,214,0.5)",
    fontVariantNumeric: "tabular-nums" as const,
    letterSpacing: "0.02em",
  }),
 
  // Loading / error states
  stateBlock: {
    padding:    "20px 12px",
    textAlign:  "center" as const,
  },
 
  spinner: {
    display:      "inline-block",
    width:        16,
    height:       16,
    border:       "2px solid rgba(255,255,255,0.1)",
    borderTop:    "2px solid rgba(200,205,214,0.6)",
    borderRadius: "50%",
    animation:    "spin 0.8s linear infinite",
  },
 
  errorText: {
    fontSize: 11,
    color:    "rgba(255, 111, 111, 0.8)",
  },
 
  nodata: {
    fontSize: 10,
    color:    "rgba(200,205,214,0.3)",
    padding:  "12px",
    textAlign: "center" as const,
  },
} as const;
 
const COLOURMAP_ACCENTS: Record<string, string> = {
  ylorrd:   "#f03b20",
  rdylgn_r: "#d73027",
  rdylgn:   "#1a9850",
  purples:  "#6a51a3",
  viridis:  "#21918c",
};
 
const SLUGS = Object.keys(INDICATORS) as IndicatorSlug[];
 
// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------
 
function CoordBar({ lat, lon }: { lat: number; lon: number }) {
  return (
    <div style={styles.coords}>
      {formatCoord(lat)}°{lat >= 0 ? "N" : "S"}&nbsp;&nbsp;
      {formatCoord(lon)}°{lon >= 0 ? "E" : "W"}
    </div>
  );
}
 
function SA2Label({ code, name }: { code: string | null; name: string | null }) {
  if (!name && !code) return null;
  return (
    <div style={styles.sa2}>
      {name ?? code}
    </div>
  );
}
 
function PrimaryMetric({
  slug,
  value,
}: {
  slug:  IndicatorSlug;
  value: number | null;
}) {
  return (
    <div style={styles.primaryBlock}>
      <span style={styles.primarySlug}>{INDICATORS[slug].label}</span>
      <span style={styles.primaryValue}>{formatValue(value, slug)}</span>
    </div>
  );
}
 
function MetricRow({
  slug,
  value,
  active,
}: {
  slug:   IndicatorSlug;
  value:  number | null;
  active: boolean;
}) {
  const meta = INDICATORS[slug];
  return (
    <div style={styles.metricRow(active)}>
      {/*<span style={styles.metricDot(meta.colourmap)} />*/}
      <span style={styles.metricLabel(active)}>{meta.label}</span>
      <span style={styles.metricValue(active)}>
        {formatValue(value, slug)}
      </span>
    </div>
  );
}
 
function LoadingState({ lat, lon }: { lat: number; lon: number }) {
  return (
    <>
      <CoordBar lat={lat} lon={lon} />
      <div style={styles.stateBlock}>
        {/* Spinner animation injected via a style tag — avoids needing
            a CSS file just for one keyframe */}
        <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
        <span style={styles.spinner} />
      </div>
    </>
  );
}
 
function ErrorState({ message }: { message: string }) {
  return (
    <div style={styles.stateBlock}>
      <span style={styles.errorText}>
        Failed to load stats — {message}
      </span>
    </div>
  );
}
 
function SuccessState({ data }: { data: PixelStats }) {
  const { activeIndicator } = useIndicatorState();
 
  // Check if this location has any data at all
  const hasAnyData = SLUGS.some(
    (slug) => data[slug as keyof PixelStats] !== null,
  );
 
  if (!hasAnyData) {
    return <div style={styles.nodata}>No data at this location</div>;
  }
 
  const primaryValue = data[activeIndicator as keyof PixelStats] as number | null;
 
  return (
    <>
      <CoordBar lat={data.lat} lon={data.lon} />
      <SA2Label code={data.sa2_code} name={data.sa2_name} />
 
      <PrimaryMetric slug={activeIndicator} value={primaryValue} />
 
      <div style={styles.metricsList}>
        {SLUGS
          .filter((slug) => slug !== activeIndicator)
          .map((slug) => (
            <MetricRow
              key={slug}
              slug={slug}
              value={data[slug as keyof PixelStats] as number | null}
              active={false}
            />
          ))}
      </div>
    </>
  );
}
 
// ---------------------------------------------------------------------------
// Panel
// ---------------------------------------------------------------------------
 
export default function InspectPanel() {
  const stats          = usePixelStats();
  const { clickedPixel, clearPixel } = useIndicatorState();
 
  const handleClose = useCallback(() => clearPixel(), [clearPixel]);
 
  // Not visible until something is clicked
  if (stats.status === "idle" || !clickedPixel) return null;
 
  return (
    <div
      style={styles.panel}
      role="region"
      aria-label="Location statistics"
      aria-live="polite"
    >
      {/* Header — always shown */}
      <div style={styles.header}>
        <span style={styles.headerLabel}>Location</span>
        <button
          style={styles.closeBtn}
          onClick={handleClose}
          aria-label="Close inspect panel"
        >
          ✕
        </button>
      </div>
 
      {/* Content — switches on fetch state */}
      {stats.status === "loading" && (
        <LoadingState lat={clickedPixel.lat} lon={clickedPixel.lon} />
      )}
      {stats.status === "error" && (
        <ErrorState message={stats.message} />
      )}
      {stats.status === "success" && (
        <SuccessState data={stats.data} />
      )}
    </div>
  );
}