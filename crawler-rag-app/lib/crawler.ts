import * as cheerio from 'cheerio';
import { generateGeminiEmbedding, generateBatchEmbeddings } from './embeddings';
import { supabaseAdmin } from './supabase';
import { CrawledChunk } from './types';

// Excluded social & non-content domains (from deep_web_crawler.py)
const EXCLUDED_DOMAINS = [
  'facebook.com',
  'fb.com',
  'zalo.me',
  'tiktok.com',
  'youtube.com',
  'youtu.be',
  'instagram.com',
  'twitter.com',
  'x.com',
  'linkedin.com',
  't.me',
];

export function cleanVietnameseText(text: string): string {
  if (!text) return '';
  return text
    .replace(/\r\n/g, '\n')
    .replace(/[ \t]+/g, ' ')
    .replace(/\n\s*\n+/g, '\n\n')
    .trim();
}

export function isInternalUrl(targetUrl: string, baseDomain: string): boolean {
  try {
    if (!targetUrl || typeof targetUrl !== 'string') return false;
    // Exclude unrendered JavaScript templates & action schemes
    if (
      targetUrl.includes('{{') ||
      targetUrl.includes('}}') ||
      targetUrl.includes('%7B') ||
      targetUrl.includes('%7D') ||
      targetUrl.startsWith('javascript:') ||
      targetUrl.startsWith('mailto:') ||
      targetUrl.startsWith('tel:')
    ) {
      return false;
    }
    const parsed = new URL(targetUrl);
    // Exclude static assets & binaries
    if (/\.(pdf|jpg|jpeg|png|gif|svg|webp|ico|css|js|zip|rar|tar|gz|mp4|mp3|exe|docx?|xlsx?)$/i.test(parsed.pathname)) {
      return false;
    }
    for (const ex of EXCLUDED_DOMAINS) {
      if (parsed.hostname.includes(ex)) return false;
    }
    return parsed.hostname === baseDomain || parsed.hostname.endsWith(`.${baseDomain}`);
  } catch {
    return false;
  }
}

export interface ExtractedPage {
  url: string;
  title: string;
  headings: { level: number; text: string }[];
  paragraphs: string[];
  tables: string[];
  images: { src: string; alt: string }[];
  sublinks: string[];
  markdown: string;
}

/**
 * Phase 1 Universal Link Discovery (Sitemap + Robots.txt)
 * Tương thích 100% với logic Phase 1 của abf_project/deep_web_crawler.py
 * Quét vét cạn sitemap index, products, news, categories.
 */
