-- Add jurisdiction field to permits table
-- This allows city and county to have overlapping permit numbers

-- 1. Add the jurisdiction column
ALTER TABLE permits ADD COLUMN IF NOT EXISTS jurisdiction VARCHAR(100);

-- 2. Update existing permits (all are from Gainesville city)
UPDATE permits SET jurisdiction = 'Gainesville' WHERE jurisdiction IS NULL;

-- 3. Drop the old unique constraint
ALTER TABLE permits DROP CONSTRAINT IF EXISTS permits_permit_number_key;

-- 4. Create new composite unique constraint
CREATE UNIQUE INDEX IF NOT EXISTS ix_permits_number_jurisdiction
    ON permits(permit_number, jurisdiction);

-- 5. Make jurisdiction NOT NULL after data migration
ALTER TABLE permits ALTER COLUMN jurisdiction SET NOT NULL;
