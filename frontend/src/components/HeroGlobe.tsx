import { useEffect, useRef } from 'react';
import createGlobe from 'cobe';

type HeroGlobeProps = {
  className?: string;
};

export const HeroGlobe = ({ className }: HeroGlobeProps) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const phiRef = useRef(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = Math.min(1.5, window.devicePixelRatio || 1);
    const globe: any = createGlobe(canvas, {
      devicePixelRatio: dpr,
      width: canvas.offsetWidth * dpr,
      height: canvas.offsetHeight * dpr,
      phi: 0,
      theta: 0.2,
  // Visuals tuned to palette; cobe has limited color control
  dark: 0.7,
  diffuse: 1.1,
  mapSamples: 6000,
  mapBrightness: 7.2,
  baseColor: [68/255, 110/255, 135/255],
  markerColor: [249/255, 207/255, 100/255],
  glowColor: [27/255, 52/255, 68/255],
      markers: [],
      onRender: (state) => {
        phiRef.current += 0.005;
        state.phi = phiRef.current;
      },
    });

    const onResize = () => {
      const d = Math.min(1.5, window.devicePixelRatio || 1);
      globe.setProps?.({
        width: canvas.offsetWidth * d,
        height: canvas.offsetHeight * d,
        devicePixelRatio: d,
      });
    };
    const RO: typeof ResizeObserver | undefined = (globalThis as any).ResizeObserver;
    if (RO) {
      const ro = new RO(onResize);
      ro.observe(canvas);
      return () => {
        globe.destroy();
        ro.disconnect();
      };
    } else {
      window.addEventListener('resize', onResize);
      return () => {
        globe.destroy();
        window.removeEventListener('resize', onResize);
      };
    }
  }, []);

  return (
    <div className={className} style={{ position: 'relative', width: '100%', height: '100%' }}>
      <canvas ref={canvasRef} style={{ width: '100%', height: '100%' }} />
    </div>
  );
};

export default HeroGlobe;
