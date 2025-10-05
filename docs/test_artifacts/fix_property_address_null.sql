-- Allow NULL property_address for parcels without street addresses (parks, conservation land, etc.)
ALTER TABLE bulk_property_records ALTER COLUMN property_address DROP NOT NULL;
