import { MutableRefObject, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import GlobeGl, { type GlobeMethods } from 'react-globe.gl';
import { feature } from 'topojson-client';
import type { FeatureCollection, MultiPolygon, Polygon } from 'geojson';
import { geoArea } from 'd3-geo';

import { cn } from '../lib/cn';
import countriesTopology from '../data/countries-50m.json';

type GeoPoint = {
  location: [latitude: number, longitude: number];
  size?: number;
  label?: string;
  marketCode?: string;
  recentActivity?: string;
  confidence?: number;
  confidenceLabel?: string;
};

type GlobeProps = {
  className?: string;
  markers?: GeoPoint[];
  focusMarket?: GeoPoint | null;
  onMarkerSelect?: (marker: GeoPoint) => void;
  disableZoom?: boolean;
  autoRotate?: boolean;
  showAtmosphere?: boolean;
  onReady?: () => void;
};

type MarkerPoint = {
  id: string;
  lat: number;
  lng: number;
  size: number;
  label: string;
  marker: GeoPoint;
  emphasis: 'focus' | 'default';
  color: string;
  glow: string;
  confidenceTier: ConfidenceTier;
  confidenceLabel?: string;
  confidenceValue?: number;
};

type ConfidenceTier = 'high' | 'medium' | 'low' | 'unknown';

const CONFIDENCE_COLORS: Record<ConfidenceTier, { fill: string; glow: string }> = {
  high: { fill: 'rgba(40, 161, 125, 0.9)', glow: 'rgba(40, 161, 125, 0.45)' },
  medium: { fill: 'rgba(240, 190, 70, 0.92)', glow: 'rgba(240, 190, 70, 0.5)' },
  low: { fill: 'rgba(223, 82, 68, 0.92)', glow: 'rgba(223, 82, 68, 0.55)' },
  unknown: { fill: 'rgba(102, 132, 151, 0.8)', glow: 'rgba(102, 132, 151, 0.4)' },
};

const inferConfidenceTier = (confidence?: number, label?: string): ConfidenceTier => {
  if (typeof confidence === 'number' && !Number.isNaN(confidence)) {
    if (confidence >= 0.75) return 'high';
    if (confidence >= 0.45) return 'medium';
    return 'low';
  }
  const normalized = label?.toLowerCase();
  if (!normalized) {
    return 'unknown';
  }
  if (normalized.includes('high')) return 'high';
  if (normalized.includes('medium') || normalized.includes('moderate')) return 'medium';
  if (normalized.includes('low')) return 'low';
  return 'unknown';
};

const WATER_COLOR = '#446e87';
const LAND_COLOR = '#fdf5ed';
const COUNTRY_BORDER_COLOR = 'rgba(5, 14, 24, 0.44)';

const createWaterTexture = () => {
  if (typeof document === 'undefined') {
    return null;
  }
  const canvas = document.createElement('canvas');
  canvas.width = 2;
  canvas.height = 2;
  let ctx: CanvasRenderingContext2D | null = null;
  try {
    ctx = canvas.getContext('2d');
  } catch {
    // jsdom may throw for getContext; fall back to solid color
    return null;
  }
  if (!ctx) {
    return null;
  }
  ctx.fillStyle = WATER_COLOR;
  ctx.fillRect(0, 0, 2, 2);
  return canvas.toDataURL('image/png');
};

const preparePolygons = (countriesTopo: any) => {
  const collection = feature(
    countriesTopo as any,
    (countriesTopo as any).objects.countries,
  ) as unknown as FeatureCollection<Polygon | MultiPolygon>;
  const features = collection.features ?? [];
  // Reduce detail by dropping very small landmasses (tiny islands)
  const AREA_THRESHOLD = 2.4e-3; // steradians; tune to balance detail vs performance
  return features.filter((f) => {
    try {
      return geoArea(f) >= AREA_THRESHOLD;
    } catch {
      return true;
    }
  });
};

const GlobeCore = ({
  className,
  markers = [],
  focusMarket = null,
  onMarkerSelect,
  disableZoom = false,
  autoRotate = true,
  showAtmosphere = false,
  onReady,
}: GlobeProps) => {
  const globeRef = useRef<GlobeMethods | undefined>(undefined);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [containerSize, setContainerSize] = useState({ width: 0, height: 0 });
  const [hasEmittedReady, setHasEmittedReady] = useState(false);
  const waterTexture = useMemo(createWaterTexture, []);
  const polygons = useMemo(() => preparePolygons(countriesTopology), []);
  // Keep interactions simple; no lock state
  const canUseWebGL = useMemo(() => {
    if (typeof window === 'undefined' || typeof document === 'undefined') return false;
    try {
      const canvas = document.createElement('canvas');
      // Some environments throw on getContext
      const gl = (canvas as any).getContext?.('webgl') || (canvas as any).getContext?.('experimental-webgl');
      return !!gl;
    } catch {
      return false;
    }
  }, []);

  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;

    const updateSize = () => {
      const rect = element.getBoundingClientRect();
      setContainerSize({
        width: Math.max(rect.width, 0),
        height: Math.max(rect.height, 0),
      });
    };

    updateSize();
    // Use ResizeObserver when available; otherwise, window resize fallback
    const RO: typeof ResizeObserver | undefined = (globalThis as any).ResizeObserver;
    if (RO) {
      const observer = new RO(updateSize);
      observer.observe(element);
      return () => observer.disconnect();
    } else {
      window.addEventListener('resize', updateSize);
      return () => window.removeEventListener('resize', updateSize);
    }
  }, []);

  useEffect(() => {
    const globe = globeRef.current;
    if (!globe || !canUseWebGL) {
      return;
    }
    const renderer = globe.renderer?.();
    // Transparent background so page shows through
    renderer?.setClearColor('rgba(0,0,0,0)', 0);
    // Lower device pixel ratio for performance on high-DPI screens
    try {
      const dpr = Math.min(1.25, (window as any).devicePixelRatio || 1);
      renderer?.setPixelRatio?.(dpr);
    } catch {}

    const globeWithMaterial = globe as unknown as { globeMaterial?: () => any };
    const material = globeWithMaterial.globeMaterial?.();
    if (material) {
      // Exact water color without shading shifts
      material.color?.set?.(WATER_COLOR);
      if (material.emissive) material.emissive.set?.('#000000');
      if ('emissiveIntensity' in material) material.emissiveIntensity = 0;
      if ('metalness' in material) material.metalness = 0;
      if ('roughness' in material) material.roughness = 1;
      if ('wireframe' in material) material.wireframe = false;
      if ('depthWrite' in material) material.depthWrite = true;
    }

  const controls = globe.controls();
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
  controls.autoRotate = !!autoRotate;
  controls.autoRotateSpeed = 0.35;
    controls.minPolarAngle = 0.12;
    controls.maxPolarAngle = Math.PI - 0.12;
    // Keep camera comfortably outside the sphere (globe radius ~100)
    controls.minDistance = 120;
    controls.maxDistance = 420;
    controls.enableZoom = !disableZoom;
    controls.enablePan = false;
  }, [waterTexture, canUseWebGL, disableZoom, autoRotate]);

  const unlockControls = useCallback(() => {
    const globe = globeRef.current;
    if (!globe || !canUseWebGL) return;
    const controls = globe.controls();
  controls.autoRotate = !!autoRotate;
    controls.enableRotate = true;
    controls.enableZoom = !disableZoom;
    controls.minAzimuthAngle = -Infinity;
    controls.maxAzimuthAngle = Infinity;
    controls.minPolarAngle = 0.12;
    controls.maxPolarAngle = Math.PI - 0.12;
    controls.minDistance = 120;
    controls.maxDistance = 420;
    controls.update();
  }, [canUseWebGL, disableZoom, autoRotate]);
  // No lockControls; keep interactions fluid

  useEffect(() => {
    const globe = globeRef.current;
    if (!globe || !canUseWebGL) return;
    unlockControls();
    if (!focusMarket) {
      // Default view keeps a broad vantage before data loads
      globe.pointOfView({ lat: 20, lng: -40, altitude: 2.15 }, 0);
      return;
    }

    const markerSize = focusMarket.size ?? 0.08;
    const zoomedAltitude = Math.min(1.6, Math.max(1.18, 1.9 - markerSize * 2.4));
    const target = {
      lat: focusMarket.location[0],
      lng: focusMarket.location[1],
      altitude: zoomedAltitude,
    };
    const focusTimeout = window.setTimeout(() => {
      globe.pointOfView(target, autoRotate ? 600 : 0);
    }, 50);
    return () => {
      window.clearTimeout(focusTimeout);
    };
  }, [focusMarket, unlockControls, canUseWebGL, autoRotate]);

  // No control locking hooks

  const points = useMemo<MarkerPoint[]>(() => {
    const focusCode = focusMarket?.marketCode;
    const focusLat = focusMarket?.location[0];
    const focusLng = focusMarket?.location[1];

    return markers.map((marker) => {
      const id = marker.marketCode ?? marker.label ?? marker.location.join(',');
      const baseSize = marker.size ?? 0.06;
      const clampedSize = Math.max(0.025, Math.min(0.14, baseSize));
      const emphasis =
        focusMarket &&
        ((focusCode && marker.marketCode && focusCode === marker.marketCode) ||
          (typeof focusLat === 'number' &&
            typeof focusLng === 'number' &&
            focusLat === marker.location[0] &&
            focusLng === marker.location[1]))
          ? 'focus'
          : 'default';

      const confidenceSourceLabel = marker.confidenceLabel ?? marker.recentActivity;
      const confidenceTier = inferConfidenceTier(marker.confidence, confidenceSourceLabel);
      const { fill, glow } = CONFIDENCE_COLORS[confidenceTier];
      const glowColor = emphasis === 'focus' ? 'rgba(255, 255, 255, 0.55)' : glow;

      return {
        id,
        lat: marker.location[0],
        lng: marker.location[1],
        size: clampedSize,
        label: marker.label ?? marker.marketCode ?? '',
        marker,
        emphasis,
        color: fill,
        glow: glowColor,
        confidenceTier,
        confidenceLabel:
          marker.confidenceLabel ?? (confidenceTier !== 'unknown'
            ? `${confidenceTier.charAt(0).toUpperCase()}${confidenceTier.slice(1)} confidence`
            : undefined),
        confidenceValue: marker.confidence,
      };
    });
  }, [focusMarket, markers]);

  const handlePointClick = useCallback(
    (point: object) => {
      const markerPoint = point as MarkerPoint;
      if (markerPoint?.marker && onMarkerSelect) {
        onMarkerSelect(markerPoint.marker);
      }
    },
    [onMarkerSelect],
  );

  const width = containerSize.width || 640;
  const height = containerSize.height || 640;

  useEffect(() => {
    if (hasEmittedReady) {
      return;
    }
    const hasSize = containerSize.width > 0 && containerSize.height > 0;
    if (!hasSize) {
      return;
    }
    if (!canUseWebGL) {
      onReady?.();
      setHasEmittedReady(true);
      return;
    }
    if (globeRef.current) {
      onReady?.();
      setHasEmittedReady(true);
    }
  }, [canUseWebGL, containerSize, hasEmittedReady, onReady]);

  return (
    <div ref={containerRef} className={cn('globe-core', className)}>
      {canUseWebGL ? (
        <GlobeGl
          ref={globeRef as MutableRefObject<GlobeMethods | undefined>}
          width={width}
          height={height}
          rendererConfig={{ alpha: true, antialias: false, preserveDrawingBuffer: false, powerPreference: 'high-performance', logarithmicDepthBuffer: true }}
          backgroundColor="rgba(0,0,0,0)"
          globeImageUrl={waterTexture ?? undefined}
          showAtmosphere={showAtmosphere}
          atmosphereAltitude={0.14}
          atmosphereColor="#fdf5ed"
          polygonsData={polygons as unknown as object[]}
          polygonAltitude={() => 0.006}
          polygonCapColor={() => LAND_COLOR}
          polygonSideColor={() => 'rgba(0,0,0,0)'}
          polygonStrokeColor={() => COUNTRY_BORDER_COLOR}
          polygonsTransitionDuration={0}
          pointsData={points as unknown as object[]}
          pointLat="lat"
          pointLng="lng"
          pointAltitude={(obj: any) => 0.06 + (obj.size ?? 0) * 0.08}
          pointColor={(obj: any) => obj.color}
          pointRadius={(obj: any) => 0.24 + (obj.size ?? 0) * 0.8}
          pointLabel={(obj: any) => obj.label ?? ''}
          pointResolution={14}
          pointsMerge={false}
          onPointClick={
            handlePointClick as (
              point: object,
              event: MouseEvent,
              coords: { lat: number; lng: number; altitude: number },
            ) => void
          }
          onPointHover={(obj: any) => {
            if (!containerRef.current) return;
            containerRef.current.style.cursor = obj ? 'pointer' : 'grab';
          }}
          enablePointerInteraction
          animateIn
        />
      ) : (
        <div style={{ width: '100%', height: '100%', background: '#1a2a35' }} aria-hidden="true" />
      )}
    </div>
  );
};

export default GlobeCore;
