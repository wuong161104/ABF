export interface PipelineNode {
  id: string;
  name: string;
  description: string;
  status: 'idle' | 'processing' | 'completed' | 'error';
  count: number;
  badge?: string;
  detail?: string;
}

export interface CrawledChunk {
  id: string;
  sourceUrl?: string;
  fileName?: string;
  heading?: string;
  content: string;
  tokenEstimate: number;
  embeddingId?: number | string;
  status: 'pending' | 'embedding' | 'synced' | 'failed';
  timestamp: string;
  similarity?: number;
}

export interface CrawlOptions {
  url: string;
  maxPages?: number;
  includeImages?: boolean;
  instantRag?: boolean;
  depth?: number;
}

export interface IngestOptions {
  fileType: 'pdf' | 'docx' | 'txt' | 'md';
  fileName: string;
  instantRag?: boolean;
}

export interface SupabaseDocumentRecord {
  id: number;
  content: string;
  metadata: {
    source?: string;
    type?: string;
    title?: string;
    heading?: string;
    created_at?: string;
    token_count?: number;
    has_vision_ocr?: boolean;
  };
  similarity?: number;
}
