/**
 * Test script to manually trigger image migration for FT-16
 */

async function testMigration() {
  const response = await fetch('https://allied-feed-ops.vercel.app/api/publish/sku', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      master_sku: 'FT-16',
      platforms: ['google'],
      environment: 'staging',
    }),
  })

  const result = await response.json()
  console.log(JSON.stringify(result, null, 2))
}

testMigration().catch(console.error)
