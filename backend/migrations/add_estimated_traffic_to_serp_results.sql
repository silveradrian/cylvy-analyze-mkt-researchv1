-- Add estimated_traffic column to serp_results table
-- This column stores the estimated traffic for each SERP result based on position and search volume

ALTER TABLE serp_results
ADD COLUMN IF NOT EXISTS estimated_traffic NUMERIC DEFAULT 0;

-- Create index for performance
CREATE INDEX IF NOT EXISTS idx_serp_results_estimated_traffic ON serp_results(estimated_traffic);

-- Update existing records with estimated traffic based on CTR curves
-- Using standard CTR curves for organic search results
UPDATE serp_results sr
SET estimated_traffic = 
    CASE 
        WHEN sr.position = 1 THEN k.avg_monthly_searches * 0.35  -- 35% CTR for position 1
        WHEN sr.position = 2 THEN k.avg_monthly_searches * 0.16  -- 16% CTR for position 2
        WHEN sr.position = 3 THEN k.avg_monthly_searches * 0.10  -- 10% CTR for position 3
        WHEN sr.position = 4 THEN k.avg_monthly_searches * 0.07  -- 7% CTR for position 4
        WHEN sr.position = 5 THEN k.avg_monthly_searches * 0.05  -- 5% CTR for position 5
        WHEN sr.position = 6 THEN k.avg_monthly_searches * 0.04  -- 4% CTR for position 6
        WHEN sr.position = 7 THEN k.avg_monthly_searches * 0.03  -- 3% CTR for position 7
        WHEN sr.position = 8 THEN k.avg_monthly_searches * 0.025 -- 2.5% CTR for position 8
        WHEN sr.position = 9 THEN k.avg_monthly_searches * 0.02  -- 2% CTR for position 9
        WHEN sr.position = 10 THEN k.avg_monthly_searches * 0.015 -- 1.5% CTR for position 10
        WHEN sr.position > 10 AND sr.position <= 20 THEN k.avg_monthly_searches * 0.01 -- 1% CTR for positions 11-20
        ELSE 0
    END
FROM keywords k
WHERE sr.keyword_id = k.id
AND k.avg_monthly_searches IS NOT NULL
AND sr.estimated_traffic = 0;

