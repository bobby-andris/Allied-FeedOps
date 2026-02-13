-- Create execute_sql RPC function for monitoring endpoints
-- Allows running read-only SELECT queries from API

CREATE OR REPLACE FUNCTION public.execute_sql(query text)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    result jsonb;
BEGIN
    -- Only allow SELECT queries for safety
    IF query !~* '^\s*SELECT' THEN
        RAISE EXCEPTION 'Only SELECT queries are allowed';
    END IF;

    -- Execute query and return as JSONB
    EXECUTE format('SELECT jsonb_agg(row_to_json(t)) FROM (%s) t', query) INTO result;

    RETURN COALESCE(result, '[]'::jsonb);
END;
$$;

-- Grant execute permission to authenticated users (anon role for API access)
GRANT EXECUTE ON FUNCTION public.execute_sql(text) TO anon;
GRANT EXECUTE ON FUNCTION public.execute_sql(text) TO authenticated;

COMMENT ON FUNCTION public.execute_sql(text) IS 'Execute read-only SELECT queries and return results as JSONB. Used by monitoring endpoints.';
