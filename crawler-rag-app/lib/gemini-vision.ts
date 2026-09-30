/**
 * Multimodal Vision & Layout OCR Engine
 * Chuyên trách bóc tách "điểm ảnh" & "điểm chữ" cho tài liệu PDF, hình ảnh biểu phí,
 * bảng biểu ngân hàng và tài liệu scan phức tạp.
 * Khóa API được tải hoàn toàn từ biến môi trường.
 */

export async function analyzePdfLayoutAndPixels(
  buffer: Buffer,
  filename: string,
  rawText: string
): Promise<{
  structuredMarkdown: string;
  hasVisionOcr: boolean;
  pixelHighlights: string[];
}> {
  const apiKey = process.env.GEMINI_API_KEY;

  if (apiKey && buffer.length > 0 && buffer.length < 15 * 1024 * 1024) {
    try {
      const base64Data = buffer.toString('base64');
      const mimeType = filename.toLowerCase().endsWith('.pdf') ? 'application/pdf' : 'image/png';

      const prompt = `Bạn là chuyên gia phân tích thị giác và bóc tách dữ liệu tài liệu (Deep Document Layout & Vision Parser).
Hãy thực hiện 2 nhiệm vụ cốt lõi:
1. "Nhận biết điểm chữ": Đọc toàn bộ văn bản, tiêu đề cấp mục (Điều, Khoản, Mục), chính sách, điều kiện.
2. "Nhận biết điểm ảnh": Nhận diện các hình ảnh, bảng biểu tính năng thẻ, biểu phí, tem nhãn, sơ đồ hoặc chữ bị chìm dưới đồ họa/ảnh scan.

Định dạng xuất ra dạng Markdown chuẩn mực:
- Giữ nguyên toàn bộ số liệu, % lãi suất, hạn mức, phí thường niên.
- Chuyển các bảng biểu thành cú pháp Table Markdown rõ ràng.
- Ghi chú các điểm ảnh đặc thù: [PIXEL_ELEMENT: biểu tượng/ảnh thẻ/biểu phí].
Không thêm lời mở đầu hay kết thúc thừa thãi.`;

      const response = await fetch(
        `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${apiKey}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            contents: [
              {
                parts: [
                  { text: prompt },
                  {
                    inline_data: {
                      mime_type: mimeType,
                      data: base64Data,
                    },
                  },
                ],
              },
            ],
            generationConfig: {
              temperature: 0.1,
              maxOutputTokens: 4096,
            },
          }),
        }
      );

      if (response.ok) {
        const result = await response.json();
        const visionText = result.candidates?.[0]?.content?.parts?.[0]?.text;
        if (visionText && visionText.length > 100) {
          return {
            structuredMarkdown: visionText,
            hasVisionOcr: true,
            pixelHighlights: ['Đã phân tích điểm ảnh & bảng biểu qua Gemini Multimodal Vision'],
          };
        }
      } else {
        console.warn(`[Gemini Vision] Response status: ${response.status}`);
      }
    } catch (err: any) {
      console.warn(`[Gemini Vision Fallback]: ${err.message}`);
    }
  }

  // Fallback to formatted raw text if multimodal call is not applicable
  return {
    structuredMarkdown: rawText,
    hasVisionOcr: false,
    pixelHighlights: ['Bóc tách text layer trực tiếp từ file tài liệu'],
  };
}
