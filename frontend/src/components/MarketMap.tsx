import { useEffect } from 'react';
import { CircleMarker, MapContainer, TileLayer, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

import type { LatLngExpression } from 'leaflet';
import type { MarketMarker } from '../types/dashboard';
import { cn } from '../lib/cn';

type MarketMapProps = {
  market: MarketMarker;
  className?: string;
  onBack?: () => void;
  renderOverlay?: boolean;
};

const Recenter = ({ center }: { center: LatLngExpression }) => {
  const map = useMap();

  useEffect(() => {
    map.setView(center, map.getZoom(), { animate: true });
    let timeoutId: number | undefined;
    if (typeof window !== 'undefined') {
      timeoutId = window.setTimeout(() => {
        map.invalidateSize();
      }, 150);
    }

    return () => {
      if (typeof window !== 'undefined' && timeoutId !== undefined) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [center, map]);

  return null;
};

export const MarketMap = ({ market, className, onBack, renderOverlay = true }: MarketMapProps) => {
  const center: LatLngExpression = [market.location[0], market.location[1]];
  const intensity = Math.min(0.12 + (market.activeEntities / Math.max(market.entities, 1)) * 0.45, 0.65);

  return (
    <div className={cn('market-map relative h-full w-full overflow-hidden', className)}>
      <MapContainer
        center={center}
        zoom={12}
        scrollWheelZoom
        style={{ height: '100%', width: '100%' }}
        className="leaflet-container--dominion"
      >
        <TileLayer
          url="https://basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
          maxZoom={19}
        />
        <Recenter center={center} />

        <CircleMarker
          center={center}
          radius={18}
          pathOptions={{
            color: '#446e87',
            fillColor: 'rgba(249, 207, 100, 0.8)',
            fillOpacity: intensity,
            weight: 3,
          }}
        />
      </MapContainer>

      <div className="market-map__tint market-map__tint--water" aria-hidden="true" />
      <div className="market-map__tint market-map__tint--land" aria-hidden="true" />

      {renderOverlay && (
        <div className="pointer-events-none absolute inset-x-6 bottom-6 rounded-2xl border border-[rgba(68,110,135,0.45)] bg-[rgba(5,14,24,0.56)] p-5 text-[#fff7ee] backdrop-blur-md">
          <div className="pointer-events-auto flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-xs uppercase tracking-[0.18em] text-[rgba(255,247,238,0.72)]">Market focus</div>
              <h3 className="text-lg font-semibold tracking-[0.04em]">{market.label}</h3>
            </div>
            {onBack && (
              <button
                type="button"
                onClick={onBack}
                className="rounded-full border border-[rgba(249,207,100,0.65)] bg-transparent px-4 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-[#f9cf64] transition-colors hover:bg-[rgba(249,207,100,0.08)]"
              >
                Back to globe
              </button>
            )}
          </div>
          <div className="mt-4 grid gap-3 text-sm leading-relaxed text-[rgba(255,247,238,0.86)]">
            <div className="flex gap-4">
              <span className="rounded-full bg-[rgba(249,207,100,0.18)] px-3 py-1 text-xs uppercase tracking-[0.12em] text-[#f9cf64]">
                Properties {market.properties}
              </span>
              <span className="rounded-full bg-[rgba(68,110,135,0.28)] px-3 py-1 text-xs uppercase tracking-[0.12em] text-[#c0d6e3]">
                Entities {market.entities}
              </span>
              <span className="rounded-full bg-[rgba(5,14,24,0.65)] px-3 py-1 text-xs uppercase tracking-[0.12em] text-[#ffefe2]">
                Active {market.activeEntities}
              </span>
            </div>
            {market.recentActivity && <p>{market.recentActivity}</p>}
          </div>
        </div>
      )}
    </div>
  );
};
