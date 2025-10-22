import { useEffect } from 'react';
import { CircleMarker, MapContainer, TileLayer, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

import type { LatLngExpression } from 'leaflet';
import type { MarketMarker, PropertyDetail } from '../types/dashboard';
import { cn } from '../lib/cn';

type MarketMapProps = {
  market: MarketMarker;
  className?: string;
  onBack?: () => void;
  onNextProperty?: () => void;
  renderOverlay?: boolean;
  propertyDetail?: PropertyDetail;
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

const formatCurrency = (value?: number) => {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return undefined;
  }
  return value.toLocaleString(undefined, { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
};

const formatLotSize = (detail?: PropertyDetail) => {
  if (!detail) {
    return undefined;
  }
  if (typeof detail.lotSizeSqft === 'number' && !Number.isNaN(detail.lotSizeSqft)) {
    const acres =
      typeof detail.acreage === 'number' && !Number.isNaN(detail.acreage)
        ? detail.acreage
        : parseFloat((detail.lotSizeSqft / 43560).toFixed(2));
    return `${detail.lotSizeSqft.toLocaleString()} sqft (${acres.toFixed(2)} acres)`;
  }
  if (typeof detail.acreage === 'number' && !Number.isNaN(detail.acreage)) {
    return `${detail.acreage.toFixed(2)} acres`;
  }
  return undefined;
};

const formatDate = (value?: string) => {
  if (!value) return undefined;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleDateString();
};

export const MarketMap = ({
  market,
  className,
  onBack,
  onNextProperty,
  renderOverlay = true,
  propertyDetail,
}: MarketMapProps) => {
  const center: LatLngExpression = [market.location[0], market.location[1]];
  const intensity = Math.min(0.12 + (market.activeEntities / Math.max(market.entities, 1)) * 0.45, 0.65);
  const isParcel = Boolean(market.parcelId);
  const detail = isParcel ? propertyDetail : undefined;
  const lotSizeDisplay = formatLotSize(detail);
  const formattedValue = formatCurrency(detail?.marketValue);
  const formattedAssessed = formatCurrency(detail?.assessedValue);
  const formattedSalePrice = formatCurrency(detail?.lastSalePrice);
  const formattedSaleDate = formatDate(detail?.lastSaleDate);

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
              <div className="text-xs uppercase tracking-[0.18em] text-[rgba(255,247,238,0.72)]">
                {isParcel ? 'Property detail' : 'Market focus'}
              </div>
              <h3 className="text-lg font-semibold tracking-[0.04em]">
                {detail?.address ?? market.label}
              </h3>
              {detail?.parcelId && (
                <p className="text-xs uppercase tracking-[0.14em] text-[rgba(255,247,238,0.65)]">
                  Parcel {detail.parcelId}
                </p>
              )}
            </div>
            {onNextProperty || onBack ? (
              <div className="flex flex-wrap items-center gap-2">
                {onNextProperty && (
                  <button
                    type="button"
                    onClick={onNextProperty}
                    className="rounded-full border border-[#f9cf64] bg-[#f9cf64] px-4 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-[#071623] transition-colors hover:border-[#ffd77c] hover:bg-[#ffd77c]"
                  >
                    Next property
                  </button>
                )}
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
            ) : null}
          </div>
          {isParcel && detail ? (
            <div className="mt-4 grid gap-3 text-sm leading-relaxed text-[rgba(255,247,238,0.86)]">
              <div className="flex flex-wrap items-center gap-3">
                {detail.propertyType && (
                  <span className="rounded-full bg-[rgba(249,207,100,0.18)] px-3 py-1 text-xs uppercase tracking-[0.12em] text-[#f9cf64]">
                    {detail.propertyType}
                  </span>
                )}
                {detail.zoning && (
                  <span className="rounded-full bg-[rgba(68,110,135,0.28)] px-3 py-1 text-xs uppercase tracking-[0.12em] text-[#c0d6e3]">
                    Zoning {detail.zoning}
                  </span>
                )}
                {formattedValue && (
                  <span className="rounded-full bg-[rgba(5,14,24,0.65)] px-3 py-1 text-xs uppercase tracking-[0.12em] text-[#ffefe2]">
                    Market {formattedValue}
                  </span>
                )}
              </div>
              <dl className="grid gap-2 text-xs uppercase tracking-[0.12em] text-[rgba(255,247,238,0.7)] sm:grid-cols-[auto,1fr] sm:gap-y-3">
                {lotSizeDisplay && (
                  <>
                    <dt className="font-semibold text-[rgba(255,247,238,0.9)]">Lot size</dt>
                    <dd className="sm:ml-3 normal-case text-[rgba(255,247,238,0.95)]">{lotSizeDisplay}</dd>
                  </>
                )}
                {detail.owner && (
                  <>
                    <dt className="font-semibold text-[rgba(255,247,238,0.9)]">Owner</dt>
                    <dd className="sm:ml-3 normal-case text-[rgba(255,247,238,0.95)]">
                      {detail.owner}
                      {detail.ownerType ? ` (${detail.ownerType.toUpperCase()})` : ''}
                    </dd>
                  </>
                )}
                {(formattedSalePrice || formattedSaleDate) && (
                  <>
                    <dt className="font-semibold text-[rgba(255,247,238,0.9)]">Last sale</dt>
                    <dd className="sm:ml-3 normal-case text-[rgba(255,247,238,0.95)]">
                      {formattedSalePrice ?? '—'}
                      {formattedSaleDate ? ` on ${formattedSaleDate}` : ''}
                    </dd>
                  </>
                )}
                {formattedAssessed && (
                  <>
                    <dt className="font-semibold text-[rgba(255,247,238,0.9)]">Assessed</dt>
                    <dd className="sm:ml-3 normal-case text-[rgba(255,247,238,0.95)]">{formattedAssessed}</dd>
                  </>
                )}
              </dl>
              {detail.aiSummary && (
                <p className="normal-case text-[rgba(255,247,238,0.86)]">{detail.aiSummary}</p>
              )}
              {detail.highlights && detail.highlights.length > 0 && (
                <ul className="list-disc space-y-1 pl-5 text-left normal-case text-[rgba(255,247,238,0.86)]">
                  {detail.highlights.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              )}
            </div>
          ) : (
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
          )}
        </div>
      )}
    </div>
  );
};
