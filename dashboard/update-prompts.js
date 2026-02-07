const { createClient } = require('@supabase/supabase-js');
const fs = require('fs');

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseKey) {
  console.error('Missing Supabase credentials');
  process.exit(1);
}

const supabase = createClient(supabaseUrl, supabaseKey);
const goldStandard = JSON.parse(fs.readFileSync('/tmp/gold-standard.json', 'utf8'));

async function update() {
  const { data, error } = await supabase
    .from('prompt_templates')
    .update({ gold_standard_examples: goldStandard })
    .eq('is_active', true)
    .select('name, version');
  
  if (error) {
    console.error('Error:', error.message);
    process.exit(1);
  }
  
  console.log('Updated:', data);
}

update();
