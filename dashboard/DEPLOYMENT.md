# FeedOps Dashboard Deployment Guide

## Vercel Deployment

### Option 1: Vercel Git Integration (Recommended)

1. **Push the branch to GitHub:**

   ```bash
   git push -u origin feature/nextjs-dashboard
   ```

2. **Connect to Vercel:**

   - Go to [vercel.com/new](https://vercel.com/new)
   - Import the `Allied-FeedOps` repository
   - Configure the project:
     - **Root Directory:** `dashboard`
     - **Framework Preset:** Next.js (auto-detected)
     - **Build Command:** `npm run build`
     - **Output Directory:** `.next`

3. **Set Environment Variables:**

   - `NEXT_PUBLIC_SUPABASE_URL`: `https://qezuszwufortkiutlhym.supabase.co`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`: (from Supabase dashboard)
   - `SUPABASE_SERVICE_ROLE_KEY`: (from Supabase dashboard - keep secret!)

4. **Deploy:**
   - Click "Deploy"
   - Subsequent pushes to the branch will auto-deploy

### Option 2: Vercel CLI

1. **Install Vercel CLI:**

   ```bash
   npm install -g vercel
   ```

2. **Login to Vercel:**

   ```bash
   vercel login
   ```

3. **Deploy from dashboard directory:**

   ```bash
   cd dashboard
   vercel --prod
   ```

4. **Set environment variables:**
   ```bash
   vercel env add NEXT_PUBLIC_SUPABASE_URL
   vercel env add NEXT_PUBLIC_SUPABASE_ANON_KEY
   vercel env add SUPABASE_SERVICE_ROLE_KEY
   ```

## Environment Variables

| Variable                        | Required | Description                             |
| ------------------------------- | -------- | --------------------------------------- |
| `NEXT_PUBLIC_SUPABASE_URL`      | Yes      | Supabase project URL                    |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Yes      | Supabase anonymous key (public)         |
| `SUPABASE_SERVICE_ROLE_KEY`     | Yes      | Supabase service role key (server-only) |

## Post-Deployment Checklist

- [ ] Verify dashboard loads at Vercel URL
- [ ] Test Supabase connection (view Review Queue)
- [ ] Test API routes (/api/stats, /api/approvals)
- [ ] Verify all pages render correctly
- [ ] Test approval workflow

## Parallel Operation

The new Next.js dashboard runs alongside the existing Streamlit dashboard:

| Dashboard           | URL                                                   |
| ------------------- | ----------------------------------------------------- |
| Streamlit (current) | `allied-feedops-nqhv5z5vpypgcikbr8hhzy.streamlit.app` |
| Next.js (new)       | `feedops-dashboard.vercel.app` (or your custom URL)   |

Both dashboards connect to the same Supabase database, so data is synchronized.

## Troubleshooting

### Build Failures

Check build logs:

```bash
# Via Vercel CLI
vercel logs

# Via Vercel Dashboard
# Go to Deployments > Select deployment > View Logs
```

### Supabase Connection Issues

1. Verify environment variables are set correctly
2. Check Supabase project is not paused
3. Verify Row Level Security policies allow access

### API Route Errors

Check server-side logs in Vercel dashboard under Functions tab.
