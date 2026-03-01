#!/bin/bash
# Test single SKU publish to trigger migration

curl -X POST https://allied-feed-ops.vercel.app/api/publish/sku \
  -H "Content-Type: application/json" \
  -d '{
    "master_sku": "FT-16",
    "platforms": ["google"],
    "environment": "staging"
  }' | jq .
