'use client';

import React, { useState, useEffect, useRef } from 'react';
import {
  Globe,
  FileText,
  Database,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Search,
  Zap,
  Eye,
  FileUp,
  Terminal,
  Copy,
  Cloud,
  Play,
  ExternalLink,
  Clock,
  Server,
  ArrowRight
} from 'lucide-react';
import { CrawledChunk } from '@/lib/types';

interface LogEntry {
  timestamp: string;
  tag: string;
  message: string;
  type: 'info' | 'success' | 'warn' | 'error';
}

export default function Home() {
  // Navigation: 2 clean modes
  const [activeSourceTab, setActiveSourceTab] = useState<'cloud' | 'documents'>('cloud');
  const [activeBottomTab, setActiveBottomTab] = useState<'query' | 'supabase' | 'logs'>('query');

  // Cloud Crawler input state
  const [targetUrl, setTargetUrl] = useState('https://mbbank.com.vn/');
  const [cloudMaxPages, setCloudMaxPages] = useState('0'); // '0' = cào 100% sitemap
  const [cloudForceRecrawl, setCloudForceRecrawl] = useState(false);
  const [isTriggeringCloud, setIsTriggeringCloud] = useState(false);
  const [cloudStatus, setCloudStatus] = useState<any>(null);
  const [cloudSuccessMsg, setCloudSuccessMsg] = useState('');
  const [cloudErrorMsg, setCloudErrorMsg] = useState('');
  const [isPollingCloud, setIsPollingCloud] = useState(false);

  // Document ingestion state
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [enableVisionOcr, setEnableVisionOcr] = useState(true);
  const [isProcessingDoc, setIsProcessingDoc] = useState(false);

  // Logs & sync chunks
  const [syncedChunks, setSyncedChunks] = useState<CrawledChunk[]>([]);
  const [logEntries, setLogEntries] = useState<LogEntry[]>([]);
  const [progressPercent, setProgressPercent] = useState<number>(0);
  const [progressMessage, setProgressMessage] = useState<string>('');

  // Supabase stats
  const [dbStats, setDbStats] = useState({ totalChunks: 0, recentRecords: [] as any[] });
  const [isLoadingStats, setIsLoadingStats] = useState(false);

  // RAG Query Sandbox
  const [queryInput, setQueryInput] = useState('');
  const [isQuerying, setIsQuerying] = useState(false);
  const [queryResult, setQueryResult] = useState<{ answer: string; matchedChunks: any[] } | null>(null);

  const streamEndRef = useRef<HTMLDivElement>(null);

  // Load stats and cloud status on mount + polling
  useEffect(() => {
    fetchStats();
    fetchCloudStatus();
    const interval = setInterval(() => {
      fetchCloudStatus();
      fetchStats();
    }, 10000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    streamEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logEntries]);

  const fetchCloudStatus = async () => {
    setIsPollingCloud(true);
    try {
      const resp = await fetch('/api/cloud-crawler');
      const data = await resp.json();
      if (data.success) {
        setCloudStatus(data);
      }
    } catch (e) {
      console.error('Lỗi kiểm tra trạng thái Cloud Runner:', e);
    } finally {
      setIsPollingCloud(false);
    }
  };

  const handleTriggerCloudCrawler = async () => {
    if (!targetUrl) return;
    setIsTriggeringCloud(true);
    setCloudSuccessMsg('');
    setCloudErrorMsg('');
    try {
      const resp = await fetch('/api/cloud-crawler', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          targetUrl,
          maxPages: cloudMaxPages,
          saveToSupabase: true,
          forceRecrawl: cloudForceRecrawl,
        }),
      });
      const data = await resp.json();
      if (!resp.ok || !data.success) {
        throw new Error(data.error || 'Lỗi khi kích hoạt Cloud Runner');
      }
      setCloudSuccessMsg(data.message);
      fetchCloudStatus();
      fetchStats();
    } catch (err: any) {
      setCloudErrorMsg(err.message);
    } finally {
      setIsTriggeringCloud(false);
    }
  };

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

  // Trigger Document Ingestion Pipeline
  const handleUploadDocument = async () => {
    if (!selectedFile) return;
    setIsProcessingDoc(true);
    setActiveBottomTab('logs');
    setProgressPercent(10);
    setProgressMessage(`Đang nạp tệp: ${selectedFile.name}...`);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('enableVisionOcr', String(enableVisionOcr));

      setLogEntries((prev) => [
        ...prev,
        {
          timestamp: new Date().toLocaleTimeString('vi-VN'),
          tag: 'DOC_UPLOAD',
          message: `Nạp tệp ${selectedFile.name} (${(selectedFile.size / 1024).toFixed(1)} KB)...`,
          type: 'info',
        },
      ]);

      const resp = await fetch('/api/ingest', {
        method: 'POST',
        body: formData,
      });

      const result = await resp.json();
      if (!resp.ok) {
        throw new Error(result.error || 'Lỗi xử lý tài liệu');
      }

      setProgressPercent(100);
      setProgressMessage(`Hoàn tất phân tích và nạp ${result.syncedCount} đoạn vào Supabase!`);

      setLogEntries((prev) => [
        ...prev,
        {
          timestamp: new Date().toLocaleTimeString('vi-VN'),
          tag: 'SUPABASE',
          message: `Đã nạp thành công ${result.syncedCount} bản ghi (Vector 3072D) vào Supabase`,
          type: 'success',
        },
      ]);

      if (Array.isArray(result.chunks)) {
        setSyncedChunks(result.chunks);
      }
      fetchStats();
    } catch (err: any) {
      setProgressPercent(100);
      setProgressMessage(`Lỗi: ${err.message}`);
      setLogEntries((prev) => [
        ...prev,
        {
          timestamp: new Date().toLocaleTimeString('vi-VN'),
          tag: 'ERROR',
          message: err.message,
          type: 'error',
        },
      ]);
    } finally {
      setIsProcessingDoc(false);
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
        body: JSON.stringify({ question: queryInput.trim() }),
      });
      const data = await resp.json();
      if (data.success) {
        setQueryResult({
          answer: data.answer,
          matchedChunks: data.matchedChunks || [],
        });
      }
    } catch (err: any) {
      console.error('Lỗi truy vấn RAG:', err);
    } finally {
      setIsQuerying(false);
    }
  };

  return (
    <main className="min-h-screen bg-[#F8FAFC] text-slate-900 flex flex-col font-sans selection:bg-blue-100 selection:text-blue-900">
      {/* Top Header */}
      <header className="border-b border-slate-200/80 bg-white/90 backdrop-blur-md sticky top-0 z-50 px-4 lg:px-8 py-3.5 flex flex-wrap items-center justify-between gap-4 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-blue-600 flex items-center justify-center shadow-md shadow-blue-500/20 text-white">
            <Zap className="w-5 h-5 fill-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-bold tracking-tight text-slate-900">
                ABF Crawler &amp; Knowledge Hub
              </h1>
              <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200">
                Cloud Runner
              </span>
            </div>
            <p className="text-xs text-slate-500">
              Thu thập dữ liệu website tự động &amp; Nạp tài liệu thông minh
            </p>
          </div>
        </div>

        {/* Status Indicators */}
        <div className="flex items-center gap-2.5 text-xs">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 font-medium">
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            <Database className="w-3.5 h-3.5 text-emerald-600" />
            <span>Supabase: {dbStats.totalChunks.toLocaleString()} Chunks</span>
          </div>

          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-100 border border-slate-200 text-slate-700 font-medium">
            <Server className="w-3.5 h-3.5 text-slate-500" />
            <span>
              {cloudStatus?.isRunning ? 'Cloud: Đang chạy' : 'Cloud: Sẵn sàng'}
            </span>
          </div>

          <button
            onClick={() => {
              fetchStats();
              fetchCloudStatus();
            }}
            disabled={isLoadingStats || isPollingCloud}
            className="p-1.5 rounded-lg bg-white border border-slate-200 hover:bg-slate-50 text-slate-500 hover:text-slate-800 transition shadow-sm"
            title="Làm mới trạng thái"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoadingStats || isPollingCloud ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="flex-1 max-w-6xl w-full mx-auto p-4 lg:p-6 space-y-6">

        {/* 1. MAIN INGESTION COMMAND CENTER */}
        <section className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm space-y-5">
          {/* Ingestion Mode Toggle Tabs */}
          <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
            <button
              onClick={() => setActiveSourceTab('cloud')}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition ${
                activeSourceTab === 'cloud'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
              }`}
            >
              <Cloud className="w-4 h-4" />
              <span>Cào Ngầm Toàn Bộ Website (Cloud Runner 6h)</span>
              {cloudStatus?.isRunning && (
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping ml-1" />
              )}
            </button>

            <button
              onClick={() => setActiveSourceTab('documents')}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition ${
                activeSourceTab === 'documents'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
              }`}
            >
              <FileUp className="w-4 h-4" />
              <span>Nạp Tài Liệu &amp; PDF (Vision OCR)</span>
            </button>
          </div>

          {/* TAB 1: CLOUD RUNNER */}
          {activeSourceTab === 'cloud' && (
            <div className="space-y-4">
              {/* Presets and URL Input */}
              <div className="space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <label className="text-xs font-semibold text-slate-700">
                    Đường dẫn Website mục tiêu:
                  </label>
                  <div className="flex flex-wrap items-center gap-1.5 text-xs">
                    <span className="text-slate-400">Gợi ý:</span>
                    {[
                      { label: 'MBBank', url: 'https://mbbank.com.vn/' },
                      { label: 'VPBank Thẻ', url: 'https://www.vpbank.com.vn/ca-nhan/dich-vu-the' },
                      { label: 'VIB Thẻ', url: 'https://www.vib.com.vn/vn/the-tin-dung' },
                      { label: 'Techcombank', url: 'https://techcombank.com/khach-hang-ca-nhan/the' },
                    ].map((p) => (
                      <button
                        key={p.label}
                        onClick={() => setTargetUrl(p.url)}
                        className="px-2.5 py-1 rounded-md bg-slate-100 hover:bg-slate-200 text-slate-700 transition"
                      >
                        {p.label}
                      </button>
                    ))}
                  </div>
                </div>

                <input
                  type="url"
                  value={targetUrl}
                  onChange={(e) => setTargetUrl(e.target.value)}
                  placeholder="https://..."
                  className="w-full bg-white border border-slate-200 rounded-xl px-4 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition"
                />
              </div>

              {/* Options */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/80">
                  <label className="text-xs font-semibold text-slate-700 block mb-1">
                    Số trang tối đa (max_pages):
                  </label>
                  <select
                    value={cloudMaxPages}
                    onChange={(e) => setCloudMaxPages(e.target.value)}
                    className="w-full bg-white border border-slate-200 rounded-lg px-3 py-1.5 text-xs text-slate-800 focus:outline-none focus:border-blue-500"
                  >
                    <option value="0">0 (Cào toàn bộ 100% website - Khuyến nghị)</option>
                    <option value="50">50 trang</option>
                    <option value="100">100 trang</option>
                    <option value="500">500 trang</option>
                    <option value="1000">1.000 trang</option>
                  </select>
                </div>

                <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/80 flex items-center justify-between">
                  <div>
                    <span className="text-xs font-semibold text-slate-700 block">Lưu trữ Supabase:</span>
                    <span className="text-xs text-emerald-600 font-medium">pgvector (3072D) tự động</span>
                  </div>
                  <label className="flex items-center gap-2 cursor-pointer select-none text-xs text-slate-600">
                    <input
                      type="checkbox"
                      checked={cloudForceRecrawl}
                      onChange={(e) => setCloudForceRecrawl(e.target.checked)}
                      className="rounded border-slate-300 text-blue-600 focus:ring-0"
                    />
                    <span>Cào lại từ đầu</span>
                  </label>
                </div>
              </div>

              {/* Action Button & Direct Links */}
              <div className="flex flex-wrap items-center gap-3 pt-2">
                <button
                  onClick={handleTriggerCloudCrawler}
                  disabled={isTriggeringCloud}
                  className="px-6 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-semibold text-sm flex items-center gap-2 shadow-sm transition disabled:opacity-50"
                >
                  {isTriggeringCloud ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin" />
                      <span>Đang kích hoạt máy chủ...</span>
                    </>
                  ) : (
                    <>
                      <Play className="w-4 h-4 fill-white" />
                      <span>Bắt Đầu Cào Ngầm Trên Cloud (6 Tiếng)</span>
                    </>
                  )}
                </button>

                {cloudStatus?.latestRun?.htmlUrl && (
                  <a
                    href={cloudStatus.latestRun.htmlUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="px-4 py-2.5 rounded-xl bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 text-xs font-medium flex items-center gap-1.5 transition shadow-sm"
                  >
                    <span>Xem Log GitHub Actions</span>
                    <ExternalLink className="w-3.5 h-3.5 text-slate-400" />
                  </a>
                )}
              </div>

              {/* Status Notifications */}
              {cloudSuccessMsg && (
                <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-800 flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>{cloudSuccessMsg}</span>
                </div>
              )}

              {cloudErrorMsg && (
                <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
                  <span>{cloudErrorMsg}</span>
                </div>
              )}

              {/* Cloud Status Banner */}
              <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 flex flex-wrap items-center justify-between gap-3 text-xs">
                <div className="flex items-center gap-2">
                  <Server className="w-4 h-4 text-slate-500" />
                  <span className="font-semibold text-slate-700">Trạng thái máy chủ:</span>
                  {cloudStatus?.isRunning ? (
                    <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 font-medium flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping" />
                      Đang cào ngầm (Run #{cloudStatus?.latestRun?.runNumber})
                    </span>
                  ) : (
                    <span className="px-2 py-0.5 rounded-full bg-slate-200 text-slate-700 font-medium">
                      Sẵn sàng nhận lệnh
                    </span>
                  )}
                </div>

                {cloudStatus?.latestRun && (
                  <div className="flex items-center gap-3 text-slate-500">
                    <span>Lần chạy gần nhất: {new Date(cloudStatus.latestRun.createdAt).toLocaleTimeString('vi-VN')}</span>
                    <a
                      href={cloudStatus.latestRun.htmlUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="text-blue-600 hover:underline flex items-center gap-1"
                    >
                      <span>Xem tiến trình</span>
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 2: DOCUMENTS */}
          {activeSourceTab === 'documents' && (
            <div className="space-y-4">
              <div
                className="border-2 border-dashed border-slate-200 hover:border-blue-400 bg-slate-50/50 rounded-2xl p-8 text-center transition cursor-pointer"
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
                <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center mx-auto mb-2 border border-blue-100">
                  <FileText className="w-5 h-5" />
                </div>
                {selectedFile ? (
                  <div>
                    <p className="text-sm font-semibold text-slate-800">{selectedFile.name}</p>
                    <p className="text-xs text-slate-500 mt-0.5">
                      {(selectedFile.size / 1024).toFixed(1)} KB • Nhấn để thay đổi tệp
                    </p>
                  </div>
                ) : (
                  <div>
                    <p className="text-sm font-semibold text-slate-800">
                      Chọn hoặc kéo thả tệp PDF / DOCX / TXT vào đây
                    </p>
                    <p className="text-xs text-slate-500 mt-1">
                      Hỗ trợ đọc văn bản và bảng biểu tự động
                    </p>
                  </div>
                )}
              </div>

              <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                <label className="flex items-center gap-2 cursor-pointer select-none text-xs text-slate-600">
                  <input
                    type="checkbox"
                    checked={enableVisionOcr}
                    onChange={(e) => setEnableVisionOcr(e.target.checked)}
                    className="rounded border-slate-300 text-blue-600 focus:ring-0"
                  />
                  <span>Nhận diện điểm ảnh &amp; bảng biểu qua Gemini Vision</span>
                </label>

                <button
                  onClick={handleUploadDocument}
                  disabled={!selectedFile || isProcessingDoc}
                  className="px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs flex items-center gap-2 transition disabled:opacity-50 shadow-sm"
                >
                  {isProcessingDoc ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>Đang phân tích &amp; nạp...</span>
                    </>
                  ) : (
                    <>
                      <Eye className="w-3.5 h-3.5" />
                      <span>Phân Tích &amp; Nạp Vào Supabase</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          )}
        </section>

        {/* 2. RESULTS & KNOWLEDGE SECTION */}
        <section className="bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden flex flex-col min-h-[460px]">
          {/* Sub Navigation Bar */}
          <div className="flex items-center justify-between border-b border-slate-200 px-4 py-2 bg-slate-50/50">
            <div className="flex items-center gap-1.5">
              <button
                onClick={() => setActiveBottomTab('query')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                  activeBottomTab === 'query'
                    ? 'bg-white text-blue-700 border border-slate-200 shadow-sm'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                <Search className="w-3.5 h-3.5 text-blue-600" />
                <span>Hỏi Đáp RAG Sandbox</span>
              </button>

              <button
                onClick={() => {
                  setActiveBottomTab('supabase');
                  fetchStats();
                }}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                  activeBottomTab === 'supabase'
                    ? 'bg-white text-emerald-700 border border-slate-200 shadow-sm'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                <Database className="w-3.5 h-3.5 text-emerald-600" />
                <span>Kho Dữ Liệu Supabase ({dbStats.totalChunks})</span>
              </button>

              <button
                onClick={() => setActiveBottomTab('logs')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                  activeBottomTab === 'logs'
                    ? 'bg-white text-slate-800 border border-slate-200 shadow-sm'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                <Terminal className="w-3.5 h-3.5 text-slate-500" />
                <span>Nhật Ký Xử Lý ({logEntries.length})</span>
              </button>
            </div>

            <div className="text-[11px] text-slate-500 font-medium">
              Vector: <span className="font-semibold text-slate-700">3072 chiều (Vilao AI)</span>
            </div>
          </div>

          {/* TAB 1: RAG QUERY SANDBOX */}
          {activeBottomTab === 'query' && (
            <div className="p-5 flex-1 flex flex-col space-y-4">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={queryInput}
                  onChange={(e) => setQueryInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleRunQuery()}
                  placeholder="Nhập câu hỏi để kiểm tra dữ liệu trong Supabase (Ví dụ: Thẻ tín dụng MB ưu đãi gì?)..."
                  className="flex-1 bg-white border border-slate-200 rounded-xl px-4 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                />
                <button
                  onClick={handleRunQuery}
                  disabled={isQuerying || !queryInput.trim()}
                  className="px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs flex items-center gap-1.5 disabled:opacity-50 transition shadow-sm"
                >
                  {isQuerying ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                  <span>Hỏi AI &amp; Tìm Kiếm</span>
                </button>
              </div>

              {queryResult ? (
                <div className="space-y-4 mt-2">
                  <div className="p-4 rounded-xl bg-blue-50/60 border border-blue-200">
                    <div className="flex items-center gap-1.5 text-xs font-bold text-blue-800 uppercase tracking-wide mb-1.5">
                      <Sparkles className="w-4 h-4 text-blue-600" />
                      <span>Câu trả lời tổng hợp (RAG Grounded):</span>
                    </div>
                    <p className="text-sm text-slate-800 leading-relaxed whitespace-pre-wrap">
                      {queryResult.answer}
                    </p>
                  </div>

                  <div>
                    <h3 className="text-xs font-semibold text-slate-600 uppercase mb-2">
                      Đoạn trích dẫn đối sánh từ Supabase:
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {queryResult.matchedChunks.map((doc, i) => (
                        <div key={doc.id || i} className="p-3.5 bg-slate-50 border border-slate-200 rounded-xl text-xs space-y-1.5">
                          <div className="flex items-center justify-between font-medium">
                            <span className="text-slate-800 font-semibold truncate max-w-[220px]">
                              {doc.metadata?.title || doc.metadata?.heading || 'Tài liệu'}
                            </span>
                            <span className="px-2 py-0.5 rounded bg-blue-100 text-blue-700 text-[11px]">
                              {doc.similarity ? (doc.similarity * 100).toFixed(0) + '% match' : 'Top Match'}
                            </span>
                          </div>
                          <p className="text-slate-600 text-xs line-clamp-4 leading-relaxed bg-white p-2.5 rounded-lg border border-slate-200/80">
                            {doc.content}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="py-16 text-center text-slate-400">
                  <Search className="w-8 h-8 mx-auto mb-2 text-slate-300" />
                  <p className="text-xs">Nhập câu hỏi để tìm kiếm ngữ nghĩa và xem câu trả lời được sinh từ Supabase.</p>
                </div>
              )}
            </div>
          )}

          {/* TAB 2: SUPABASE KNOWLEDGE REPOSITORY */}
          {activeBottomTab === 'supabase' && (
            <div className="p-4 flex-1 flex flex-col space-y-3">
              <div className="flex items-center justify-between text-xs text-slate-500">
                <span>15 Bản ghi mới nhất trong <code>public.documents</code>:</span>
                <span className="font-medium text-emerald-600">Supabase Connected</span>
              </div>

              <div className="border border-slate-200 rounded-xl overflow-hidden bg-white">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-200">
                    <tr>
                      <th className="p-2.5">ID</th>
                      <th className="p-2.5">Tiêu đề</th>
                      <th className="p-2.5">Loại</th>
                      <th className="p-2.5">Nội dung trích đoạn</th>
                      <th className="p-2.5">Thời gian</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-xs">
                    {dbStats.recentRecords.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="p-8 text-center text-slate-400">
                          Chưa có dữ liệu nào. Hãy kích hoạt cào hoặc nạp tệp để lưu vào Supabase.
                        </td>
                      </tr>
                    ) : (
                      dbStats.recentRecords.map((rec) => (
                        <tr key={rec.id} className="hover:bg-slate-50 transition">
                          <td className="p-2.5 font-semibold text-blue-600">#{rec.id}</td>
                          <td className="p-2.5 font-medium text-slate-800 max-w-[200px] truncate">
                            {rec.metadata?.heading || rec.metadata?.title || 'Tài liệu'}
                          </td>
                          <td className="p-2.5">
                            <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 text-[11px]">
                              {rec.metadata?.type || 'web'}
                            </span>
                          </td>
                          <td className="p-2.5 text-slate-600 max-w-[320px] truncate">
                            {rec.content}
                          </td>
                          <td className="p-2.5 text-slate-400 whitespace-nowrap">
                            {rec.metadata?.created_at ? new Date(rec.metadata.created_at).toLocaleTimeString('vi-VN') : 'Gần đây'}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB 3: LOGS & CONSOLE */}
          {activeBottomTab === 'logs' && (
            <div className="p-4 flex-1 flex flex-col space-y-3">
              {progressMessage && (
                <div className="p-3 rounded-xl bg-slate-100 border border-slate-200 text-xs text-slate-700 flex items-center justify-between">
                  <span>{progressMessage}</span>
                  <span className="font-semibold text-blue-600">{progressPercent}%</span>
                </div>
              )}

              <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden font-mono flex flex-col flex-1 shadow-inner">
                <div className="flex items-center justify-between px-3 py-1.5 bg-slate-950 border-b border-slate-800 text-xs text-slate-400">
                  <div className="flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-rose-500/80" />
                    <span className="w-2.5 h-2.5 rounded-full bg-amber-500/80" />
                    <span className="w-2.5 h-2.5 rounded-full bg-emerald-500/80" />
                    <span className="ml-2 text-[11px]">Console Logs</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => {
                        const text = logEntries.map((l) => `[${l.timestamp}] [${l.tag}] ${l.message}`).join('\n');
                        navigator.clipboard.writeText(text);
                      }}
                      className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px] transition"
                    >
                      Copy Logs
                    </button>
                    <button
                      onClick={() => setLogEntries([])}
                      className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px] transition"
                    >
                      Xóa
                    </button>
                  </div>
                </div>

                <div className="p-3 space-y-1 max-h-[360px] overflow-y-auto text-xs leading-relaxed">
                  {logEntries.length === 0 ? (
                    <div className="py-12 text-center text-slate-500">
                      Chưa có nhật ký nào. Hãy nạp tài liệu để xem tiến trình.
                    </div>
                  ) : (
                    logEntries.map((l, i) => (
                      <div key={i} className="flex items-start gap-2 text-slate-300">
                        <span className="text-slate-500 shrink-0 text-[11px]">[{l.timestamp}]</span>
                        <span className="text-blue-400 font-semibold shrink-0">[{l.tag}]</span>
                        <span className={l.type === 'error' ? 'text-rose-400 font-medium' : l.type === 'success' ? 'text-emerald-400' : 'text-slate-300'}>
                          {l.message}
                        </span>
                      </div>
                    ))
                  )}
                  <div ref={streamEndRef} />
                </div>
              </div>
            </div>
          )}
        </section>
      </div>

      {/* Clean Footer */}
      <footer className="border-t border-slate-200 bg-white py-3.5 px-6 text-center text-xs text-slate-500 flex flex-wrap items-center justify-between gap-2 mt-8">
        <div>
          <span>ABF Enterprise Knowledge Platform</span>
        </div>
        <div className="flex items-center gap-4 text-[11px]">
          <span>Supabase pgvector (3072D)</span>
          <span>•</span>
          <span>GitHub Actions Cloud Runner</span>
          <span>•</span>
          <span>Vercel Edge</span>
        </div>
      </footer>
    </main>
  );
}
