# Streamlit Cloud Deployment

## Quick Setup

1. Push this repo to GitHub.
2. Create a new app in Streamlit Cloud.
3. Set the main file to `streamlit_app.py`.
4. Deploy.

## Notes

- The demo baseline lives in `dashboard_data/lifestyle-eval`.
- New runs write to `dashboard_data/lifestyle-eval-candidate` by default.
- The app uses `dashboard_data/catalog.csv` for original title/description and category/collection.
- Lifestyle images are stored alongside the patch JSONs, so the dashboard can load them
  without any external storage or network access.

## Updating the Demo Data

If you re-run a batch locally and want to refresh the demo dataset:

1. Run the batch so outputs land in `dashboard_data/lifestyle-eval-candidate`.
2. Copy `dashboard_data/lifestyle-eval-candidate` to `dashboard_data/lifestyle-eval` when you want to promote a run to the demo baseline.
3. Re-run the sync helper if needed (see `feedops.quality.data_loader.sync_lifestyle_images`).
4. Commit the updated `dashboard_data/` contents.
