import { ComponentPropsWithoutRef } from 'react';
import { cn } from '../lib/cn';
import './Globe.css';
import GlobeCore from './GlobeCore';

export const Globe = ({ className, ...props }: ComponentPropsWithoutRef<typeof GlobeCore>) => {
  return (
    <div className="globe-shell">
      <GlobeCore className={cn('globe-core', className)} {...props} />
    </div>
  );
};
