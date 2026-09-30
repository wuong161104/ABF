import { NextResponse } from 'next/server';
import { supabaseAdmin } from '@/lib/supabase';

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    // Count total documents in Supabase
    const { count, error: countError } = await supabaseAdmin
      .from('documents')
      .select('*', { count: 'exact', head: true });

    // Fetch 15 most recent records
    const { data: recentDocs, error: recentError } = await supabaseAdmin
      .from('documents')
      .select('id, content, metadata')
      .order('id', { ascending: false })
      .limit(15);

    if (countError || recentError) {
      throw countError || recentError;
    }

    return NextResponse.json({
      success: true,
      totalChunks: count || 0,
      recentRecords: recentDocs || [],
      supabaseUrl: process.env.NEXT_PUBLIC_SUPABASE_URL || 'https://azpvcqpnecljsosamnot.supabase.co',
      vectorDimensions: 3072,
    });
  } catch (err: any) {
    return NextResponse.json({
      success: false,
      totalChunks: 0,
      recentRecords: [],
      error: err.message,
    });
  }
}