export async function fetchSitemapUrls(
  targetUrl: string,
  onLog?: (msg: string, type?: 'info' | 'success' | 'warn') => void
): Promise<string[]> {
  const urlsFound: string[] = [];
  const visitedSitemaps = new Set<string>();

  let parsed: URL;
  try {
    parsed = new URL(targetUrl);
  } catch {
    return [];
  }

  const origin = parsed.origin;
  const baseDomain = parsed.hostname;

  const sitemapCandidates = [
    `${origin}/robots.txt`,
    `${origin}/sitemap.xml`,
    `${origin}/sitemap_index.xml`,
    `${origin}/sitemap-index.xml`,
    `${origin}/sitemap/sitemap.xml`,
    `${origin}/SiteMap/sitemap.xml`,
  ];

  // 1. Kiểm tra robots.txt để tìm sitemap links chính thức
  try {
    const robotsRes = await fetch(`${origin}/robots.txt`, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
      },
      signal: AbortSignal.timeout(8000),
    });

    if (robotsRes.ok) {
      const robotsTxt = await robotsRes.text();
      for (const line of robotsTxt.split(/\r?\n/)) {
        if (line.trim().toLowerCase().startsWith('sitemap:')) {
          const smUrl = line.split(/:\s*/)[1]?.trim();
          if (smUrl && !sitemapCandidates.includes(smUrl)) {
            sitemapCandidates.unshift(smUrl);
          }
        }
      }
    }
  } catch {
    // Ignore robots.txt error
  }

  // 2. Duyệt qua hàng đợi sitemap (hỗ trợ cả sitemap lồng nhau sitemapindex)
  const queue = [...sitemapCandidates];
  const MAX_SITEMAPS_TO_CRAWL = 20;

  while (queue.length > 0 && visitedSitemaps.size < MAX_SITEMAPS_TO_CRAWL) {
    const smUrl = queue.shift()!;
    if (visitedSitemaps.has(smUrl)) continue;
    visitedSitemaps.add(smUrl);

    if (smUrl.endsWith('robots.txt')) continue;

    try {
      const res = await fetch(smUrl, {
        headers: {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
          Accept: 'application/xml, text/xml, */*',
        },
        signal: AbortSignal.timeout(10000),
      });

      if (!res.ok) continue;
      const xmlText = await res.text();
      if (!xmlText.trim()) continue;

      const locMatches = Array.from(xmlText.matchAll(/<loc>(.*?)<\/loc>/gi)).map((m) => m[1].trim());
      if (locMatches.length === 0) continue;

      if (onLog) {
        onLog(`-> Đọc thành công Sitemap '${smUrl}': phát hiện ${locMatches.length} liên kết / mục con.`, 'info');
      }

      for (const loc of locMatches) {
        if (!loc) continue;
        const cleanLoc = loc.trim();
        // Nếu là sitemap con
        if (
          cleanLoc.endsWith('.xml') ||
          (cleanLoc.toLowerCase().includes('sitemap') && !cleanLoc.endsWith('.html') && !cleanLoc.endsWith('.htm'))
        ) {
          if (!visitedSitemaps.has(cleanLoc) && !queue.includes(cleanLoc)) {
            queue.push(cleanLoc);
          }
        } else {
          if (isInternalUrl(cleanLoc, baseDomain)) {
            urlsFound.push(cleanLoc);
          }
        }
      }
    } catch {
      // Bỏ qua lỗi sitemap lẻ
    }
  }

  const uniqueUrls = Array.from(new Set(urlsFound));
  if (uniqueUrls.length > 0 && onLog) {
    onLog(`✨ Tìm thấy tổng cộng ${uniqueUrls.length} URL từ Sitemap chính thức của website!`, 'success');
  }
  return uniqueUrls;
}

