import { useMemo } from 'react';
import logo from '../assets/logo.svg';
import { cn } from '../lib/cn';
import './LoadingScreen.css';

const SEGMENT_COUNT = 28;

type LoadingScreenProps = {
  className?: string;
  title?: string;
  subtitle?: string;
  status?: string;
  detail?: string;
  progress: number;
  progressCaption?: string;
  accentLabel?: string;
};

export const LoadingScreen = ({
  className,
  title = 'Dominion Intelligence',
  subtitle = 'System handshake',
  status = 'Connecting to project graph',
  detail,
  progress,
  progressCaption = 'Synchronizing global feed',
  accentLabel = 'Dominion OS',
}: LoadingScreenProps) => {
  const clampedProgress = Math.min(100, Math.max(0, Math.round(progress)));

  const segments = useMemo(() => {
    const activeSegments = Math.round((clampedProgress / 100) * SEGMENT_COUNT);
    return Array.from({ length: SEGMENT_COUNT }, (_, index) => index < activeSegments);
  }, [clampedProgress]);

  const detailParts = useMemo(() => {
    if (!detail) {
      return null;
    }
    const lastSeparatorIndex = detail.lastIndexOf('·');
    if (lastSeparatorIndex === -1 || lastSeparatorIndex === detail.length - 1) {
      return { primary: detail, location: undefined };
    }
    return {
      primary: detail.slice(0, lastSeparatorIndex).trim(),
      location: detail.slice(lastSeparatorIndex + 1).trim(),
    };
  }, [detail]);

  return (
    <div className={cn('loading-screen', className)}>
      <div className="loading-screen__core">
        
        <header className="loading-screen__header">
          <span className="loading-screen__subtitle">{subtitle}</span>
          <h1 className="loading-screen__title">{title}</h1>
        </header>

        <div className="loading-screen__status">
          <p>{status}</p>
          {detailParts && (
            <p className="loading-screen__detail">
              {detailParts.location ? (
                <>
                  {detailParts.primary}
                  <br />
                  <span className="loading-screen__detail-location">{detailParts.location}</span>
                </>
              ) : (
                detailParts.primary
              )}
            </p>
          )}
        </div>

        <div className="loading-screen__progress">
          <div className="loading-screen__progress-value">
            <span>{clampedProgress}</span>
            <span className="loading-screen__progress-percent">%</span>
          </div>
          <div className="loading-screen__progress-meta">
            <span className="loading-screen__progress-accent">{accentLabel}</span>
            <span className="loading-screen__progress-caption">{progressCaption}</span>
          </div>
        </div>

        <div className="loading-screen__bar">
          {segments.map((isActive, index) => (
            <span
              key={index}
              className={cn('loading-screen__segment', isActive && 'loading-screen__segment--active')}
              aria-hidden="true"
            />
          ))}
        </div>
      </div>
    </div>
  );
};

export default LoadingScreen;
