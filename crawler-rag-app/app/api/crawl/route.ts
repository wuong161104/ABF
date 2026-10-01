import { NextRequest } from 'next/server';
import { crawlSinglePage, chunkTextSemantically, syncChunkToSupabase, syncChunksBatchToSupabase } from '@/lib/crawler';

export const maxDuration = 60; // Allow 60 seconds on Vercel Pro / Functions
export const dynamic = 'force-dynamic';

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { url, instantRag = true } = body;
    // Default: recursive full crawl (up to 15 internal pages per execution to stay safely within Vercel limits)
    const maxSubpages = typeof body.maxPages === 'number' && body.maxPages > 0 ? body.maxPages : 15;

    if (!url || !url.startsWith('http')) {
      return new Response(JSON.stringify({ error: 'URL không hợp lệ' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    // Set up a streaming response (ReadableStream)
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      async start(controller) {
        const sendEvent = (event: string, data: any) => {
          controller.enqueue(encoder.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`));
        };

        const log = (tag: string, message: string, type: 'info' | 'success' | 'warn' | 'error' = 'info') => {
          sendEvent('log', {
            timestamp: new Date().toLocaleTimeString('vi-VN'),
            tag,
            message,
            type,
          });
        };

        try {
          sendEvent('progress', {
            percent: 5,
            stage: 'ingestion',
            message: `Bắt đầu kết nối mục tiêu: ${url}`,
          });

          sendEvent('pipeline_step', {
            stepId: 'fetch',
            status: 'processing',
            message: `Đang kết nối và tải toàn bộ DOM: ${url}`,
          });
          log('CRAWL', `Bắt đầu phân tích trang chủ: ${url}`);

          // 1. Crawl main page
          const mainPage = await crawlSinglePage(url);
          log('CRAWL', `Đã bóc tách trang chính: "${mainPage.title}" (${mainPage.headings.length} headings, ${mainPage.tables.length} bảng biểu)`, 'success');

          sendEvent('pipeline_step', {
            stepId: 'fetch',
            status: 'completed',
            count: 1,
            message: `Đã trích xuất trang chính: "${mainPage.title}"`,
          });

          sendEvent('pipeline_step', {
            stepId: 'vision_ocr',
            status: 'completed',
            count: mainPage.tables.length,
            message: `Bóc tách cấu trúc HTML: ${mainPage.tables.length} bảng biểu & biểu phí đã chuẩn hóa`,
          });
          if (mainPage.tables.length > 0) {
            log('VISION_OCR', `Chuẩn hóa ${mainPage.tables.length} bảng biểu / biểu phí sang Markdown Table`, 'info');
          }

          sendEvent('progress', {
            percent: 25,
            stage: 'chunking',
            message: 'Đang phân đoạn ngữ nghĩa Semantic Chunking...',
          });

          // 2. Chunking main page
          sendEvent('pipeline_step', {
            stepId: 'chunking',
            status: 'processing',
            message: 'Đang phân đoạn ngữ nghĩa (Semantic Chunking 900 chars / 150 overlap)...',
          });

          const allChunks: Array<{ heading: string; content: string; url: string; title: string }> = [];
          const mainChunks = chunkTextSemantically(mainPage.markdown, {
            url: mainPage.url,
            title: mainPage.title,
          });
          mainChunks.forEach((c) => allChunks.push({ ...c, url: mainPage.url, title: mainPage.title }));
          log('CHUNKER', `Trang chính tạo ${mainChunks.length} chunks ngữ cảnh tiêu đề`, 'success');

          // 3. Recursive Subpages Crawl (Toàn bộ website)
          const PRODUCT_KEYWORDS = ['san-pham', 'the-tin-dung', 'card', 'ca-nhan', 'dich-vu', 'vay', 'tiet-kiem', 'uu-dai', 'bieu-phi', 'lai-suat', 'chi-tiet'];
          const sortedSublinks = [...mainPage.sublinks].sort((a, b) => {
            const scoreA = PRODUCT_KEYWORDS.reduce((acc, kw) => acc + (a.toLowerCase().includes(kw) ? 1 : 0), 0);
            const scoreB = PRODUCT_KEYWORDS.reduce((acc, kw) => acc + (b.toLowerCase().includes(kw) ? 1 : 0), 0);
            return scoreB - scoreA;
          });
          const sublinks = sortedSublinks.slice(0, maxSubpages);

          if (sublinks.length > 0) {
            log('RECURSIVE', `Phát hiện ${mainPage.sublinks.length} link nội bộ. Đã phân loại & tiến hành quét ${sublinks.length} trang con trọng tâm...`, 'info');
            sendEvent('pipeline_step', {
              stepId: 'fetch',
              status: 'processing',
              count: 1 + sublinks.length,
              message: `Đang quét đệ quy toàn bộ ${sublinks.length} trang con nội bộ...`,
            });

            let subIndex = 0;
            for (const subUrl of sublinks) {
              subIndex++;
              const subPercent = 25 + Math.round((subIndex / sublinks.length) * 15);
              sendEvent('progress', {
                percent: subPercent,
                stage: 'subpages',
                message: `Đang cào trang con (${subIndex}/${sublinks.length}): ${subUrl.slice(0, 60)}...`,
              });
              try {
                const sub = await crawlSinglePage(subUrl);
                const scs = chunkTextSemantically(sub.markdown, {
                  url: sub.url,
                  title: sub.title,
                });
                scs.forEach((c) => allChunks.push({ ...c, url: sub.url, title: sub.title }));
                log('CRAWL_SUB', `[${subIndex}/${sublinks.length}] Hoàn tất: "${sub.title}" (${scs.length} chunks)`, 'success');
              } catch (subErr: any) {
                log('WARN', `Bỏ qua link ${subUrl}: ${subErr.message}`, 'warn');
              }
            }

            sendEvent('pipeline_step', {
              stepId: 'fetch',
              status: 'completed',
              count: 1 + sublinks.length,
              message: `Đã cào toàn bộ trang chính và ${sublinks.length} trang con liên kết`,
            });
          }

          sendEvent('pipeline_step', {
            stepId: 'chunking',
            status: 'completed',
            count: allChunks.length,
            message: `Tổng cộng ${allChunks.length} chunks ngữ nghĩa toàn bộ website`,
          });
          log('CHUNKER', `Tổng hợp hoàn tất: ${allChunks.length} chunks sẵn sàng RAG`, 'success');

          // 4. Instant RAG: Batch Sync to Supabase via Vilao AI
          if (instantRag && allChunks.length > 0) {
            sendEvent('pipeline_step', {
              stepId: 'embedding',
              status: 'processing',
              message: 'Bắt đầu Instant RAG: Sinh vector 3072 dims qua Vilao AI & Upsert Supabase...',
            });
            log('VILAO_AI', `Bắt đầu sinh Vector 3072D (dg/text-embedding-3-large) siêu tốc theo Batch cho ${allChunks.length} chunks...`, 'info');

            const syncedChunks = await syncChunksBatchToSupabase(
              allChunks.map((item) => ({
                heading: item.heading,
                content: item.content,
                url: item.url,
                title: item.title,
                type: 'web_page',
              })),
              (syncedChunk, current, total) => {
                const ragPercent = 40 + Math.round((current / total) * 58);
                const headingText = syncedChunk.heading || 'Nội dung';
                sendEvent('progress', {
                  percent: ragPercent,
                  stage: 'embedding',
                  current,
                  total,
                  message: `Đang Vectorize & Upsert Supabase (${current}/${total}): ${headingText.slice(0, 45)}...`,
                });
                log('SUPABASE', `[${current}/${total}] Synced chunk ID #${syncedChunk.id} [${headingText}] -> pgvector (3072D)`, 'success');
                sendEvent('chunk_synced', {
                  chunk: syncedChunk,
                  progress: { current, total },
                });
              }
            );

            sendEvent('pipeline_step', {
              stepId: 'embedding',
              status: 'completed',
              count: syncedChunks.length,
              message: `Hoàn tất embedding 3072D (Vilao AI) cho ${syncedChunks.length} chunks`,
            });

            sendEvent('pipeline_step', {
              stepId: 'supabase',
              status: 'completed',
              count: syncedChunks.length,
              message: `Đã đồng bộ trọn vẹn ${syncedChunks.length} bản ghi vào public.documents trên Supabase`,
            });
          }

          sendEvent('progress', {
            percent: 100,
            stage: 'finished',
            message: `Hoàn tất toàn bộ quy trình! Đã RAG thành công ${allChunks.length} chunks vào Supabase.`,
          });
          log('FINISHED', `Toàn bộ quy trình hoàn tất 100%. Cơ sở tri thức Supabase đã sẵn sàng phục vụ RAG.`, 'success');

          sendEvent('finished', {
            success: true,
            title: mainPage.title,
            url: mainPage.url,
            totalChunks: allChunks.length,
            sublinksCount: mainPage.sublinks.length,
          });

          controller.close();
        } catch (err: any) {
          log('ERROR', `Lỗi dừng đột ngột: ${err.message}`, 'error');
          sendEvent('pipeline_step', {
            stepId: 'fetch',
            status: 'error',
            message: err.message,
          });
          sendEvent('progress', {
            percent: 100,
            stage: 'error',
            message: `Lỗi: ${err.message}`,
          });
          controller.close();
        }
      },
    });

    return new Response(stream, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        Connection: 'keep-alive',
      },
    });
  } catch (error: any) {
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}
