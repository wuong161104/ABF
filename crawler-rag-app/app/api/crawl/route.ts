import { NextRequest } from 'next/server';
import { crawlSinglePage, chunkTextSemantically, syncChunkToSupabase } from '@/lib/crawler';

export const maxDuration = 60; // Allow 60 seconds on Vercel Pro / Functions
export const dynamic = 'force-dynamic';

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { url, maxPages = 1, instantRag = true } = body;

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

        try {
          sendEvent('pipeline_step', {
            stepId: 'fetch',
            status: 'processing',
            message: `Đang kết nối và tải toàn bộ DOM: ${url}`,
          });

          // 1. Crawl main page
          const mainPage = await crawlSinglePage(url);

          sendEvent('pipeline_step', {
            stepId: 'fetch',
            status: 'completed',
            count: 1,
            message: `Đã trích xuất trang chính: "${mainPage.title}" (${mainPage.headings.length} headings, ${mainPage.tables.length} tables)`,
          });

          sendEvent('pipeline_step', {
            stepId: 'vision_ocr',
            status: 'completed',
            count: mainPage.tables.length,
            message: `Bóc tách cấu trúc HTML: ${mainPage.tables.length} bảng biểu & biểu phí đã chuẩn hóa`,
          });

          // 2. Chunking
          sendEvent('pipeline_step', {
            stepId: 'chunking',
            status: 'processing',
            message: 'Đang phân đoạn ngữ nghĩa (Semantic Chunking 900 chars / 150 overlap)...',
          });

          const chunks = chunkTextSemantically(mainPage.markdown, {
            url: mainPage.url,
            title: mainPage.title,
          });

          sendEvent('pipeline_step', {
            stepId: 'chunking',
            status: 'completed',
            count: chunks.length,
            message: `Tạo thành công ${chunks.length} chunks có ngữ cảnh tiêu đề`,
          });

          // 3. Instant RAG: Sync each chunk immediately to Supabase
          if (instantRag) {
            sendEvent('pipeline_step', {
              stepId: 'embedding',
              status: 'processing',
              message: 'Bắt đầu quá trình Instant RAG: Sinh vector 3072 dims & Upsert Supabase...',
            });

            let syncedCount = 0;
            for (let i = 0; i < chunks.length; i++) {
              const chunk = chunks[i];
              sendEvent('chunk_progress', {
                status: 'embedding',
                index: i + 1,
                total: chunks.length,
                heading: chunk.heading,
                preview: chunk.content.slice(0, 120),
              });

              const syncedChunk = await syncChunkToSupabase(chunk, {
                url: mainPage.url,
                title: mainPage.title,
                type: 'web_page',
              });

              syncedCount++;

              sendEvent('chunk_synced', {
                chunk: syncedChunk,
                progress: { current: syncedCount, total: chunks.length },
              });
            }

            sendEvent('pipeline_step', {
              stepId: 'embedding',
              status: 'completed',
              count: syncedCount,
              message: `Hoàn tất embedding 3072 chiều cho ${syncedCount} chunks`,
            });

            sendEvent('pipeline_step', {
              stepId: 'supabase',
              status: 'completed',
              count: syncedCount,
              message: `Đã đồng bộ trọn vẹn ${syncedCount} bản ghi vào public.documents trên Supabase`,
            });
          }

          // 4. Crawl subpages if requested (up to maxPages)
          if (maxPages > 1 && mainPage.sublinks.length > 0) {
            const subpagesToCrawl = mainPage.sublinks.slice(0, maxPages - 1);
            sendEvent('log', {
              message: `Tiến hành cào tiếp ${subpagesToCrawl.length} trang con nội bộ liên quan...`,
            });

            for (const subUrl of subpagesToCrawl) {
              try {
                const sub = await crawlSinglePage(subUrl);
                const subChunks = chunkTextSemantically(sub.markdown, {
                  url: sub.url,
                  title: sub.title,
                });

                if (instantRag) {
                  for (const sc of subChunks) {
                    const synced = await syncChunkToSupabase(sc, {
                      url: sub.url,
                      title: sub.title,
                      type: 'web_subpage',
                    });
                    sendEvent('chunk_synced', {
                      chunk: synced,
                      isSubpage: true,
                    });
                  }
                }
              } catch (subErr: any) {
                console.warn(`[Subpage Skip]: ${subUrl} - ${subErr.message}`);
              }
            }
          }

          sendEvent('finished', {
            success: true,
            title: mainPage.title,
            url: mainPage.url,
            totalImages: mainPage.images.length,
            sublinksCount: mainPage.sublinks.length,
          });

          controller.close();
        } catch (err: any) {
          sendEvent('pipeline_step', {
            stepId: 'fetch',
            status: 'error',
            message: err.message,
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
