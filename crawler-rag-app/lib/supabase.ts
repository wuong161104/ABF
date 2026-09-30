import { createClient } from '@supabase/supabase-js';

// Strip any UTF-8 BOM (0xFEFF) or non-ASCII characters from Windows PowerShell pipes
const sanitize = (val: string | undefined, fallback: string = ''): string => {
  if (!val) return fallback;
  return val.replace(/^\uFEFF/, '').replace(/[^\x20-\x7E]/g, '').trim();
};

const supabaseUrl = sanitize(
  process.env.NEXT_PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL,
  'https://azpvcqpnecljsosamnot.supabase.co'
);

const supabaseAnonKey = sanitize(
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || process.env.SUPABASE_ANON_KEY,
  'sb_publishable_4JgOUmiY71dG8yOAcUoAiw_lMZL8d5r'
);

const supabaseServiceKey = sanitize(
  process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_KEY,
  supabaseAnonKey
);

// Client-side instance
export const supabase = createClient(supabaseUrl, supabaseAnonKey);

// Server-side admin instance (bypasses RLS for backend ingestion and pgvector inserts)
export const supabaseAdmin = createClient(supabaseUrl, supabaseServiceKey, {
  auth: {
    persistSession: false,
    autoRefreshToken: false,
  },
});
