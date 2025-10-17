import { useEffect, useRef } from 'react';
import { geoOrthographic, geoPath } from 'd3-geo';
import countriesTopology from '../data/countries-50m.json';
import { feature } from 'topojson-client';

const WATER_COLOR = '#446e87';
const LAND_COLOR = '#fdf5ed';

export type StaticCanvasGlobeProps = {
  className?: string;
};

export const StaticCanvasGlobe = ({ className }: StaticCanvasGlobeProps) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const countries = feature(
      countriesTopology as any,
      (countriesTopology as any).objects.countries,
    ) as any;

    let animationFrame: number | null = null;
    let rotation = 0;

    const render = (angle: number) => {
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      const { clientWidth: w, clientHeight: h } = canvas;
      canvas.width = Math.max(1, Math.floor(w * dpr));
      canvas.height = Math.max(1, Math.floor(h * dpr));
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.scale(dpr, dpr);

      ctx.clearRect(0, 0, w, h);

      const size = Math.min(w, h);
      const radius = (size / 2) * 0.96;
      const centerX = w / 2;
      const centerY = h / 2;

      const projection = geoOrthographic()
        .rotate([angle, -18, 0])
        .translate([centerX, centerY])
        .scale(radius)
        .clipAngle(90);
      const path = geoPath(projection, ctx);

      // Draw water as a circle (sphere)
      ctx.beginPath();
      ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
      ctx.fillStyle = WATER_COLOR;
      ctx.fill();

      // Draw land polygons
      const countries = feature(
        countriesTopology as any,
        (countriesTopology as any).objects.countries,
      ) as any;

      ctx.fillStyle = LAND_COLOR;
      ctx.strokeStyle = 'rgba(5, 14, 24, 0.35)';
      ctx.lineWidth = 0.6;
      for (const f of countries.features as any[]) {
        ctx.beginPath();
        path(f);
        ctx.fill();
        ctx.stroke();
      }
    };

    const tick = () => {
      rotation = (rotation + 0.12) % 360;
      render(rotation);
      animationFrame = window.requestAnimationFrame(tick);
    };

    render(rotation);
    animationFrame = window.requestAnimationFrame(tick);

    const RO: typeof ResizeObserver | undefined = (globalThis as any).ResizeObserver;
    if (RO) {
      const ro = new RO(() => render(rotation));
      ro.observe(canvas);
      return () => {
        ro.disconnect();
        if (animationFrame) {
          window.cancelAnimationFrame(animationFrame);
        }
      };
    } else {
      const onResize = () => render(rotation);
      window.addEventListener('resize', onResize);
      return () => {
        window.removeEventListener('resize', onResize);
        if (animationFrame) {
          window.cancelAnimationFrame(animationFrame);
        }
      };
    }
  }, []);

  return (
    <div className={className} style={{ position: 'relative', width: '100%', height: '100%' }}>
      <canvas ref={canvasRef} style={{ width: '100%', height: '100%', display: 'block' }} />
    </div>
  );
};

export default StaticCanvasGlobe;
