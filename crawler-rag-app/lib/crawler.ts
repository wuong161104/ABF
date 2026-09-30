import * as cheerio from 'cheerio';
import { generateGeminiEmbedding } from './embeddings';
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
    const parsed = new URL(targetUrl);
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

export async function crawlSinglePage(url: string): Promise<ExtractedPage> {
  const resp = await fetch(url, {
    headers: {
      'User-Agent':
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 ABF-Crawler/2.0',
      Accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
      'Accept-Language': 'vi,en;q=0.9',
    },
    signal: AbortSignal.timeout(15000),
  });

  if (!resp.ok) {
    throw new Error(`HTTP Error ${resp.status} while fetching ${url}`);
  }

  const html = await resp.text();
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
