import { NextRequest } from 'next/server';
import { PDFParse } from 'pdf-parse';
import { analyzePdfLayoutAndPixels } from '@/lib/gemini-vision';
import { chunkTextSemantically, syncChunkToSupabase } from '@/lib/crawler';

export const maxDuration = 60;
export const dynamic = 'force-dynamic';

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
      // Step 1: Nhận biết "điểm chữ" (text layer extraction)
      try {
        const parser = new PDFParse({ data: buffer });
        const parsed = await parser.getText();
        extractedText = typeof parsed === 'string' ? parsed : (parsed?.text || '');
        await parser.destroy();
      } catch (pdfErr: any) {
        console.warn(`[PDF Parse Layer Warning]: ${pdfErr.message}`);
      }

      // Step 2: Nhận biết "điểm ảnh" (layout analysis & multimodal OCR)
      const visionResult = await analyzePdfLayoutAndPixels(buffer, fileName, extractedText);
      extractedText = visionResult.structuredMarkdown;
      hasVisionOcr = visionResult.hasVisionOcr;
      pixelHighlights = visionResult.pixelHighlights;
    } else {
      // Text / Markdown / Plain Document
      extractedText = buffer.toString('utf-8');
      pixelHighlights = ['Bóc tách văn bản trực tiếp từ tệp văn bản/Markdown'];
    }

    // Step 3: Semantic Chunking
    const chunks = chunkTextSemantically(extractedText, {
      fileName: fileName,
      title: fileName,
    });

    const syncedChunks = [];
    if (instantRag) {
      // Step 4: Instant RAG
      for (const chunk of chunks) {
        const synced = await syncChunkToSupabase(chunk, {
          fileName: fileName,
          title: fileName,
          type: isPdf ? 'document_pdf' : 'document_text',
        });
        syncedChunks.push(synced);
      }
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
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}
