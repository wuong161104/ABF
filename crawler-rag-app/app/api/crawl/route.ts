import { NextRequest } from 'next/server';
import { crawlSinglePage, fetchSitemapUrls, chunkTextSemantically, syncChunkToSupabase, syncChunksBatchToSupabase } from '@/lib/crawler';

export const maxDuration = 60; // Allow 60 seconds on Vercel Pro / Functions
export const dynamic = 'force-dynamic';

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { url, instantRag = true } = body;
    // Default: recursive crawl (up to 15 prioritized internal pages per execution to stay safely within Vercel limits)
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
            message: `Bắt đầu quét vét cạn liên kết: ${url}`,
          });

          sendEvent('pipeline_step', {
            stepId: 'fetch',
            status: 'processing',
            message: `Bắt đầu Phase 1: Quét vét cạn liên kết (Sitemap + DOM Menu)...`,
          });
          log('QUÉT LINK', `Bắt đầu Phase 1: Quét vét cạn toàn bộ liên kết (Sitemap + DOM Menu + Landing)...`, 'info');

          // 1. Quét Sitemap XML chính thức (như crawler trên GitHub Actions)
          const sitemapUrls = await fetchSitemapUrls(url, (msg, type) => {
            log('QUÉT LINK', msg, type || 'info');
          });

          // 2. Bóc tách DOM trang chính
          log('CRAWL', `Bắt đầu bóc tách DOM trang chính: ${url}`);
          const mainPage = await crawlSinglePage(url);
          log('CRAWL', `Đã bóc tách trang chính: "${mainPage.title}" (${mainPage.headings.length} headings, ${mainPage.tables.length} bảng biểu)`, 'success');

          // Hợp nhất URL từ Sitemap và DOM
          const allDiscoveredLinks = Array.from(new Set([...mainPage.sublinks, ...sitemapUrls]));
          log('SUCCESS', `Tổng kết Phase 1: Khám phá thành công ${allDiscoveredLinks.length} URLs trên toàn bộ website!`, 'success');

          sendEvent('pipeline_step', {
            stepId: 'fetch',
            status: 'completed',
            count: allDiscoveredLinks.length || 1,
            message: `Đã quét và bóc tách thành công ${allDiscoveredLinks.length} liên kết toàn bộ website (Sitemap + DOM)`,
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

          const startTime = Date.now();
          let totalSynced = 0;

          sendEvent('progress', {
            percent: 20,
            stage: 'chunking',
            message: 'Đang phân đoạn ngữ nghĩa Semantic Chunking trang chính...',
          });

          // 2. Chunking & RAG Sync trang chính ngay lập tức
          sendEvent('pipeline_step', {
            stepId: 'chunking',
            status: 'processing',
            message: 'Đang phân đoạn ngữ nghĩa (Semantic Chunking 900 chars / 150 overlap)...',
          });

          const mainChunks = chunkTextSemantically(mainPage.markdown, {
            url: mainPage.url,
            title: mainPage.title,
          });
          log('CHUNKER', `Trang chính tạo ${mainChunks.length} chunks ngữ cảnh tiêu đề`, 'success');

          if (instantRag && mainChunks.length > 0) {
            sendEvent('pipeline_step', {
              stepId: 'embedding',
              status: 'processing',
              message: `Đang Vectorize & Upsert ${mainChunks.length} chunks trang chính vào Supabase...`,
            });
            log('VILAO_AI', `Bắt đầu sinh Vector 3072D (dg/text-embedding-3-large) cho ${mainChunks.length} chunks trang chính...`, 'info');

            await syncChunksBatchToSupabase(
              mainChunks.map((c) => ({ ...c, url: mainPage.url, title: mainPage.title, type: 'web_page' })),
              (syncedChunk) => {
                totalSynced++;
                const headingText = syncedChunk.heading || 'Nội dung';
                sendEvent('progress', {
                  percent: 25,
                  stage: 'embedding',
                  current: totalSynced,
                  total: totalSynced,
                  message: `[Supabase] Đã nạp Chunk #${syncedChunk.id}: ${headingText.slice(0, 40)}...`,
                });
                log('SUPABASE', `[${totalSynced}] Synced chunk ID #${syncedChunk.id} [${headingText}] -> pgvector (3072D)`, 'success');
                sendEvent('chunk_synced', {
                  chunk: syncedChunk,
                  progress: { current: totalSynced, total: totalSynced },
                });
              }
            );
          }

          // 3. Recursive Subpages Crawl (Toàn bộ website)
          const PRODUCT_KEYWORDS = ['the-tin-dung', 'san-pham', 'card', 'ca-nhan', 'dich-vu', 'vay', 'tiet-kiem', 'uu-dai', 'bieu-phi', 'lai-suat', 'chi-tiet', 'detail'];
          const candidateLinks = allDiscoveredLinks.filter((l) => l !== mainPage.url && l !== url);
          const sortedSublinks = candidateLinks.sort((a, b) => {
            const scoreA = PRODUCT_KEYWORDS.reduce((acc, kw) => acc + (a.toLowerCase().includes(kw) ? 2 : 0), 0);
            const scoreB = PRODUCT_KEYWORDS.reduce((acc, kw) => acc + (b.toLowerCase().includes(kw) ? 2 : 0), 0);
            return scoreB - scoreA;
          });
          const sublinks = sortedSublinks.slice(0, maxSubpages);

          if (sublinks.length > 0) {
            log('RECURSIVE', `Tổng hợp ${allDiscoveredLinks.length} liên kết toàn site (Sitemap + DOM). Tiến hành bóc tách sâu ${sublinks.length} trang con nghiệp vụ trọng tâm...`, 'info');
            sendEvent('pipeline_step', {
              stepId: 'fetch',
              status: 'processing',
              count: 1 + sublinks.length,
              message: `Đang quét đệ quy toàn bộ ${sublinks.length} trang con nội bộ...`,
            });

            let subIndex = 0;
            for (const subUrl of sublinks) {
              // Time Guard: Giữ an toàn trong ngưỡng 46s của Vercel Serverless (ngăn ngắt kết nối đột ngột)
              if (Date.now() - startTime > 46000) {
                log('WARN', `Đã đạt giới hạn thời gian an toàn của Vercel (46s). Dừng quét thêm để hoàn tất đóng gói dữ liệu an toàn.`, 'warn');
                break;
              }

              subIndex++;
              const subPercent = 30 + Math.round((subIndex / sublinks.length) * 65);
              sendEvent('progress', {
                percent: subPercent,
                stage: 'subpages',
                message: `Đang cào & RAG trang con (${subIndex}/${sublinks.length}): ${subUrl.slice(0, 60)}...`,
              });

              try {
                const sub = await crawlSinglePage(subUrl);
                const scs = chunkTextSemantically(sub.markdown, {
                  url: sub.url,
                  title: sub.title,
                });
                log('CRAWL_SUB', `[${subIndex}/${sublinks.length}] Hoàn tất bóc tách: "${sub.title}" (${scs.length} chunks)`, 'info');

                // RAG trực tiếp ngay lập tức vào Supabase cho trang này
                if (instantRag && scs.length > 0) {
                  await syncChunksBatchToSupabase(
                    scs.map((c) => ({ ...c, url: sub.url, title: sub.title, type: 'web_page' })),
                    (syncedChunk) => {
                      totalSynced++;
                      const headingText = syncedChunk.heading || 'Nội dung';
                      sendEvent('progress', {
                        percent: subPercent,
                        stage: 'embedding',
                        current: totalSynced,
                        total: totalSynced,
                        message: `[Supabase] Đã nạp Chunk #${syncedChunk.id}: ${headingText.slice(0, 40)}...`,
                      });
                      log('SUPABASE', `[${totalSynced}] Synced chunk ID #${syncedChunk.id} [${headingText}] -> pgvector (3072D)`, 'success');
                      sendEvent('chunk_synced', {
                        chunk: syncedChunk,
                        progress: { current: totalSynced, total: totalSynced },
                      });
                    }
                  );
                }
              } catch (subErr: any) {
                log('WARN', `Bỏ qua link ${subUrl}: ${subErr.message}`, 'warn');
              }
            }

            sendEvent('pipeline_step', {
              stepId: 'fetch',
              status: 'completed',
              count: 1 + subIndex,
              message: `Đã cào và lưu trữ toàn bộ trang chính cùng ${subIndex} trang con liên kết`,
            });
          }

          sendEvent('pipeline_step', {
            stepId: 'chunking',
            status: 'completed',
            count: totalSynced,
            message: `Tổng cộng ${totalSynced} chunks ngữ nghĩa đã tạo`,
          });

          sendEvent('pipeline_step', {
            stepId: 'embedding',
            status: 'completed',
            count: totalSynced,
            message: `Hoàn tất embedding 3072D (Vilao AI) cho ${totalSynced} chunks`,
          });

          sendEvent('pipeline_step', {
            stepId: 'supabase',
            status: 'completed',
            count: totalSynced,
            message: `Đã đồng bộ trọn vẹn ${totalSynced} bản ghi vào public.documents trên Supabase`,
          });

          sendEvent('progress', {
            percent: 100,
            stage: 'finished',
            message: `Hoàn tất toàn bộ quy trình! Đã RAG thành công ${totalSynced} chunks vào Supabase.`,
          });
          log('FINISHED', `Toàn bộ quy trình hoàn tất 100%. Đã nạp tổng cộng ${totalSynced} chunks vào Supabase.`, 'success');

          sendEvent('finished', {
            success: true,
            title: mainPage.title,
            url: mainPage.url,
            totalChunks: totalSynced,
            sublinksCount: allDiscoveredLinks.length,
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