export async function crawlSinglePage(url: string): Promise<ExtractedPage> {
  const browserHeaders = {
    'User-Agent':
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    Accept:
      'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
    'Sec-Ch-Ua': '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
    'Sec-Ch-Ua-Mobile': '?0',
    'Sec-Ch-Ua-Platform': '"Windows"',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1',
  };

  let html = '';
  let usedFallback = false;

  try {
    const resp = await fetch(url, {
      headers: browserHeaders,
      signal: AbortSignal.timeout(12000),
    });

    if (resp.ok) {
      html = await resp.text();
      // Check if this is a Client-Side Rendered (SPA) page or contains unrendered dynamic templates
      const hasSpaTemplates =
        html.includes('{{') ||
        html.includes('ng-app') ||
        html.includes('v-bind') ||
        html.includes('id="__next"') ||
        html.includes('id="root"') ||
        html.includes('<app-root');

      if (hasSpaTemplates && (html.includes('{{x.') || html.includes('{{') || html.length < 5000)) {
        console.warn(`[SPA/Dynamic Page Detected]: Kích hoạt Headless Jina Renderer cho ${url}`);
        usedFallback = true;
      }
    } else {
      console.warn(`[Crawler Direct Fetch Failed ${resp.status}]: Kích hoạt Jina Fallback cho ${url}`);
      usedFallback = true;
    }
  } catch (directErr: any) {
    console.warn(`[Crawler Direct Fetch Exception]: ${directErr.message}. Kích hoạt Jina Fallback...`);
    usedFallback = true;
  }

  // Fallback qua Jina Reader proxy nếu trang web bật Akamai / WAF chặn IP Cloud
  if (usedFallback) {
    try {
      const jinaResp = await fetch(`https://r.jina.ai/${url}`, {
        headers: {
          Accept: 'text/plain',
          'X-No-Cache': 'true',
        },
        signal: AbortSignal.timeout(20000),
      });

      if (!jinaResp.ok) {
        throw new Error(`Jina Reader HTTP ${jinaResp.status}`);
      }

      const jinaMd = await jinaResp.text();
      return parseJinaMarkdown(url, jinaMd);
    } catch (fallbackErr: any) {
      throw new Error(`Không thể cào trang web (WAF/Cloudflare chặn và Fallback thất bại): ${fallbackErr.message}`);
    }
  }

  const $ = cheerio.load(html);

  // Remove noisy elements
  $('script, style, noscript, iframe, svg, nav.ad, .cookie-banner, .advertisement').remove();

  const title = $('title').text().trim() || $('h1').first().text().trim() || url;
  const parsedOrigin = new URL(url);
  const baseDomain = parsedOrigin.hostname;

  // Extract headings
  const headings: { level: number; text: string }[] = [];
  $('h1, h2, h3, h4, h5, h6').each((_, el) => {
    const text = $(el).text().trim();
    if (text.length > 2 && text.length < 200) {
      const level = parseInt(el.tagName.replace('h', '')) || 2;
      headings.push({ level, text });
    }
  });

  // Extract tables
  const tables: string[] = [];
  $('table').each((_, tbl) => {
    const rows: string[] = [];
    $(tbl).find('tr').each((_, tr) => {
      const cols: string[] = [];
      $(tr).find('th, td').each((_, td) => {
        cols.push($(td).text().trim().replace(/\|/g, '-'));
      });
      if (cols.length > 0) {
        rows.push(`| ${cols.join(' | ')} |`);
      }
    });
    if (rows.length > 1) {
      // Create markdown table
      const headerSep = `| ${rows[0].split('|').filter(Boolean).map(() => '---').join(' | ')} |`;
      const mdTable = [rows[0], headerSep, ...rows.slice(1)].join('\n');
      tables.push(mdTable);
    }
  });

  // Extract clean paragraphs
  const paragraphs: string[] = [];
  $('p, article, section, .content, .detail').find('p, li').each((_, el) => {
    const text = cleanVietnameseText($(el).text());
    if (text.length > 30 && !paragraphs.includes(text)) {
      paragraphs.push(text);
    }
  });

  // Extract images
  const images: { src: string; alt: string }[] = [];
  $('img').each((_, el) => {
    const src = $(el).attr('src') || $(el).attr('data-src');
    const alt = $(el).attr('alt')?.trim() || '';
    if (src && !src.includes('data:image')) {
      const fullSrc = src.startsWith('http') ? src : new URL(src, url).href;
      images.push({ src: fullSrc, alt });
    }
  });

  // Extract sublinks
  const sublinks: string[] = [];
  $('a[href]').each((_, el) => {
    const href = $(el).attr('href')?.trim();
    if (href && !href.startsWith('#') && !href.startsWith('javascript:')) {
      try {
        const absolute = new URL(href, url).href;
        if (isInternalUrl(absolute, baseDomain) && !sublinks.includes(absolute)) {
          sublinks.push(absolute);
        }
      } catch {
        // invalid URL
      }
    }
  });

  // Build markdown structure
  let md = `# ${title}\n\nNguồn: ${url}\n\n---\n\n`;
  if (headings.length > 0) {
    md += `## Mục lục cấu trúc trang\n` + headings.map((h) => `${'  '.repeat(h.level - 1)}- ${h.text}`).join('\n') + '\n\n';
  }
  if (tables.length > 0) {
    md += `### Bảng biểu & Biểu phí trích xuất:\n\n` + tables.join('\n\n') + '\n\n';
  }
  md += paragraphs.join('\n\n');

  // Nếu Cheerio bóc tách được quá ít nội dung (< 3 đoạn văn hoặc < 3 headings), trang có thể là SPA cần chạy JavaScript
  if (paragraphs.length < 3 && headings.length < 3) {
    try {
      console.warn(`[Thin Content Detected (${paragraphs.length} paragraphs)]: Kích hoạt Jina Headless cho ${url}`);
      const jinaResp = await fetch(`https://r.jina.ai/${url}`, {
        headers: {
          Accept: 'text/plain',
          'X-No-Cache': 'true',
        },
        signal: AbortSignal.timeout(20000),
      });

      if (jinaResp.ok) {
        const jinaMd = await jinaResp.text();
        const jinaPage = parseJinaMarkdown(url, jinaMd);
        if (jinaPage.paragraphs.length > paragraphs.length || jinaPage.sublinks.length > sublinks.length) {
          return jinaPage;
        }
      }
    } catch {
      // Giữ kết quả cheerio nếu Jina không khả dụng
    }
  }

  return {
    url,
    title,
    headings,
    paragraphs,
    tables,
    images: images.slice(0, 20),
    sublinks: sublinks.slice(0, 50),
    markdown: cleanVietnameseText(md),
  };
}

