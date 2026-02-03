# Task: Implement Settings Page API Health Checks

## Objective

Make the Settings page show real connectivity status for all integrated services instead of hardcoded "Active" badges.

## Current State

- Settings page exists at `dashboard/src/app/(dashboard)/settings/page.tsx`
- All badges show hardcoded "Active" status
- No actual API connectivity checks

## Files to Create/Modify

1. `dashboard/src/app/api/health/route.ts` - NEW health check endpoint
2. `dashboard/src/app/(dashboard)/settings/page.tsx` - Fetch and display real status
3. `dashboard/src/components/settings/ApiStatusCard.tsx` - NEW reusable component

## Requirements

### 1. Health Check API (`/api/health`)

Create an endpoint that tests connectivity to all services:

```typescript
GET /api/health?services=supabase,google-ads,google-analytics,shopify,gmc

Response:
{
  supabase: { status: 'connected', latency: 45 },
  googleAds: { status: 'connected', customerId: '6253381786' },
  googleAnalytics: { status: 'connected', propertyId: '...' },
  shopify: { status: 'connected', store: 'alliedbrass.myshopify.com' },
  gmc: { status: 'error', error: 'Invalid credentials' }
}
```

### 2. Service-Specific Health Checks

**Supabase**:

```typescript
const { data, error } = await supabase
  .from("sku_approvals")
  .select("count")
  .limit(1);
// If no error, connected
```

**Google Ads**:

```typescript
// Use google-ads-api to fetch account info
// If successful, return customer ID
```

**Google Analytics**:

```typescript
// Use googleapis with service account
// Make a simple metadata request
```

**Shopify**:

```typescript
// GraphQL query for shop info
query { shop { name } }
```

**Google Merchant Center**:

```typescript
// Test Google Sheets API access to the supplemental feed
// Or test Content API if we have those credentials
```

### 3. Update Settings Page

Convert to client component or use server actions:

```tsx
"use client";

export default function SettingsPage() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/health?services=all")
      .then((res) => res.json())
      .then(setHealth)
      .finally(() => setLoading(false));
  }, []);

  return (
    // ... existing layout
    <ApiStatusCard
      name="Supabase"
      status={health?.supabase.status}
      details={`Project: ${health?.supabase.projectId}`}
      loading={loading}
    />
  );
}
```

### 4. ApiStatusCard Component

Reusable component for showing API status:

```tsx
interface ApiStatusCardProps {
  name: string;
  icon: ReactNode;
  status: "connected" | "error" | "unknown";
  details?: string;
  error?: string;
  loading?: boolean;
  onRefresh?: () => void;
}
```

Features:

- Show loading spinner while checking
- Green badge for connected
- Red badge with error message for failed
- Gray badge for unknown/unchecked
- Optional refresh button to re-check
- Show latency if available

### 5. Refresh Functionality

Add a "Refresh All" button that re-runs all health checks:

```tsx
<Button onClick={refreshHealth}>
  <RefreshCw className="h-4 w-4 mr-2" />
  Refresh Status
</Button>
```

### 6. Danger Zone Actions (Stretch Goal)

Make the danger zone buttons functional:

**Clear All Approvals**:

- Confirmation modal
- Calls API to delete all `sku_approvals` and `variant_approvals`
- Requires typing "CONFIRM" to proceed

**Clear Performance Data**:

- Confirmation modal
- Clears `performance_snapshots` and `performance_baselines`

## Environment Variables Used

```
NEXT_PUBLIC_SUPABASE_URL
NEXT_PUBLIC_SUPABASE_ANON_KEY
GOOGLE_ADS_DEVELOPER_TOKEN
GOOGLE_ADS_CUSTOMER_ID
GOOGLE_SERVICE_ACCOUNT_KEY
SHOPIFY_STORE_URL
SHOPIFY_ACCESS_TOKEN
GMC_API_KEY
GOOGLE_SHEETS_SPREADSHEET_ID
```

## Success Criteria

1. Settings page shows real connectivity status on load
2. Each service shows appropriate status (connected/error)
3. Error messages are helpful and specific
4. Refresh button re-checks all services
5. No credentials are exposed in the UI
6. Works on Vercel deployment

## Security Notes

- Health check should not expose full credentials
- Only return safe metadata (customer IDs, store names, not tokens)
- Health endpoint should be protected by auth middleware
