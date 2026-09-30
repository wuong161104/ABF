/**
 * Embedding Generator: Generates 3072-dimensional vector embeddings
 * Compatible with Supabase documents.embedding table.
 * All API keys are loaded strictly from environment variables.
 */

function getGeminiKeys(): string[] {
  const primary = process.env.GEMINI_API_KEY;
  const multi = process.env.GEMINI_API_KEYS;
  const keys: string[] = [];

  if (primary) keys.push(primary);
  if (multi) {
    keys.push(...multi.split(',').map((k) => k.trim()).filter(Boolean));
  }
  return keys.length > 0 ? keys : [''];
}

let keyIndex = 0;

function getNextKey(): string {
  const keys = getGeminiKeys();
  const key = keys[keyIndex % keys.length];
  keyIndex = (keyIndex + 1) % keys.length;
  return key;
}

export async function generateGeminiEmbedding(text: string, retries = 3): Promise<number[]> {
  const cleanText = text.replace(/\s+/g, ' ').trim().slice(0, 8000);
  if (!cleanText) {
    throw new Error('Text is empty for embedding');
  }

  for (let attempt = 0; attempt < retries; attempt++) {
    const apiKey = getNextKey();
    if (!apiKey) break;

    try {
      const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key=${apiKey}`;
      const resp = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: 'models/gemini-embedding-001',
          content: {
            parts: [{ text: cleanText }],
          },
        }),
      });

      if (!resp.ok) {
        const errorText = await resp.text();
        console.warn(`[Gemini Embedding] Attempt ${attempt + 1} failed: ${resp.status} - ${errorText.slice(0, 100)}`);
        await new Promise((r) => setTimeout(r, 600));
        continue;
      }

      const json = await resp.json();
      const embedding = json.embedding?.values;
      if (Array.isArray(embedding) && embedding.length > 0) {
        return embedding;
      }
    } catch (err: any) {
      console.warn(`[Gemini Embedding] Exception on attempt ${attempt + 1}: ${err.message}`);
      await new Promise((r) => setTimeout(r, 600));
    }
  }

  // Fallback to OpenAI text-embedding-3-large (3072 dimensions) if Gemini fails
  if (process.env.OPENAI_API_KEY) {
    try {
      const openaiResp = await fetch('https://api.openai.com/v1/embeddings', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${process.env.OPENAI_API_KEY}`,
        },
        body: JSON.stringify({
          model: 'text-embedding-3-large',
          input: cleanText,
          dimensions: 3072,
        }),
      });

      if (openaiResp.ok) {
        const ojson = await openaiResp.json();
        return ojson.data[0].embedding;
      }
    } catch (err) {
      console.error('[OpenAI Embedding Fallback Failed]:', err);
    }
  }

  throw new Error('Failed to generate 3072-dim vector embedding. Vui lòng kiểm tra GEMINI_API_KEY.');
}
