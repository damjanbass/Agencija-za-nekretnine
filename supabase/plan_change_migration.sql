-- Dodaje kolonu za čuvanje prethodnog PayPal subscription ID-a tokom promene plana.
-- Webhook je koristi da automatski otkaže staru pretplatu kada nova se aktivira.
ALTER TABLE agencies ADD COLUMN IF NOT EXISTS previous_paypal_subscription_id TEXT;
