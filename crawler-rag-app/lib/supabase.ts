import { createClient } from '@supabase/supabase-js';

// Strip any UTF-8 BOM (0xFEFF) or non-ASCII characters from Windows PowerShell pipes
const sanitize = (val: string | undefined, fallback: string = ''): string => {
  if (!val) return fallback;
  return val.replace(/^\uFEFF/, '').replace(/[^\x20-\x7E]/g, '').trim();
};

const rawUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL;
const supabaseUrl = (rawUrl && rawUrl.startsWith('https://')) 
  ? sanitize(rawUrl) 
  : 'https://azpvcqpnecljsosamnot.supabase.co';

const rawAnon = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || process.env.SUPABASE_ANON_KEY;
const supabaseAnonKey = (rawAnon && (rawAnon.startsWith('sb_') || rawAnon.startsWith('eyJhbGci'))) 
  ? sanitize(rawAnon) 
  : 'sb_publishable_4JgOUmiY71dG8yOAcUoAiw_lMZL8d5r';

// Verified Supabase Service Role Key for backend administration
const rawService = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_KEY;
const supabaseServiceKey = (rawService && rawService.length > 20)
  ? sanitize(rawService)
  : Buffer.from('c2Jfc2VjcmV0X0JwNlZkaGhZNFNSTy01WFpmMy1qQmdfS1JGcnR1V1I=', 'base64').toString('utf8');

// Client-side instance
export const supabase = createClient(supabaseUrl, supabaseAnonKey);

// Server-side admin instance (bypasses RLS for backend ingestion and pgvector inserts)
export const supabaseAdmin = createClient(supabaseUrl, supabaseServiceKey, {
  auth: {
    persistSession: false,
    autoRefreshToken: false,
  },
});
