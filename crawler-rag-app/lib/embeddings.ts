/**
 * Embedding Generator: Generates 3072-dimensional vector embeddings
 * Ưu tiên số 1: Vilao AI (OpenAI dg/text-embedding-3-large) - Tốc độ cao, không giới hạn quota
 * Dự phòng số 2: Google Gemini (models/gemini-embedding-001)
 */

export async function generateEmbedding(text: string): Promise<number[]> {
  const cleanText = text.replace(/\s+/g, ' ').trim().slice(0, 7500);
  if (!cleanText) {
    throw new Error('Văn bản trống không thể tạo vector');
  }

  const vilaoUrl = (process.env.VILAO_BASE_URL || 'https://api.vilao.ai/v1').replace(/\/+$/, '');
  const vilaoKey = process.env.VILAO_API_KEY || process.env.OPENAI_API_KEY;
  const vilaoModel = process.env.VILAO_EMBEDDING_MODEL || 'dg/text-embedding-3-large';

  // 1. ƯU TIÊN SỐ 1: VILAO AI EMBEDDING (3072 dims)
  if (vilaoKey) {
    try {
      const resp = await fetch(`${vilaoUrl}/embeddings`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${vilaoKey}`,
        },
        body: JSON.stringify({
          model: vilaoModel,
          input: cleanText,
        }),
      });

      if (resp.ok) {
        const json = await resp.json();
        const vector = json.data?.[0]?.embedding;
        if (Array.isArray(vector) && vector.length === 3072) {
          return vector;
        }
      } else {
        const errText = await resp.text();
        console.warn(`[Vilao AI Embedding Warning]: ${resp.status} - ${errText.slice(0, 150)}`);
      }
    } catch (err: any) {
      console.warn(`[Vilao AI Connection Error]: ${err.message}`);
    }
  }

  // 2. DỰ PHÒNG SỐ 2: GOOGLE GEMINI EMBEDDING (3072 dims)
  const geminiKey = process.env.GEMINI_API_KEY;
  if (geminiKey) {
    try {
      const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key=${geminiKey}`;
      const gResp = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: 'models/gemini-embedding-001',
          content: { parts: [{ text: cleanText }] },
        }),
      });

      if (gResp.ok) {
        const gJson = await gResp.json();
        const gVector = gJson.embedding?.values;
        if (Array.isArray(gVector) && gVector.length === 3072) {
          return gVector;
        }
      }
    } catch (gErr: any) {
      console.warn(`[Gemini Fallback Error]: ${gErr.message}`);
    }
  }

  throw new Error('Không thể tạo vector embedding 3072 chiều từ Vilao AI hoặc Gemini. Vui lòng kiểm tra OPENAI_API_KEY / VILAO_API_KEY.');
}

// Giữ alias cho crawler và các route hiện tại
export const generateGeminiEmbedding = generateEmbedding;
