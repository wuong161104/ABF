'use client';

import React, { useState, useEffect, useRef } from 'react';
import {
  Globe,
  FileText,
  Database,
  Layers,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Search,
  Zap,
  Eye,
  FileUp,
  Activity
} from 'lucide-react';
import { PipelineNode, CrawledChunk } from '@/lib/types';

export default function Home() {
  // Navigation tabs
  const [activeSourceTab, setActiveSourceTab] = useState<'crawler' | 'documents'>('crawler');
  const [activeBottomTab, setActiveBottomTab] = useState<'stream' | 'query' | 'supabase'>('stream');

  // Crawler inputs
  const [targetUrl, setTargetUrl] = useState('https://www.vpbank.com.vn/ca-nhan/dich-vu-the');
  const [maxPages, setMaxPages] = useState(1);
  const [instantRag, setInstantRag] = useState(true);

  // Document inputs
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [enableVisionOcr, setEnableVisionOcr] = useState(true);

  // Pipeline status nodes
  const [pipelineNodes, setPipelineNodes] = useState<PipelineNode[]>([
    { id: 'fetch', name: '1. Ingestion', description: 'Web Fetch / Doc Upload', status: 'idle', count: 0 },
    { id: 'vision_ocr', name: '2. Multimodal Vision', description: 'Điểm ảnh & Điểm chữ OCR', status: 'idle', count: 0 },
    { id: 'chunking', name: '3. Semantic Chunker', description: 'Structure & Overlap (900c)', status: 'idle', count: 0 },
    { id: 'embedding', name: '4. Vectorizer (3072d)', description: 'Gemini Vector Embedding', status: 'idle', count: 0 },
    { id: 'supabase', name: '5. Supabase Sync', description: 'pgvector & Knowledge DB', status: 'idle', count: 0 },
  ]);

  // Real-time chunks and logs
  const [syncedChunks, setSyncedChunks] = useState<CrawledChunk[]>([]);
  const [logs, setLogs] = useState<string[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [activeStepText, setActiveStepText] = useState('Hệ thống sẵn sàng tiếp nhận URL hoặc tài liệu.');

  // Supabase stats
  const [dbStats, setDbStats] = useState({ totalChunks: 0, recentRecords: [] as any[] });
  const [isLoadingStats, setIsLoadingStats] = useState(false);

  // RAG Query Sandbox
  const [queryInput, setQueryInput] = useState('');
  const [isQuerying, setIsQuerying] = useState(false);
  const [queryResult, setQueryResult] = useState<{ answer: string; matchedChunks: any[] } | null>(null);

  const streamEndRef = useRef<HTMLDivElement>(null);

  // Load Supabase Stats on mount
  useEffect(() => {
    fetchStats();
  }, []);

  useEffect(() => {
    streamEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [syncedChunks, logs]);

  const fetchStats = async () => {
    setIsLoadingStats(true);
    try {
      const resp = await fetch('/api/stats');
      const data = await resp.json();
      if (data.success) {
        setDbStats({
          totalChunks: data.totalChunks,
          recentRecords: data.recentRecords,
        });
      }
    } catch (e) {
      console.error('Error fetching stats:', e);
    } finally {
      setIsLoadingStats(false);
    }
  };

  const updateNodeStatus = (stepId: string, status: PipelineNode['status'], countDelta = 0, message?: string) => {
    setPipelineNodes((prev) =>
      prev.map((node) => {
        if (node.id === stepId) {
          return {
            ...node,
            status,
            count: countDelta > 0 ? countDelta : node.count,
            detail: message || node.detail,
          };
        }
        return node;
      })
    );
    if (message) {
      setActiveStepText(message);
      setLogs((prev) => [...prev, `[${new Date().toLocaleTimeString()}] ${message}`]);
    }
  };

  const resetPipeline = () => {
    setPipelineNodes([
      { id: 'fetch', name: '1. Ingestion', description: 'Web Fetch / Doc Upload', status: 'idle', count: 0 },
      { id: 'vision_ocr', name: '2. Multimodal Vision', description: 'Điểm ảnh & Điểm chữ OCR', status: 'idle', count: 0 },
      { id: 'chunking', name: '3. Semantic Chunker', description: 'Structure & Overlap (900c)', status: 'idle', count: 0 },
      { id: 'embedding', name: '4. Vectorizer (3072d)', description: 'Gemini Vector Embedding', status: 'idle', count: 0 },
      { id: 'supabase', name: '5. Supabase Sync', description: 'pgvector & Knowledge DB', status: 'idle', count: 0 },
    ]);
    setSyncedChunks([]);
    setLogs([]);
  };

  // Trigger Crawler Pipeline
  const handleStartCrawl = async () => {
    if (!targetUrl) return;
    setIsProcessing(true);
    resetPipeline();
    setActiveBottomTab('stream');

    try {
      updateNodeStatus('fetch', 'processing', 0, `Đang kết nối và quét DOM: ${targetUrl}`);

      const response = await fetch('/api/crawl', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: targetUrl,
          maxPages,
          instantRag,
        }),
      });

      if (!response.ok) {
        throw new Error(`Lỗi kết nối máy chủ (${response.status})`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let pipelineHasError = false;
      let errorStepMessage = '';

      if (!reader) throw new Error('Không thể khởi tạo luồng dữ liệu.');

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.trim()) continue;
          const eventMatch = line.match(/^event: (.+)$/m);
          const dataMatch = line.match(/^data: (.+)$/m);

          if (eventMatch && dataMatch) {
            const eventName = eventMatch[1].trim();
            const eventData = JSON.parse(dataMatch[1].trim());

            if (eventName === 'pipeline_step') {
              if (eventData.status === 'error') {
                pipelineHasError = true;
                errorStepMessage = eventData.message || 'Lỗi xử lý';
              }
              updateNodeStatus(eventData.stepId, eventData.status, eventData.count || 0, eventData.message);
            } else if (eventName === 'chunk_synced') {
              setSyncedChunks((prev) => [...prev, eventData.chunk]);
              setPipelineNodes((nodes) =>
                nodes.map((n) =>
                  n.id === 'supabase'
                    ? { ...n, count: n.count + 1, status: 'completed' }
                    : n.id === 'embedding'
                    ? { ...n, count: n.count + 1, status: 'completed' }
                    : n
                )
              );
            } else if (eventName === 'log') {
              setLogs((prev) => [...prev, `[${new Date().toLocaleTimeString()}] ${eventData.message}`]);
            }
          }
        }
      }

      fetchStats();
      if (pipelineHasError) {
        setActiveStepText(`❌ Quá trình gián đoạn: ${errorStepMessage}`);
      } else {
        setActiveStepText('✅ Hoàn tất toàn bộ quy trình Crawl & RAG tức thì vào Supabase!');
      }
    } catch (err: any) {
      updateNodeStatus('fetch', 'error', 0, err.message);
      setActiveStepText(`❌ Lỗi kết nối: ${err.message}`);
    } finally {
      setIsProcessing(false);
    }
  };

  // Trigger Document Ingestion Pipeline
  const handleUploadDocument = async () => {
    if (!selectedFile) return;
    setIsProcessing(true);
    resetPipeline();
    setActiveBottomTab('stream');

    try {
      updateNodeStatus('fetch', 'processing', 1, `Đang nạp file: ${selectedFile.name}`);

      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('instantRag', 'true');
      formData.append('visionOcr', enableVisionOcr ? 'true' : 'false');

      updateNodeStatus('vision_ocr', 'processing', 1, 'Đang phân tích điểm ảnh & điểm chữ bằng Gemini Vision...');

      const resp = await fetch('/api/ingest', {
        method: 'POST',
        body: formData,
      });

      const result = await resp.json();
      if (!resp.ok) {
        throw new Error(result.error || 'Lỗi xử lý tài liệu');
      }

      updateNodeStatus('vision_ocr', 'completed', 1, result.pixelHighlights?.join(', ') || 'Đã phân tích điểm chữ & điểm ảnh');
      updateNodeStatus('chunking', 'completed', result.totalChunks, `Phân tách thành công ${result.totalChunks} đoạn ngữ nghĩa`);
      updateNodeStatus('embedding', 'completed', result.syncedCount, `Hoàn tất embedding 3072D cho ${result.syncedCount} chunks`);
      updateNodeStatus('supabase', 'completed', result.syncedCount, `Đã đồng bộ ${result.syncedCount} bản ghi vào Supabase`);

      if (Array.isArray(result.chunks)) {
        setSyncedChunks(result.chunks);
      }

      fetchStats();
      setActiveStepText(`✅ Tài liệu ${selectedFile.name} đã được phân tích điểm ảnh/điểm chữ và RAG vào Supabase!`);
    } catch (err: any) {
      updateNodeStatus('fetch', 'error', 0, err.message);
    } finally {
      setIsProcessing(false);
    }
  };

  // Trigger RAG Query
  const handleRunQuery = async () => {
    if (!queryInput.trim()) return;
    setIsQuerying(true);
    try {
      const resp = await fetch('/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: queryInput, matchCount: 5 }),
      });
      const data = await resp.json();
      if (data.success) {
        setQueryResult({
          answer: data.answer,
          matchedChunks: data.matchedChunks,
        });
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsQuerying(false);
    }
  };

  return (
    <main className="min-h-screen bg-[#07090E] text-slate-100 flex flex-col selection:bg-cyan-500/20 selection:text-cyan-200">
      {/* Top Navbar */}
      <header className="border-b border-[#161D2B] bg-[#0A0D16]/90 backdrop-blur-md sticky top-0 z-50 px-4 lg:px-8 py-3.5 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-cyan-600 via-blue-600 to-indigo-600 flex items-center justify-center shadow-lg shadow-cyan-900/30 ring-1 ring-cyan-400/30">
            <Zap className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-bold tracking-tight text-white flex items-center gap-1.5">
                ABF Multimodal Crawler & RAG Hub
              </h1>
              <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded-full bg-cyan-950/80 text-cyan-300 border border-cyan-700/40">
                v2.4 Production
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Cào tự động • Nhận diện điểm ảnh & điểm chữ • Instant RAG Supabase • Deploy Vercel
            </p>
          </div>
        </div>

        {/* Global Connection Badges */}
        <div className="flex items-center gap-2.5 text-xs font-mono">
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#0E1524] border border-[#1E293B] text-emerald-400 shadow-sm">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
            <Database className="w-3.5 h-3.5 text-emerald-400" />
            <span>Supabase: {dbStats.totalChunks} Chunks (3072D)</span>
          </div>

          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#0E1524] border border-[#1E293B] text-amber-300">
            <Eye className="w-3.5 h-3.5 text-amber-400" />
            <span>Gemini Vision Multimodal</span>
          </div>

          <button
            onClick={fetchStats}
            disabled={isLoadingStats}
            className="p-1.5 rounded-lg bg-[#0E1524] border border-[#1E293B] hover:border-slate-600 text-slate-400 hover:text-white transition"
            title="Làm mới trạng thái Supabase"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoadingStats ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="flex-1 max-w-7xl w-full mx-auto p-4 lg:p-6 space-y-6">

        {/* 1. INTERACTIVE 5-NODE REALTIME PIPELINE VISUALIZER */}
        <section className="bg-[#0C111C] border border-[#1A2333] rounded-2xl p-5 shadow-2xl relative overflow-hidden">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-cyan-400" />
              <h2 className="text-sm font-semibold tracking-wide uppercase text-slate-300">
                Visual Pipeline Luồng Dữ Liệu Tự Động (Instant RAG Architecture)
              </h2>
            </div>
            <span className="text-xs font-mono text-cyan-400 bg-cyan-950/60 border border-cyan-800/40 px-2.5 py-1 rounded-md">
              {activeStepText}
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-5 gap-3 relative">
            {pipelineNodes.map((node, idx) => {
              const isProcessing = node.status === 'processing';
              const isCompleted = node.status === 'completed';
              const isError = node.status === 'error';

              return (
                <div
                  key={node.id}
                  className={`relative p-3.5 rounded-xl border transition-all duration-300 flex flex-col justify-between ${
                    isProcessing
                      ? 'bg-cyan-950/30 border-cyan-500/60 shadow-lg shadow-cyan-950/50 radar-active'
                      : isCompleted
                      ? 'bg-[#0E1626] border-emerald-500/40 shadow-sm'
                      : isError
                      ? 'bg-rose-950/20 border-rose-500/60 text-rose-300'
                      : 'bg-[#0E1420] border-[#182232] opacity-80'
                  }`}
                >
                  <div className="flex items-start justify-between mb-2">
                    <span className="text-xs font-bold text-white tracking-tight">{node.name}</span>
                    {isProcessing ? (
                      <RefreshCw className="w-4 h-4 text-cyan-400 animate-spin" />
                    ) : isCompleted ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    ) : isError ? (
                      <AlertCircle className="w-4 h-4 text-rose-400" />
                    ) : (
                      <span className="w-2 h-2 rounded-full bg-slate-700" />
                    )}
                  </div>
                  <p className="text-[11px] text-slate-400 line-clamp-2 leading-relaxed mb-2">
                    {node.description}
                  </p>
                  {isError && node.message && (
                    <div className="mb-2 p-1.5 rounded-lg bg-rose-950/60 border border-rose-800/60 text-[10px] text-rose-300 font-mono line-clamp-2" title={node.message}>
                      ⚠️ {node.message}
                    </div>
                  )}
                  <div className="flex items-center justify-between text-[11px] font-mono pt-2 border-t border-slate-800/60">
                    <span className="text-slate-500">Items:</span>
                    <span className={isCompleted ? 'text-emerald-400 font-bold' : isProcessing ? 'text-cyan-300 font-bold' : 'text-slate-400'}>
                      {node.count}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        {/* 2. DUAL INGESTION COMMAND CENTER */}
        <section className="bg-[#0C111C] border border-[#1A2333] rounded-2xl p-5 shadow-xl">
          {/* Ingestion Mode Toggle Tabs */}
          <div className="flex items-center gap-2 border-b border-[#1A2333] pb-3 mb-5">
            <button
              onClick={() => setActiveSourceTab('crawler')}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition ${
                activeSourceTab === 'crawler'
                  ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/40'
              }`}
            >
              <Globe className="w-4 h-4" />
              <span>Deep Web Crawler (Toàn diện website & link con)</span>
            </button>

            <button
              onClick={() => setActiveSourceTab('documents')}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition ${
                activeSourceTab === 'documents'
                  ? 'bg-amber-500/10 text-amber-400 border border-amber-500/30'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/40'
              }`}
            >
              <FileUp className="w-4 h-4" />
              <span>Nạp Tài Liệu &amp; PDF (&quot;Điểm ảnh &amp; Điểm chữ&quot; OCR)</span>
            </button>
          </div>

          {/* TAB 1: CRAWLER STATION */}
          {activeSourceTab === 'crawler' && (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <label className="text-xs font-semibold text-slate-300 flex items-center gap-2">
                  <span>🔗 Đường dẫn Website mục tiêu:</span>
                  <span className="text-[11px] font-normal text-slate-500">(Hỗ trợ cào thẻ headings h1-h6, biểu phí, ảnh, link con)</span>
                </label>
                <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
                  <span className="text-slate-500 mr-1">Presets:</span>
                  {[
                    { label: 'Thẻ VPBank', url: 'https://www.vpbank.com.vn/ca-nhan/dich-vu-the' },
                    { label: 'Thẻ VIB', url: 'https://www.vib.com.vn/vn/the-tin-dung' },
                    { label: 'Techcombank', url: 'https://techcombank.com/khach-hang-ca-nhan/the' },
                    { label: 'VPBank Toàn Trang', url: 'https://www.vpbank.com.vn/' },
                  ].map((p) => (
                    <button
                      key={p.label}
                      onClick={() => setTargetUrl(p.url)}
                      className="px-2.5 py-1 rounded-md bg-[#131B2A] border border-[#212E44] hover:border-cyan-500/50 text-slate-300 hover:text-cyan-300 transition"
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex flex-col sm:flex-row gap-3">
                <div className="relative flex-1">
                  <input
                    type="url"
                    value={targetUrl}
                    onChange={(e) => setTargetUrl(e.target.value)}
                    placeholder="https://..."
                    className="w-full bg-[#080B12] border border-[#212E44] rounded-xl px-4 py-3 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-cyan-500 transition"
                  />
                </div>
                <button
                  onClick={handleStartCrawl}
                  disabled={isProcessing}
                  className="px-6 py-3 rounded-xl bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-bold text-sm flex items-center justify-center gap-2 shadow-lg shadow-cyan-900/30 transition disabled:opacity-50"
                >
                  {isProcessing ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin" />
                      <span>Đang Crawl & RAG Tức Thì...</span>
                    </>
                  ) : (
                    <>
                      <Zap className="w-4 h-4 text-cyan-200" />
                      <span>BẮT ĐẦU CRAWL & RAG NGAY</span>
                    </>
                  )}
                </button>
              </div>

              <div className="flex flex-wrap items-center gap-6 pt-2 text-xs text-slate-400 border-t border-slate-800/40">
                <label className="flex items-center gap-2 cursor-pointer select-none text-cyan-300">
                  <input
                    type="checkbox"
                    checked={instantRag}
                    onChange={(e) => setInstantRag(e.target.checked)}
                    className="rounded bg-slate-900 border-slate-700 text-cyan-500 focus:ring-0"
                  />
                  <span>Bật chế độ &quot;Cào đoạn nào - RAG Supabase đoạn đó ngay lập tức&quot;</span>
                </label>

                <div className="flex items-center gap-2">
                  <span>Số trang con tối đa:</span>
                  <input
                    type="number"
                    min="1"
                    max="20"
                    value={maxPages}
                    onChange={(e) => setMaxPages(parseInt(e.target.value) || 1)}
                    className="w-16 bg-[#080B12] border border-[#212E44] rounded-md px-2 py-1 text-center text-white"
                  />
                  <span className="text-[11px] text-slate-500">(1 = Chỉ trang chính, &gt;1 = Tự động quét tiếp link con)</span>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: DOCUMENT & PDF MULTIMODAL INGESTION */}
          {activeSourceTab === 'documents' && (
            <div className="space-y-4">
              <div
                className="border-2 border-dashed border-[#223048] hover:border-amber-500/50 bg-[#080C14] rounded-2xl p-8 text-center transition cursor-pointer relative"
                onClick={() => document.getElementById('docFileInput')?.click()}
              >
                <input
                  id="docFileInput"
                  type="file"
                  accept=".pdf,.docx,.txt,.md"
                  className="hidden"
                  onChange={(e) => {
                    if (e.target.files && e.target.files[0]) {
                      setSelectedFile(e.target.files[0]);
                    }
                  }}
                />
                <div className="w-12 h-12 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-400 flex items-center justify-center mx-auto mb-3">
                  <FileText className="w-6 h-6" />
                </div>
                {selectedFile ? (
                  <div>
                    <p className="text-sm font-bold text-white">{selectedFile.name}</p>
                    <p className="text-xs text-slate-400 mt-1">
                      Kích thước: {(selectedFile.size / 1024).toFixed(1)} KB • Nhấn để đổi file khác
                    </p>
                  </div>
                ) : (
                  <div>
                    <p className="text-sm font-semibold text-slate-300">
                      Kéo thả hoặc nhấp để chọn tệp tài liệu (PDF, DOCX, TXT, MD)
                    </p>
                    <p className="text-xs text-slate-500 mt-1">
                      Đặc biệt: PDF sẽ được phân tích điểm chữ & điểm ảnh (bảng biểu biểu phí, scan) qua Gemini Vision
                    </p>
                  </div>
                )}
              </div>

              <div className="flex flex-wrap items-center justify-between gap-4 pt-2">
                <label className="flex items-center gap-2 cursor-pointer select-none text-xs text-amber-300">
                  <input
                    type="checkbox"
                    checked={enableVisionOcr}
                    onChange={(e) => setEnableVisionOcr(e.target.checked)}
                    className="rounded bg-slate-900 border-slate-700 text-amber-500 focus:ring-0"
                  />
                  <span>Tự động kích hoạt nhận diện điểm ảnh, hình ảnh biểu phí bảng biểu qua Gemini Vision</span>
                </label>

                <button
                  onClick={handleUploadDocument}
                  disabled={!selectedFile || isProcessing}
                  className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-500 hover:to-orange-500 text-white font-bold text-sm flex items-center gap-2 transition disabled:opacity-50"
                >
                  {isProcessing ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin" />
                      <span>Đang phân tích & RAG...</span>
                    </>
                  ) : (
                    <>
                      <Eye className="w-4 h-4" />
                      <span>PHÂN TÍCH ĐIỂM ẢNH/ĐIỂM CHỮ & RAG</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          )}
        </section>

        {/* 3. MULTI-PANEL RESULTS: REALTIME STREAM / RAG QUERY SANDBOX / SUPABASE REPOSITORY */}
        <section className="bg-[#0C111C] border border-[#1A2333] rounded-2xl overflow-hidden shadow-2xl flex flex-col min-h-[500px]">
          {/* Sub Navigation Bar */}
          <div className="flex items-center justify-between border-b border-[#1A2333] bg-[#0A0E18] px-4 py-2.5">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setActiveBottomTab('stream')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                  activeBottomTab === 'stream'
                    ? 'bg-slate-800 text-cyan-300 border border-slate-700'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                <Activity className="w-3.5 h-3.5" />
                <span>Live RAG Chunks Stream ({syncedChunks.length})</span>
              </button>

              <button
                onClick={() => setActiveBottomTab('query')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                  activeBottomTab === 'query'
                    ? 'bg-slate-800 text-blue-300 border border-slate-700'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                <Search className="w-3.5 h-3.5" />
                <span>Kiểm Thử RAG Sandbox (Hỏi & Tra Cứu)</span>
              </button>

              <button
                onClick={() => {
                  setActiveBottomTab('supabase');
                  fetchStats();
                }}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                  activeBottomTab === 'supabase'
                    ? 'bg-slate-800 text-emerald-300 border border-slate-700'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                <Database className="w-3.5 h-3.5" />
                <span>Kho Dữ Liệu Supabase ({dbStats.totalChunks})</span>
              </button>
            </div>

            <div className="text-[11px] font-mono text-slate-500">
              Embedding Model: <span className="text-cyan-400">Gemini 3072D</span>
            </div>
          </div>

          {/* TAB CONTENT 1: LIVE RAG CHUNKS STREAM */}
          {activeBottomTab === 'stream' && (
            <div className="p-4 flex-1 flex flex-col space-y-3">
              {syncedChunks.length === 0 ? (
                <div className="flex-1 flex flex-col items-center justify-center text-slate-500 py-16">
                  <Layers className="w-12 h-12 text-slate-700 mb-3" />
                  <p className="text-sm font-medium">Chưa có dữ liệu nào được RAG vào Supabase trong phiên này.</p>
                  <p className="text-xs text-slate-600 mt-1">
                    Nhập URL hoặc tải tệp lên phía trên rồi nhấn Bắt đầu để thấy các chunk xuất hiện theo thời gian thực!
                  </p>
                </div>
              ) : (
                <div className="space-y-3 max-h-[550px] overflow-y-auto pr-1">
                  {syncedChunks.map((chunk, idx) => (
                    <div
                      key={chunk.id || idx}
                      className="p-3.5 rounded-xl bg-[#090D17] border border-[#1A2438] hover:border-cyan-500/40 transition glow-card flex flex-col gap-2"
                    >
                      <div className="flex items-center justify-between text-xs">
                        <div className="flex items-center gap-2">
                          <span className="w-5 h-5 rounded-md bg-cyan-950 border border-cyan-800/60 text-cyan-300 font-mono flex items-center justify-center text-[10px] font-bold">
                            #{idx + 1}
                          </span>
                          <span className="font-semibold text-white truncate max-w-md">
                            {chunk.heading || 'Nội dung chung'}
                          </span>
                        </div>
                        <div className="flex items-center gap-3 font-mono text-[11px]">
                          <span className="text-slate-500">~{chunk.tokenEstimate} tokens</span>
                          <span className="px-2 py-0.5 rounded bg-emerald-950/80 text-emerald-400 border border-emerald-800/40 flex items-center gap-1 font-semibold">
                            <CheckCircle2 className="w-3 h-3" />
                            <span>Synced ID: {chunk.embeddingId || 'pgvector'}</span>
                          </span>
                        </div>
                      </div>
                      <p className="text-xs text-slate-300 bg-[#06080F] p-2.5 rounded-lg font-mono border border-slate-900 leading-relaxed whitespace-pre-wrap">
                        {chunk.content}
                      </p>
                      <div className="flex items-center justify-between text-[10px] text-slate-500 font-mono">
                        <span>Nguồn: {chunk.sourceUrl || chunk.fileName}</span>
                        <span>{chunk.timestamp}</span>
                      </div>
                    </div>
                  ))}
                  <div ref={streamEndRef} />
                </div>
              )}
            </div>
          )}

          {/* TAB CONTENT 2: RAG QUERY & SANDBOX TESTER */}
          {activeBottomTab === 'query' && (
            <div className="p-5 flex-1 flex flex-col space-y-4">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={queryInput}
                  onChange={(e) => setQueryInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleRunQuery()}
                  placeholder="Đặt câu hỏi thử nghiệm để kiểm tra dữ liệu vừa RAG (ví dụ: Điều kiện mở thẻ VPBank StepUp là gì?)..."
                  className="flex-1 bg-[#080B12] border border-[#212E44] rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-blue-500"
                />
                <button
                  onClick={handleRunQuery}
                  disabled={isQuerying || !queryInput.trim()}
                  className="px-6 py-3 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-bold text-sm flex items-center gap-2 disabled:opacity-50 transition"
                >
                  {isQuerying ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                  <span>Hỏi AI & Vector Search</span>
                </button>
              </div>

              {queryResult && (
                <div className="space-y-4 mt-2">
                  <div className="p-4 rounded-xl bg-blue-950/20 border border-blue-500/30">
                    <div className="flex items-center gap-2 text-xs font-bold text-blue-400 uppercase tracking-wide mb-2">
                      <Sparkles className="w-4 h-4" />
                      <span>Câu trả lời tổng hợp từ Gemini 1.5 Flash (RAG Grounded):</span>
                    </div>
                    <div className="text-sm text-slate-200 leading-relaxed whitespace-pre-wrap font-sans">
                      {queryResult.answer}
                    </div>
                  </div>

                  <div>
                    <h3 className="text-xs font-semibold uppercase text-slate-400 mb-2">
                      Top Đoạn Trích Dẫn Tìm Thấy Từ Supabase pgvector:
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {queryResult.matchedChunks.map((doc, i) => (
                        <div key={doc.id || i} className="p-3 bg-[#080B13] border border-[#1E293B] rounded-xl text-xs space-y-1.5">
                          <div className="flex items-center justify-between font-mono text-[11px]">
                            <span className="text-cyan-400 font-bold truncate max-w-[200px]">
                              {doc.metadata?.title || doc.metadata?.heading || 'Tài liệu'}
                            </span>
                            <span className="px-2 py-0.5 rounded bg-blue-950 text-blue-300 border border-blue-800/40">
                              Độ khớp: {doc.similarity ? (doc.similarity * 100).toFixed(1) + '%' : 'Top Match'}
                            </span>
                          </div>
                          <p className="text-slate-300 font-mono text-[11px] line-clamp-4 bg-black/40 p-2 rounded border border-slate-900">
                            {doc.content}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB CONTENT 3: SUPABASE KNOWLEDGE EXPLORER */}
          {activeBottomTab === 'supabase' && (
            <div className="p-4 flex-1 flex flex-col space-y-3">
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span>15 Bản ghi mới nhất trong bảng <code>public.documents</code>:</span>
                <span className="font-mono text-emerald-400">Database: postgres.azpvcqpnecljsosamnot</span>
              </div>

              <div className="border border-[#1A2438] rounded-xl overflow-hidden">
                <table className="w-full text-left text-xs">
                  <thead className="bg-[#080C14] text-slate-400 font-mono uppercase text-[10px] border-b border-[#1A2438]">
                    <tr>
                      <th className="p-2.5">ID</th>
                      <th className="p-2.5">Tiêu đề / Heading</th>
                      <th className="p-2.5">Loại</th>
                      <th className="p-2.5">Nội dung trích đoạn</th>
                      <th className="p-2.5">Thời gian</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#151D2C] font-mono text-[11px]">
                    {dbStats.recentRecords.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="p-6 text-center text-slate-500">
                          Chưa có dữ liệu. Hãy cào trang web hoặc nạp tài liệu để ghi vào Supabase.
                        </td>
                      </tr>
                    ) : (
                      dbStats.recentRecords.map((rec) => (
                        <tr key={rec.id} className="hover:bg-slate-900/40 transition">
                          <td className="p-2.5 text-cyan-400 font-bold">#{rec.id}</td>
                          <td className="p-2.5 text-white font-medium max-w-[180px] truncate">
                            {rec.metadata?.heading || rec.metadata?.title || 'Tài liệu'}
                          </td>
                          <td className="p-2.5 text-slate-400">
                            <span className="px-1.5 py-0.5 rounded bg-slate-800 text-[10px]">
                              {rec.metadata?.type || 'doc'}
                            </span>
                          </td>
                          <td className="p-2.5 text-slate-300 max-w-[300px] truncate">
                            {rec.content}
                          </td>
                          <td className="p-2.5 text-slate-500 whitespace-nowrap">
                            {rec.metadata?.created_at ? new Date(rec.metadata.created_at).toLocaleTimeString('vi-VN') : 'Mới nạp'}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </section>

      </div>

      {/* Footer */}
      <footer className="border-t border-[#161D2B] bg-[#0A0D16] py-4 px-6 text-center text-xs text-slate-500 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span>ABF Enterprise Data Platform</span>
          <span>•</span>
          <span className="text-cyan-400">Designed with Taste Skill v2</span>
        </div>
        <div className="flex items-center gap-4 text-[11px]">
          <span>Deploy Target: <b>Vercel Edge / Serverless</b></span>
          <span>Storage: <b>Supabase pgvector (3072D)</b></span>
          <span>Vision: <b>Gemini 1.5 Flash</b></span>
        </div>
      </footer>
    </main>
  );
}