/**
 * Parser cho nội dung Markdown thu về từ Jina Reader fallback (vượt WAF/Cloudflare)
 */
export function parseJinaMarkdown(url: string, rawMd: string): ExtractedPage {
  const parsedOrigin = new URL(url);
  const baseDomain = parsedOrigin.hostname;

  // 1. Title
  const titleMatch = rawMd.match(/^Title:\s*(.+)$/m) || rawMd.match(/^#\s*(.+)$/m);
  const title = titleMatch ? titleMatch[1].trim() : parsedOrigin.hostname;

  // 2. Headings
  const headings: { level: number; text: string }[] = [];
  const headingMatches = Array.from(rawMd.matchAll(/^(#{1,6})\s+(.+)$/gm));
  for (const match of headingMatches) {
    const level = match[1].length;
    const text = match[2].trim();
    if (text.length > 2 && text.length < 200) {
      headings.push({ level, text });
    }
  }

  // 3. Tables (Markdown tables)
  const tables: string[] = [];
  const tableMatches = rawMd.match(/(\|.+?\|\n\|[-:\s|]+?\|\n(?:\|.+?\|\n?)+)/g);
  if (tableMatches) {
    for (const tbl of tableMatches) {
      if (tbl.split('\n').length >= 3) {
        tables.push(tbl.trim());
      }
    }
  }

  // 4. Sublinks
  const sublinks: string[] = [];
  const linkMatches = Array.from(rawMd.matchAll(/\[(?:[^\]]*)\]\((https?:\/\/[^\s\)]+)\)/g));
  for (const lm of linkMatches) {
    const href = lm[1].trim();
    if (isInternalUrl(href, baseDomain) && !sublinks.includes(href)) {
      sublinks.push(href);
    }
  }

  // 5. Clean Paragraphs
  const paragraphs: string[] = [];
  const lines = rawMd.split('\n\n');
  for (const block of lines) {
    const cleaned = cleanVietnameseText(block);
    if (
      cleaned.length > 40 &&
      !cleaned.startsWith('#') &&
      !cleaned.startsWith('|') &&
      !cleaned.startsWith('Title:') &&
      !cleaned.startsWith('URL Source:') &&
      !cleaned.startsWith('Markdown Content:')
    ) {
      paragraphs.push(cleaned);
    }
  }

  return {
    url,
    title,
    headings,
    paragraphs,
    tables,
    images: [],
    sublinks: sublinks.slice(0, 50),
    markdown: cleanVietnameseText(rawMd),
  };
}

/**
 * Semantic Chunker: Chia văn bản thành các khối 800 - 1000 ký tự với overlap 150
 * và gắn kèm context heading để tăng độ chính xác của RAG.
 */
export function chunkTextSemantically(
  text: string,
  metadata: { url?: string; title?: string; fileName?: string }
): Array<{ heading: string; content: string }> {
  const chunks: Array<{ heading: string; content: string }> = [];
  const lines = text.split('\n');
  let currentHeading = metadata.title || 'Nội dung chung';
  let buffer = '';

  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith('#')) {
      currentHeading = trimmed.replace(/^#+\s*/, '');
    }

    if ((buffer + '\n' + trimmed).length > 900) {
      if (buffer.trim().length > 50) {
        chunks.push({
          heading: currentHeading,
          content: buffer.trim(),
        });
      }
      // Overlap: keep last 150 chars
      buffer = buffer.slice(-150) + '\n' + trimmed;
    } else {
      buffer += '\n' + trimmed;
    }
  }

  if (buffer.trim().length > 50) {
    chunks.push({
      heading: currentHeading,
      content: buffer.trim(),
    });
  }

  return chunks;
}

/**
 * Instant RAG Syncer: Nhận 1 chunk, sinh vector embedding 3072 chiều,
 * và upsert ngay lập tức vào bảng public.documents trên Supabase.
 */
export async function syncChunkToSupabase(
  chunk: { heading: string; content: string },
  sourceMeta: { url?: string; title?: string; fileName?: string; type: string }
): Promise<CrawledChunk> {
  const startTime = new Date().toISOString();
  try {
    const fullContent = `[${sourceMeta.title || sourceMeta.fileName || 'Tài liệu'}] - ${chunk.heading}\n${chunk.content}`;
    const embedding = await generateGeminiEmbedding(fullContent);

    const { data, error } = await supabaseAdmin
      .from('documents')
      .insert({
        content: fullContent,
        metadata: {
          source: sourceMeta.url || sourceMeta.fileName,
          title: sourceMeta.title || sourceMeta.fileName,
          heading: chunk.heading,
          type: sourceMeta.type,
          created_at: startTime,
          token_count: Math.ceil(fullContent.length / 4),
        },
        embedding: embedding,
      })
      .select('id')
      .single();

    if (error) {
      throw error;
    }

    return {
      id: String(data?.id || Math.random().toString(36).substring(7)),
      sourceUrl: sourceMeta.url,
      fileName: sourceMeta.fileName,
      heading: chunk.heading,
      content: chunk.content,
      tokenEstimate: Math.ceil(fullContent.length / 4),
      embeddingId: data?.id,
      status: 'synced',
      timestamp: new Date().toLocaleTimeString('vi-VN'),
    };
  } catch (err: any) {
    console.error('[Supabase Instant RAG Error]:', err.message);
    return {
      id: Math.random().toString(36).substring(7),
      sourceUrl: sourceMeta.url,
      fileName: sourceMeta.fileName,
      heading: chunk.heading,
      content: chunk.content,
      tokenEstimate: Math.ceil(chunk.content.length / 4),
      status: 'failed',
      timestamp: new Date().toLocaleTimeString('vi-VN'),
    };
  }
}

/**
 * Batch RAG Syncer: Vectorize theo batch 10 chunks qua Vilao AI (3072D)
 * và bulk insert vào Supabase pgvector với hiệu năng cao gấp 10 lần.
 */
export async function syncChunksBatchToSupabase(
  items: Array<{
    heading: string;
    content: string;
    url?: string;
    title?: string;
    fileName?: string;
    type: string;
  }>,
  onProgress?: (synced: CrawledChunk, current: number, total: number) => void
): Promise<CrawledChunk[]> {
  const results: CrawledChunk[] = [];
  const BATCH_SIZE = 10;

  for (let i = 0; i < items.length; i += BATCH_SIZE) {
    const batch = items.slice(i, i + BATCH_SIZE);
    const fullContents = batch.map(
      (item) => `[${item.title || item.fileName || 'Tài liệu'}] - ${item.heading}\n${item.content}`
    );

    let embeddings: number[][] = [];
    try {
      embeddings = await generateBatchEmbeddings(fullContents);
    } catch {
      embeddings = [];
    }

    const insertRows = batch.map((item, idx) => ({
      content: fullContents[idx],
      metadata: {
        source: item.url || item.fileName,
        title: item.title || item.fileName,
        heading: item.heading,
        type: item.type,
        created_at: new Date().toISOString(),
        token_count: Math.ceil(fullContents[idx].length / 4),
      },
      embedding: embeddings[idx] || null,
    }));

    try {
      const { data, error } = await supabaseAdmin
        .from('documents')
        .insert(insertRows)
        .select('id');

      if (error) throw error;

      batch.forEach((item, idx) => {
        const rowId = data?.[idx]?.id ? String(data[idx].id) : Math.random().toString(36).substring(7);
        const syncedChunk: CrawledChunk = {
          id: rowId,
          sourceUrl: item.url,
          fileName: item.fileName,
          heading: item.heading,
          content: item.content,
          tokenEstimate: Math.ceil(fullContents[idx].length / 4),
          embeddingId: Number(rowId),
          status: 'synced',
          timestamp: new Date().toLocaleTimeString('vi-VN'),
        };
        results.push(syncedChunk);
        if (onProgress) {
          onProgress(syncedChunk, results.length, items.length);
        }
      });
    } catch (err: any) {
      console.warn('[Supabase Batch Insert Fallback to Single]:', err.message);
      for (let j = 0; j < batch.length; j++) {
        const item = batch[j];
        const res = await syncChunkToSupabase(
          { heading: item.heading, content: item.content },
          { url: item.url, title: item.title, fileName: item.fileName, type: item.type }
        );
        results.push(res);
        if (onProgress) {
          onProgress(res, results.length, items.length);
        }
      }
    }
  }

  return results;
}
