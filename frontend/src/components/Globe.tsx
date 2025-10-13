import { useEffect, useRef } from 'react';
import type { COBEOptions } from 'cobe';
import { useMotionValue, useSpring } from 'framer-motion';

import { cn } from '../lib/cn';

const MOVEMENT_DAMPING = 1400;

// Extend config with an optional scale property supported by cobe at runtime
const DOMINION_GLOBE_CONFIG: COBEOptions & { scale?: number } = {
  width: 800,
  height: 800,
  onRender: () => {},
  devicePixelRatio: 2,
  // Make the sphere slightly smaller than the canvas so it never
  // touches the edges (prevents visual clipping at the top).
  scale: 0.88,
  phi: 1.1,
  theta: 0.35,
  dark: 0,
  diffuse: 0.4,
  mapSamples: 16000,
  mapBrightness: 1.2,
  baseColor: [68 / 255, 110 / 255, 135 / 255],
  markerColor: [5 / 255, 14 / 255, 24 / 255],
  glowColor: [255 / 255, 247 / 255, 238 / 255],
  markers: [
    { location: [29.6516, -82.3248], size: 0.18 }, // Gainesville, FL
    { location: [27.9506, -82.4572], size: 0.06 }, // Tampa, FL
    { location: [30.3322, -81.6557], size: 0.05 }, // Jacksonville, FL
    { location: [25.7617, -80.1918], size: 0.05 }, // Miami, FL
    { location: [28.5383, -81.3792], size: 0.04 }, // Orlando, FL
  ],
};

type GlobeProps = {
  className?: string;
  config?: Partial<COBEOptions & { scale?: number }>;
};

export const Globe = ({ className, config = {} }: GlobeProps) => {
  let phi = 0;
  let width = 0;
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const pointerInteracting = useRef<number | null>(null);

  const motionValue = useMotionValue(0);
  const motionSpring = useSpring(motionValue, {
    mass: 1,
    damping: 30,
    stiffness: 100,
  });

  const setPointerInteraction = (value: number | null) => {
    pointerInteracting.current = value;
    if (canvasRef.current) {
      canvasRef.current.style.cursor = value !== null ? 'grabbing' : 'grab';
    }
  };

  const updateMovement = (clientX: number) => {
    if (pointerInteracting.current !== null) {
      const delta = clientX - pointerInteracting.current;
      motionValue.set(motionValue.get() + delta / MOVEMENT_DAMPING);
      pointerInteracting.current = clientX;
    }
  };

  useEffect(() => {
    let destroyGlobe: (() => void) | undefined;

    const handleResize = () => {
      if (!canvasRef.current) return;
      const parent = canvasRef.current.parentElement as HTMLElement | null;
      const target = parent ?? canvasRef.current;
      const rect = target.getBoundingClientRect();
      // Use the smaller dimension to keep the render square and
      // ensure the globe fits within the visible area.
      const dim = Math.floor(Math.min(rect.width, rect.height || rect.width));
      width = Math.max(dim, 1); // guard against 0 during initial layout
    };

    const targetEl = () => canvasRef.current?.parentElement ?? canvasRef.current;

    window.addEventListener('resize', handleResize);
    let resizeObserver: ResizeObserver | undefined;
    try {
      if (typeof ResizeObserver !== 'undefined') {
        resizeObserver = new ResizeObserver(() => handleResize());
        const el = targetEl();
        if (el) resizeObserver.observe(el);
      }
    } catch {}

    handleResize();

    const initGlobe = async () => {
      if (!canvasRef.current) {
        return;
      }

      const { default: createGlobe } = await import('cobe');
      const globe = createGlobe(canvasRef.current, {
        ...DOMINION_GLOBE_CONFIG,
        ...config,
        width: width * 2,
        height: width * 2,
        onRender: (state) => {
          if (pointerInteracting.current === null) {
            phi += 0.0045;
          }

          state.phi = phi + motionSpring.get();
          state.width = width * 2;
          state.height = width * 2;
        },
      });

      destroyGlobe = () => globe.destroy();

      requestAnimationFrame(() => {
        if (canvasRef.current) {
          canvasRef.current.style.opacity = '1';
        }
      });
    };

    initGlobe();

    return () => {
      destroyGlobe?.();
      window.removeEventListener('resize', handleResize);
      resizeObserver?.disconnect();
    };
  }, [config, motionSpring, motionValue]);

  return (
    <div className={cn('relative mx-auto aspect-square w-full', className)}>
      <canvas
        ref={canvasRef}
        className="size-full opacity-0 transition-opacity duration-500 [contain:layout_paint_size]"
        onPointerDown={(event) => setPointerInteraction(event.clientX)}
        onPointerUp={() => setPointerInteraction(null)}
        onPointerOut={() => setPointerInteraction(null)}
        onMouseMove={(event) => updateMovement(event.clientX)}
        onTouchMove={(event) => {
          if (event.touches[0]) {
            updateMovement(event.touches[0].clientX);
          }
        }}
      />
    </div>
  );
};
