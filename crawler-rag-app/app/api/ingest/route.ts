import { NextRequest } from 'next/server';
import zlib from 'zlib';
import { analyzePdfLayoutAndPixels } from '@/lib/gemini-vision';
import { chunkTextSemantically, syncChunksBatchToSupabase } from '@/lib/crawler';

export const maxDuration = 60;
export const dynamic = 'force-dynamic';

/**
 * Lightweight, zero-dependency native PDF stream text extractor
 * Safe for all Node.js / Vercel Serverless runtimes without Canvas or DOM globals.
 */
function extractPdfTextNative(buffer: Buffer): string {
  try {
    const content = buffer.toString('binary');
    const streamRegex = /stream[\r\n]+([\s\S]*?)[\r\n]+endstream/g;
    let text = '';
    let match;

    while ((match = streamRegex.exec(content)) !== null) {
      const rawStream = Buffer.from(match[1], 'binary');
      let uncompressed = '';
      try {
        uncompressed = zlib.inflateSync(rawStream).toString('utf-8');
      } catch {
        try {
          uncompressed = zlib.inflateRawSync(rawStream).toString('utf-8');
        } catch {
          uncompressed = rawStream.toString('latin1');
        }
      }

      // Extract text in parentheses (Tj / TJ operators in PDF syntax)
      const textMatches = uncompressed.match(/\((.*?)\)\s*Tj/g) || [];
      for (const tm of textMatches) {
        const clean = tm.replace(/^\(/, '').replace(/\)\s*Tj$/, '').trim();
        if (clean && clean.length > 1) {
          text += clean + ' ';
        }
      }

      // Also extract array text objects [(...)] TJ
      const arrayMatches = uncompressed.match(/\[(.*?)\]\s*TJ/g) || [];
      for (const am of arrayMatches) {
        const parts = am.match(/\((.*?)\)/g) || [];
        for (const p of parts) {
          const clean = p.replace(/^\(/, '').replace(/\)$/, '').trim();
          if (clean) text += clean + ' ';
        }
      }
    }

    return text.trim();
  } catch (err: any) {
    console.warn('[Native PDF Text Extractor]:', err.message);
    return '';
  }
}

export async function POST(req: NextRequest) {
  try {
    const formData = await req.formData();
    const file = formData.get('file') as File | null;
    const instantRag = formData.get('instantRag') !== 'false';

    if (!file) {
      return new Response(JSON.stringify({ error: 'Không tìm thấy file tải lên' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    const arrayBuffer = await file.arrayBuffer();
    const buffer = Buffer.from(arrayBuffer);
    const fileName = file.name;
    const isPdf = fileName.toLowerCase().endsWith('.pdf');

    let extractedText = '';
    let hasVisionOcr = false;
    let pixelHighlights: string[] = [];

    if (isPdf) {
      // 1. Native text layer extraction (pure Node.js, 0 dependencies)
      const nativeText = extractPdfTextNative(buffer);

      // 2. Multimodal Vision OCR (Gemini 1.5 Flash natively processes raw PDF bytes)
      try {
        const visionResult = await analyzePdfLayoutAndPixels(buffer, fileName, nativeText);
        if (visionResult.structuredMarkdown && visionResult.structuredMarkdown.trim().length > 50) {
          extractedText = visionResult.structuredMarkdown;
          hasVisionOcr = visionResult.hasVisionOcr;
          pixelHighlights = visionResult.pixelHighlights;
        } else {
          extractedText = nativeText || 'Tài liệu PDF không chứa văn bản thô.';
          pixelHighlights = ['Bóc tách văn bản trực tiếp từ tệp PDF'];
        }
      } catch (visionErr: any) {
        console.warn('[Vision OCR Warning]:', visionErr.message);
        extractedText = nativeText || 'Không thể bóc tách văn bản từ PDF.';
        pixelHighlights = ['Dự phòng: Bóc tách text layer trực tiếp'];
      }
    } else {
      // Plain text / Markdown document
      extractedText = buffer.toString('utf-8');
      pixelHighlights = ['Bóc tách văn bản trực tiếp từ tệp văn bản/Markdown'];
    }

    // 3. Semantic Chunking
    const chunks = chunkTextSemantically(extractedText, {
      fileName: fileName,
      title: fileName,
    });

    let syncedChunks: any[] = [];
    if (instantRag && chunks.length > 0) {
      // 4. Batch RAG Ingestion (10x faster via batch vectorization)
      syncedChunks = await syncChunksBatchToSupabase(
        chunks.map((c) => ({
          ...c,
          fileName,
          title: fileName,
          type: isPdf ? 'document_pdf' : 'document_text',
        }))
      );
    }

    return new Response(
      JSON.stringify({
        success: true,
        fileName: fileName,
        isPdf,
        hasVisionOcr,
        pixelHighlights,
        totalChunks: chunks.length,
        syncedCount: syncedChunks.length,
        chunks: syncedChunks,
      }),
      {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  } catch (error: any) {
    console.error('[Document Ingest Error]:', error);
    return new Response(JSON.stringify({ error: error.message || 'Lỗi xử lý tài liệu' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}
