import { useCallback } from "react";
import { useIndicatorState } from "../hooks/UseZState";
import { INDICATORS, YEARS } from "../config/Indicators";
import type { IndicatorSlug } from "../config/Indicators";
 
// ---------------------------------------------------------------------------
// Styles — dark glass panel, monospace aesthetic matching the data context
// ---------------------------------------------------------------------------
 
const styles = {
  panel: {
    position:        "absolute" as const,
    top:             20,
    right:           20,
    width:           220,
    background:      "rgba(10, 12, 16, 0.82)",
    backdropFilter:  "blur(12px)",
    WebkitBackdropFilter: "blur(12px)",
    border:          "1px solid rgba(255,255,255,0.08)",
    borderRadius:    4,
    padding:         "16px 14px",
    fontFamily:      "'DM Mono', 'Fira Mono', monospace",
    color:           "#c8cdd6",
    userSelect:      "none" as const,
    boxShadow:       "0 8px 32px rgba(0,0,0,0.48)",
  },
 
  section: {
    marginBottom: 18,
  },
 
  sectionLabel: {
    fontSize:      9,
    fontWeight:    600,
    letterSpacing: "0.14em",
    textTransform: "uppercase" as const,
    color:         "rgba(200,205,214,0.4)",
    marginBottom:  8,
    display:       "block",
  },
 
  indicatorBtn: (active: boolean) => ({
    display:         "flex",
    alignItems:      "center",
    gap:             8,
    width:           "100%",
    padding:         "6px 8px",
    marginBottom:    2,
    background:      active ? "rgba(255,255,255,0.07)" : "transparent",
    border:          active
                       ? "1px solid rgba(255,255,255,0.14)"
                       : "1px solid transparent",
    borderRadius:    3,
    cursor:          "pointer",
    textAlign:       "left" as const,
    transition:      "background 120ms, border-color 120ms",
  }),
 
  indicatorDot: (colourmap: string) => ({
    width:        7,
    height:       7,
    borderRadius: "50%",
    flexShrink:   0,
    background:   COLOURMAP_ACCENTS[colourmap] ?? "#888",
  }),
 
  indicatorLabel: (active: boolean) => ({
    fontSize:    11,
    fontWeight:  active ? 600 : 400,
    color:       active ? "#e8eaf0" : "rgba(200,205,214,0.6)",
    letterSpacing: "0.02em",
    transition:  "color 120ms",
  }),
 
  indicatorUnit: {
    marginLeft:  "auto",
    fontSize:    9,
    color:       "rgba(200,205,214,0.3)",
    letterSpacing: "0.06em",
  },
 
  sliderRow: {
    display:        "flex",
    alignItems:     "center",
    gap:            10,
    marginBottom:   6,
  },
 
  sliderLabel: {
    fontSize:    9,
    color:       "rgba(200,205,214,0.4)",
    letterSpacing: "0.1em",
    textTransform: "uppercase" as const,
    minWidth:    46,
  },
 
  sliderValue: {
    fontSize:    10,
    color:       "rgba(200,205,214,0.55)",
    minWidth:    32,
    textAlign:   "right" as const,
    fontVariantNumeric: "tabular-nums" as const,
  },
 
  slider: {
    flex:        1,
    appearance:  "none" as const,
    height:      2,
    background:  "rgba(255,255,255,0.12)",
    borderRadius: 2,
    outline:     "none",
    cursor:      "pointer",
    accentColor: "#7eb8f7",
  },
 
  divider: {
    height:     1,
    background: "rgba(255,255,255,0.06)",
    margin:     "14px 0",
  },
} as const;
 
// Representative accent colour per titiler colourmap name
const COLOURMAP_ACCENTS: Record<string, string> = {
  ylorrd:   "#f03b20",
  rdylgn_r: "#d73027",
  rdylgn:   "#1a9850",
  purples:  "#6a51a3",
  viridis:  "#21918c",
};
 
// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------
 
function IndicatorButton({
  slug,
  active,
  onSelect,
}: {
  slug:     IndicatorSlug;
  active:   boolean;
  onSelect: (slug: IndicatorSlug) => void;
}) {
  const meta = INDICATORS[slug];
 
  return (
    <button
      style={styles.indicatorBtn(active)}
      onClick={() => onSelect(slug)}
      aria-pressed={active}
      aria-label={`Select ${meta.label} indicator`}
    >
      {/*<span style={styles.indicatorDot(meta.colourmap)} />*/}
      <span style={styles.indicatorLabel(active)}>{meta.label}</span>
      <span style={styles.indicatorUnit}>{meta.unit}</span>
    </button>
  );
}
 
function SliderRow({
  label,
  value,
  min,
  max,
  step,
  displayValue,
  onChange,
}: {
  label:        string;
  value:        number;
  min:          number;
  max:          number;
  step:         number;
  displayValue: string;
  onChange:     (v: number) => void;
}) {
  return (
    <div style={styles.sliderRow}>
      <span style={styles.sliderLabel}>{label}</span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        style={styles.slider}
        onChange={(e) => onChange(Number(e.target.value))}
        aria-label={label}
      />
      <span style={styles.sliderValue}>{displayValue}</span>
    </div>
  );
}
 
// ---------------------------------------------------------------------------
// Panel
// ---------------------------------------------------------------------------
 
export default function LayerPanel() {
  const {
    activeIndicator,
    activeYear,
    opacity,
    setIndicator,
    setYear,
    setOpacity,
  } = useIndicatorState();
 
  const handleYearChange = useCallback(
    (v: number) => setYear(String(v)),
    [setYear],
  );
 
  const handleOpacityChange = useCallback(
    (v: number) => setOpacity(v / 100),
    [setOpacity],
  );
 
  const yearMin = Number(YEARS[0]);
  const yearMax = Number(YEARS[YEARS.length - 1]);
 
  return (
    <div style={styles.panel} role="region" aria-label="Layer controls">
 
      {/* Indicator selector */}
      <div style={styles.section}>
        <span style={styles.sectionLabel}>Indicator</span>
        {(Object.keys(INDICATORS) as IndicatorSlug[]).map((slug) => (
          <IndicatorButton
            key={slug}
            slug={slug}
            active={slug === activeIndicator}
            onSelect={setIndicator}
          />
        ))}
      </div>
 
      <div style={styles.divider} />
 
      {/* Year slider */}
      <div style={styles.section}>
        <span style={styles.sectionLabel}>Year</span>
        <SliderRow
          label="Year"
          value={Number(activeYear)}
          min={yearMin}
          max={yearMax}
          step={1}
          displayValue={activeYear}
          onChange={handleYearChange}
        />
      </div>
 
      <div style={styles.divider} />
 
      {/* Opacity slider */}
      <div style={styles.section}>
        <span style={styles.sectionLabel}>Display</span>
        <SliderRow
          label="Opacity"
          value={Math.round(opacity * 100)}
          min={0}
          max={100}
          step={5}
          displayValue={`${Math.round(opacity * 100)}%`}
          onChange={handleOpacityChange}
        />
      </div>
 
    </div>
  );
}
 