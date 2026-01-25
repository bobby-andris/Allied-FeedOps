# Streamlit Cloud Deployment

## Quick Setup
1. Push this repo to GitHub.
2. Create a new app in Streamlit Cloud.
3. Set the main file to `streamlit_app.py`.
4. Deploy.

## Notes
- The demo data lives in `dashboard_data/lifestyle-eval`.
- The app uses `dashboard_data/catalog.csv` for original title/description and category/collection.
- Lifestyle images are stored alongside the patch JSONs, so the dashboard can load them
  without any external storage or network access.

## Updating the Demo Data
If you re-run a batch locally and want to refresh the demo dataset:
1. Recreate the `dashboard_data/lifestyle-eval` folder from your exports.
2. Re-run the sync helper (see `feedops.quality.data_loader.sync_lifestyle_images`).
3. Commit the updated `dashboard_data/` contents.
