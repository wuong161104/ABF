import { NextRequest } from 'next/server';
import { generateGeminiEmbedding } from '@/lib/embeddings';
import { supabaseAdmin } from '@/lib/supabase';

export const dynamic = 'force-dynamic';

export async function POST(req: NextRequest) {
  try {
    const { query, matchCount = 4 } = await req.json();

    if (!query || typeof query !== 'string') {
      return new Response(JSON.stringify({ error: 'Câu hỏi không hợp lệ' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    // 1. Generate query embedding (3072 dims)
    const queryEmbedding = await generateGeminiEmbedding(query);

    // 2. Query Supabase vector similarity
    const { data: matchedDocs, error } = await supabaseAdmin.rpc('match_documents', {
      query_embedding: queryEmbedding,
      match_count: matchCount,
    });

    if (error) {
      throw error;
    }

    // 3. Generate synthesized answer with Gemini 1.5 Flash using retrieved context
    const context = (matchedDocs || [])
      .map((d: any, i: number) => `[Tài liệu ${i + 1} - Nguồn: ${d.metadata?.source || d.metadata?.title || 'Kho tri thức'}]\n${d.content}`)
      .join('\n\n---\n\n');

    let answer = 'Không tìm thấy dữ liệu liên quan trong kho tri thức Supabase.';

    if (matchedDocs && matchedDocs.length > 0) {
      const apiKey = process.env.GEMINI_API_KEY;
      const prompt = `Bạn là trợ lý RAG chuyên nghiệp. Hãy trả lời câu hỏi của người dùng một cách chính xác, súc tích và mạch lạc DỰA TRÊN các đoạn tài liệu được cung cấp dưới đây. Nếu thông tin không có trong tài liệu, hãy thành thật thông báo.

TÀI LIỆU THAM KHẢO TỪ SUPABASE:
${context}

CÂU HỎI:
${query}`;

      try {
        const resp = await fetch(
          `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${apiKey}`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              contents: [{ parts: [{ text: prompt }] }],
              generationConfig: { temperature: 0.2, maxOutputTokens: 1024 },
            }),
          }
        );

        if (resp.ok) {
          const json = await resp.json();
          answer = json.candidates?.[0]?.content?.parts?.[0]?.text || answer;
        }
      } catch (geminiErr: any) {
        console.warn('[Gemini Answer Synthesis Warning]:', geminiErr.message);
        answer = 'Đã tìm thấy các tài liệu phù hợp trong vector store (xem danh sách bên dưới).';
      }
    }

    return new Response(
      JSON.stringify({
        success: true,
        query,
        answer,
        matchedChunks: matchedDocs || [],
      }),
      {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  } catch (err: any) {
    return new Response(JSON.stringify({ error: err.message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}
