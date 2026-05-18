-- Omogući custom branding za Premium plan
UPDATE plans
SET custom_branding = true
WHERE id = 'premium';

-- Verifikacija
SELECT id, name, price_eur, custom_branding FROM plans ORDER BY price_eur;
