/**
 * Embedding Generator: Generates 3072-dimensional vector embeddings
 * Ưu tiên số 1: Vilao AI (OpenAI dg/text-embedding-3-large) - Tốc độ cao, không giới hạn quota
 * Dự phòng số 2: Google Gemini (models/gemini-embedding-001)
 */

const sanitize = (val: string | undefined, fallback: string = ''): string => {
  if (!val) return fallback;
  return val.replace(/^\uFEFF/, '').replace(/[^\x20-\x7E]/g, '').trim();
};

export async function generateEmbedding(text: string): Promise<number[]> {
  const cleanText = text.replace(/\s+/g, ' ').trim().slice(0, 7500);
  if (!cleanText) {
    throw new Error('Văn bản trống không thể tạo vector');
  }

  const vilaoUrl = sanitize(process.env.VILAO_BASE_URL, 'https://api.vilao.ai/v1').replace(/\/+$/, '');
  const vilaoKey = sanitize(process.env.VILAO_API_KEY || process.env.OPENAI_API_KEY, 'sk-2125a627679b5cadf195b535fa8abe19be75956839f868958bffe263a5612a25');
  const vilaoModel = sanitize(process.env.VILAO_EMBEDDING_MODEL, 'dg/text-embedding-3-large');

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
        signal: AbortSignal.timeout(8000),
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
  const geminiKey = sanitize(process.env.GEMINI_API_KEY);
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

export async function generateBatchEmbeddings(texts: string[]): Promise<number[][]> {
  if (!texts || texts.length === 0) return [];
  const cleanTexts = texts.map((t) => t.replace(/\s+/g, ' ').trim().slice(0, 7500)).filter(Boolean);
  if (cleanTexts.length === 0) return [];

  const vilaoUrl = sanitize(process.env.VILAO_BASE_URL, 'https://api.vilao.ai/v1').replace(/\/+$/, '');
  const vilaoKey = sanitize(process.env.VILAO_API_KEY || process.env.OPENAI_API_KEY, 'sk-2125a627679b5cadf195b535fa8abe19be75956839f868958bffe263a5612a25');
  const vilaoModel = sanitize(process.env.VILAO_EMBEDDING_MODEL, 'dg/text-embedding-3-large');

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
          input: cleanTexts,
        }),
        signal: AbortSignal.timeout(10000),
      });

      if (resp.ok) {
        const json = await resp.json();
        if (Array.isArray(json.data) && json.data.length === cleanTexts.length) {
          return json.data.map((item: any) => item.embedding);
        }
      }
    } catch (err: any) {
      console.warn(`[Vilao AI Batch Embedding Error]: ${err.message}, falling back to single items`);
    }
  }

  // Fallback: sequential single generation
  const results: number[][] = [];
  for (const text of cleanTexts) {
    results.push(await generateEmbedding(text));
  }
  return results;
}

export const generateGeminiEmbedding = generateEmbedding;
