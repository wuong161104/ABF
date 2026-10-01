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
  Cloud,
  Play,
  ExternalLink,
  Clock,
  Server,
  Layers,
  Send,
  Trash2,
  ShieldCheck,
  ChevronRight,
  Info
} from 'lucide-react';
import { CrawledChunk } from '@/lib/types';

interface LogEntry {
  timestamp: string;
  tag: string;
  message: string;
  type: 'info' | 'success' | 'warn' | 'error';
}

export default function Home() {
  // Navigation: Data Source tab
  const [activeSourceTab, setActiveSourceTab] = useState<'cloud' | 'documents'>('cloud');

  // Cloud Crawler state
  const [targetUrl, setTargetUrl] = useState('https://mbbank.com.vn/');
  const [cloudMaxPages, setCloudMaxPages] = useState('0'); // '0' = all sitemap
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
  const [progressPercent, setProgressPercent] = useState<number>(0);
  const [progressMessage, setProgressMessage] = useState<string>('');

  // Logs & sync chunks
  const [logEntries, setLogEntries] = useState<LogEntry[]>([
    {
      timestamp: new Date().toLocaleTimeString('vi-VN'),
      tag: 'SYSTEM',
      message: 'ABF Knowledge Studio sẵn sàng hoạt động. Kết nối Supabase pgvector 3072D.',
      type: 'info',
    },
  ]);

  // Supabase stats
  const [dbStats, setDbStats] = useState({ totalChunks: 0, recentRecords: [] as any[] });
  const [isLoadingStats, setIsLoadingStats] = useState(false);

  // RAG Query Sandbox
  const [queryInput, setQueryInput] = useState('');
  const [isQuerying, setIsQuerying] = useState(false);
  const [queryResult, setQueryResult] = useState<{ answer: string; matchedChunks: any[] } | null>(null);

  const streamEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Initial load + interval polling
  useEffect(() => {
    fetchStats();
    fetchCloudStatus();
    const interval = setInterval(() => {
      fetchCloudStatus();
      fetchStats();
    }, 12000);
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
      setLogEntries((prev) => [
        ...prev,
        {
          timestamp: new Date().toLocaleTimeString('vi-VN'),
          tag: 'CLOUD_TRIGGER',
          message: `Đã kích hoạt Cloud Runner cho ${targetUrl} (Run #${data.runId || 'mới'})`,
          type: 'success',
        },
      ]);
      fetchCloudStatus();
      fetchStats();
    } catch (err: any) {
      setCloudErrorMsg(err.message);
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
      console.error('Lỗi nạp thống kê Supabase:', e);
    } finally {
      setIsLoadingStats(false);
    }
  };

  const handleUploadDocument = async () => {
    if (!selectedFile) return;
    setIsProcessingDoc(true);
    setProgressPercent(20);
    setProgressMessage(`Đang đọc tệp ${selectedFile.name}...`);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('enableVisionOcr', String(enableVisionOcr));

      setLogEntries((prev) => [
        ...prev,
        {
          timestamp: new Date().toLocaleTimeString('vi-VN'),
          tag: 'INGEST',
          message: `Nạp tệp ${selectedFile.name} (${(selectedFile.size / 1024).toFixed(1)} KB)...`,
          type: 'info',
        },
      ]);

      const resp = await fetch('/api/ingest', {
        method: 'POST',
        body: formData,
      });

      const responseText = await resp.text();
      let result: any;
      try {
        result = JSON.parse(responseText);
      } catch {
        throw new Error(`Máy chủ phản hồi không hợp lệ (${resp.status}): ${responseText.slice(0, 150)}`);
      }

      if (!resp.ok || !result.success) {
        throw new Error(result.error || `Lỗi xử lý tài liệu (mã ${resp.status})`);
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

      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
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

  const handleRunQuery = async (customPrompt?: string) => {
    const q = customPrompt !== undefined ? customPrompt : queryInput;
    if (!q.trim()) return;
    if (customPrompt) setQueryInput(customPrompt);

    setIsQuerying(true);
    try {
      const resp = await fetch('/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q.trim() }),
      });
      const data = await resp.json();
      if (data.success) {
        setQueryResult({
          answer: data.answer,
          matchedChunks: data.matchedChunks || [],
        });
        setLogEntries((prev) => [
          ...prev,
          {
            timestamp: new Date().toLocaleTimeString('vi-VN'),
            tag: 'RAG_QUERY',
            message: `Hỏi đáp RAG thành công (${data.matchedChunks?.length || 0} chunks khớp)`,
            type: 'info',
          },
        ]);
      } else {
        throw new Error(data.error || 'Không thể truy vấn RAG');
      }
    } catch (err: any) {
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
      setIsQuerying(false);
    }
  };

  const sampleQuestions = [
    'Thẻ tín dụng VPBank MWG hoàn tiền bao nhiêu %?',
    'Điều kiện mở thẻ tín dụng VIB Online Plus?',
    'Biểu phí thường niên thẻ tín dụng MBBank?',
  ];

  return (
    <div className="min-h-screen bg-[#F8FAFC] text-slate-900 font-sans selection:bg-blue-100 selection:text-blue-900 flex flex-col">
      {/* 1. KHỐI HEADER + KPIS HỆ THỐNG GHIM TRÊN CÙNG */}
      <header className="sticky top-0 z-40 bg-white/95 backdrop-blur-sm border-b border-slate-200/80 px-4 sm:px-6 lg:px-8 py-3.5 shadow-sm">
        <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-4">
          
          {/* Logo & Tiêu đề */}
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-blue-600 flex items-center justify-center text-white shadow-sm shadow-blue-500/25">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-base font-bold tracking-tight text-slate-900">ABF Knowledge Studio</h1>
                <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200/80">
                  RAG 3072D
                </span>
              </div>
              <p className="text-xs text-slate-500">Trung tâm thu thập dữ liệu & kiểm thử RAG Thẻ Ngân Hàng</p>
            </div>
          </div>

          {/* 3 Thẻ Chỉ Số Nhanh (System KPIs) */}
          <div className="flex items-center gap-4 text-xs">
            {/* KPI 1: Cloud Runner */}
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-50 border border-slate-200/80">
              <span className={`w-2 h-2 rounded-full ${
                cloudStatus?.latestRun?.status === 'in_progress' ? 'bg-amber-500 animate-pulse' : 'bg-emerald-500'
              }`}></span>
              <span className="text-slate-500">Cloud Runner:</span>
              <span className="font-semibold text-slate-800">
                {cloudStatus?.latestRun ? `Run #${cloudStatus.latestRun.runNumber}` : 'Sẵn sàng'}
              </span>
            </div>

            {/* KPI 2: Supabase Chunks */}
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-50 border border-slate-200/80">
              <Database className="w-3.5 h-3.5 text-blue-600" />
              <span className="text-slate-500">Supabase:</span>
              <span className="font-semibold text-slate-800">
                {dbStats.totalChunks.toLocaleString()} Chunks
              </span>
            </div>

            {/* KPI 3: Gemini Vision Model */}
            <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-50 border border-slate-200/80">
              <Sparkles className="w-3.5 h-3.5 text-amber-500" />
              <span className="text-slate-500">Model:</span>
              <span className="font-semibold text-slate-800">Gemini 1.5 Flash Vision</span>
            </div>
          </div>

        </div>
      </header>

      {/* 2. KHÔNG GIAN LÀM VIỆC CHÍNH (LAYOUT 2 CỘT SPLIT WORKBENCH) */}
      <main className="max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-6 flex-1">
        <div className="grid grid-cols-12 gap-6 items-start">

          {/* ==================== CỘT TRÁI: DATA INGESTION HUB (5 CỘT) ==================== */}
          <div className="col-span-12 lg:col-span-5 space-y-5">
            
            {/* Khối Nguồn Dữ Liệu */}
            <section className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm space-y-4">
              
              {/* Header Khối & Tab chuyển đổi */}
              <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                <span className="font-semibold text-sm text-slate-800 flex items-center gap-2">
                  <Cloud className="w-4 h-4 text-blue-600" /> Nạp Dữ Liệu Ngân Hàng
                </span>
                
                {/* Segmented Control */}
                <div className="inline-flex bg-slate-100 p-0.5 rounded-lg text-xs">
                  <button
                    onClick={() => setActiveSourceTab('cloud')}
                    className={`px-3 py-1.5 rounded-md font-medium transition-all ${
                      activeSourceTab === 'cloud'
                        ? 'bg-white text-slate-900 shadow-sm font-semibold'
                        : 'text-slate-500 hover:text-slate-800'
                    }`}
                  >
                    Cloud Crawler
                  </button>
                  <button
                    onClick={() => setActiveSourceTab('documents')}
                    className={`px-3 py-1.5 rounded-md font-medium transition-all ${
                      activeSourceTab === 'documents'
                        ? 'bg-white text-slate-900 shadow-sm font-semibold'
                        : 'text-slate-500 hover:text-slate-800'
                    }`}
                  >
                    Tài Liệu PDF / OCR
                  </button>
                </div>
              </div>

              {/* TAB 1: CLOUD CRAWLER */}
              {activeSourceTab === 'cloud' && (
                <div className="space-y-4 pt-1">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                      URL Ngân hàng / Website mục tiêu
                    </label>
                    <input
                      type="url"
                      value={targetUrl}
                      onChange={(e) => setTargetUrl(e.target.value)}
                      placeholder="https://mbbank.com.vn/"
                      className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2.5 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                        Giới hạn trang (0 = tất cả)
                      </label>
                      <input
                        type="number"
                        min="0"
                        value={cloudMaxPages}
                        onChange={(e) => setCloudMaxPages(e.target.value)}
                        className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                        Chế độ cào
                      </label>
                      <select
                        value={cloudForceRecrawl ? 'force' : 'incremental'}
                        onChange={(e) => setCloudForceRecrawl(e.target.value === 'force')}
                        className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                      >
                        <option value="incremental">Quét bài mới (Incremental)</option>
                        <option value="force">Cào lại toàn bộ (Recrawl)</option>
                      </select>
                    </div>
                  </div>

                  {/* Nút Kích Hoạt Cào Ngầm */}
                  <button
                    onClick={handleTriggerCloudCrawler}
                    disabled={isTriggeringCloud || !targetUrl}
                    className="w-full py-2.5 px-4 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white rounded-xl text-xs font-semibold flex items-center justify-center gap-2 shadow-sm shadow-blue-500/20 transition-all cursor-pointer"
                  >
                    {isTriggeringCloud ? (
                      <>
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Đang gửi lệnh Cloud Runner...
                      </>
                    ) : (
                      <>
                        <Play className="w-3.5 h-3.5 fill-white" /> Kích Hoạt Cào Ngầm Trên Cloud
                      </>
                    )}
                  </button>

                  {/* Thông báo kết quả Cloud Trigger */}
                  {cloudSuccessMsg && (
                    <div className="p-3 bg-emerald-50 border border-emerald-200/80 rounded-xl text-xs text-emerald-800 flex items-start gap-2">
                      <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                      <span>{cloudSuccessMsg}</span>
                    </div>
                  )}
                  {cloudErrorMsg && (
                    <div className="p-3 bg-red-50 border border-red-200/80 rounded-xl text-xs text-red-800 flex items-start gap-2">
                      <AlertCircle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
                      <span>{cloudErrorMsg}</span>
                    </div>
                  )}

                  {/* Thông tin Runner lần chạy gần nhất */}
                  {cloudStatus?.latestRun && (
                    <div className="p-3.5 bg-slate-50 border border-slate-200/80 rounded-xl text-xs space-y-2">
                      <div className="flex justify-between items-center">
                        <span className="text-slate-500">Tiến trình gần nhất:</span>
                        <a
                          href={cloudStatus.latestRun.url}
                          target="_blank"
                          rel="noreferrer"
                          className="font-semibold text-blue-600 hover:underline flex items-center gap-1"
                        >
                          Run #{cloudStatus.latestRun.runNumber} <ExternalLink className="w-3 h-3" />
                        </a>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-slate-500">Trạng thái:</span>
                        <span className={`font-semibold capitalize ${
                          cloudStatus.latestRun.status === 'completed'
                            ? 'text-emerald-700'
                            : cloudStatus.latestRun.status === 'in_progress'
                            ? 'text-amber-600'
                            : 'text-slate-700'
                        }`}>
                          {cloudStatus.latestRun.status === 'completed' ? 'Hoàn thành' : 'Đang xử lý ngầm...'}
                        </span>
                      </div>
                      {cloudStatus.latestRun.conclusion && (
                        <div className="flex justify-between items-center">
                          <span className="text-slate-500">Kết luận:</span>
                          <span className="font-semibold text-slate-800 uppercase text-[11px]">
                            {cloudStatus.latestRun.conclusion}
                          </span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* TAB 2: TÀI LIỆU PDF / VISION OCR */}
              {activeSourceTab === 'documents' && (
                <div className="space-y-4 pt-1">
                  <div
                    onClick={() => fileInputRef.current?.click()}
                    className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all ${
                      selectedFile
                        ? 'border-blue-500 bg-blue-50/50'
                        : 'border-slate-200 hover:border-slate-300 bg-slate-50/60'
                    }`}
                  >
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".pdf,.txt,.md"
                      onChange={(e) => {
                        if (e.target.files && e.target.files[0]) {
                          setSelectedFile(e.target.files[0]);
                        }
                      }}
                      className="hidden"
                    />
                    <FileUp className="w-8 h-8 text-blue-600 mx-auto mb-2" />
                    {selectedFile ? (
                      <div>
                        <div className="text-xs font-bold text-slate-800">{selectedFile.name}</div>
                        <div className="text-[11px] text-slate-500 mt-0.5">
                          {(selectedFile.size / 1024).toFixed(1)} KB — Sẵn sàng nạp
                        </div>
                      </div>
                    ) : (
                      <div>
                        <div className="text-xs font-semibold text-slate-700">Kéo thả hoặc click để chọn tệp</div>
                        <div className="text-[11px] text-slate-400 mt-0.5">
                          Hỗ trợ thể lệ PDF, điều khoản hoàn tiền, text scan
                        </div>
                      </div>
                    )}
                  </div>

                  <div className="flex items-center justify-between text-xs">
                    <label className="flex items-center gap-2 text-slate-700 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={enableVisionOcr}
                        onChange={(e) => setEnableVisionOcr(e.target.checked)}
                        className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                      />
                      <span>Bóc tách thị giác Gemini Vision OCR</span>
                    </label>
                  </div>

                  {/* Tiến độ upload */}
                  {isProcessingDoc && (
                    <div className="space-y-1.5">
                      <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
                        <div
                          className="bg-blue-600 h-full transition-all duration-300"
                          style={{ width: `${progressPercent}%` }}
                        ></div>
                      </div>
                      <p className="text-[11px] text-slate-500 text-center font-medium">{progressMessage}</p>
                    </div>
                  )}

                  <button
                    onClick={handleUploadDocument}
                    disabled={isProcessingDoc || !selectedFile}
                    className="w-full py-2.5 px-4 bg-slate-900 hover:bg-slate-800 disabled:bg-slate-300 text-white rounded-xl text-xs font-semibold flex items-center justify-center gap-2 shadow-sm transition-all cursor-pointer"
                  >
                    {isProcessingDoc ? (
                      <>
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Đang phân tích PDF...
                      </>
                    ) : (
                      <>
                        <Sparkles className="w-3.5 h-3.5 text-amber-400" /> Bắt Đầu Nạp Vào Supabase
                      </>
                    )}
                  </button>
                </div>
              )}

            </section>

            {/* Khối Nhật Ký Hoạt Động (Live Terminal Console) */}
            <section className="bg-slate-900 border border-slate-800 rounded-2xl p-4 shadow-sm space-y-2 text-xs font-mono">
              <div className="flex items-center justify-between border-b border-slate-800 pb-2 text-[11px]">
                <span className="flex items-center gap-1.5 text-slate-400 font-semibold">
                  <Terminal className="w-3.5 h-3.5 text-blue-400" /> Nhật Ký Xử Lý Live
                </span>
                <button
                  onClick={() => setLogEntries([])}
                  className="text-slate-500 hover:text-slate-300 text-[11px] flex items-center gap-1"
                >
                  <Trash2 className="w-3 h-3" /> Xóa
                </button>
              </div>

              <div className="max-h-44 overflow-y-auto space-y-1.5 pr-1 text-[11px] scrollbar-thin">
                {logEntries.map((log, idx) => (
                  <div key={idx} className="flex items-start gap-2 leading-relaxed">
                    <span className="text-slate-500 shrink-0">[{log.timestamp}]</span>
                    <span className={`px-1 rounded text-[10px] uppercase font-bold shrink-0 ${
                      log.type === 'error'
                        ? 'bg-red-950 text-red-400'
                        : log.type === 'success'
                        ? 'bg-emerald-950 text-emerald-400'
                        : 'bg-slate-800 text-blue-400'
                    }`}>
                      {log.tag}
                    </span>
                    <span className={`break-words ${
                      log.type === 'error' ? 'text-red-300' : log.type === 'success' ? 'text-emerald-300' : 'text-slate-300'
                    }`}>
                      {log.message}
                    </span>
                  </div>
                ))}
                <div ref={streamEndRef} />
              </div>
            </section>

          </div>

          {/* ==================== CỘT PHẢI: RAG PLAYGROUND & SUPABASE INSPECTOR (7 CỘT) ==================== */}
          <div className="col-span-12 lg:col-span-7 space-y-5">
            
            {/* Khối Sân Thử Nghiệm Truy Vấn RAG */}
            <section className="bg-white border border-slate-200 rounded-2xl p-5 sm:p-6 shadow-sm space-y-4">
              <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                <div>
                  <h2 className="font-semibold text-sm text-slate-900 flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-blue-600" /> RAG Query Sandbox (Kiểm Thử Hỏi Đáp)
                  </h2>
                  <p className="text-xs text-slate-500 mt-0.5">Đặt câu hỏi để kiểm tra độ chính xác và trích dẫn nguồn của AI</p>
                </div>
                <span className="text-[11px] font-medium px-2 py-0.5 rounded bg-slate-100 text-slate-600">
                  Cosine Similarity
                </span>
              </div>

              {/* Ô Nhập Câu Hỏi */}
              <div className="space-y-2.5">
                <div className="relative">
                  <input
                    type="text"
                    value={queryInput}
                    onChange={(e) => setQueryInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleRunQuery()}
                    placeholder="Nhập câu hỏi về ưu đãi thẻ tín dụng, điều kiện hoàn tiền..."
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-4 pr-24 py-3 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all"
                  />
                  <button
                    onClick={() => handleRunQuery()}
                    disabled={isQuerying || !queryInput.trim()}
                    className="absolute right-2 top-2 px-3.5 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 shadow-sm transition-all cursor-pointer"
                  >
                    {isQuerying ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                    <span>Hỏi</span>
                  </button>
                </div>

                {/* Gợi Ý Câu Hỏi Mẫu */}
                <div className="flex flex-wrap items-center gap-1.5 text-xs">
                  <span className="text-slate-400 text-[11px]">Gợi ý:</span>
                  {sampleQuestions.map((sq, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleRunQuery(sq)}
                      className="px-2.5 py-1 rounded-lg bg-slate-50 hover:bg-blue-50 text-slate-600 hover:text-blue-700 border border-slate-200/80 hover:border-blue-200 text-[11px] transition-all cursor-pointer"
                    >
                      {sq}
                    </button>
                  ))}
                </div>
              </div>

              {/* Hộp Hiển Thị Kết Quả RAG */}
              {queryResult && (
                <div className="p-4 bg-slate-50 border border-slate-200/90 rounded-xl space-y-3.5 animate-in fade-in duration-200">
                  <div className="flex items-center justify-between border-b border-slate-200/70 pb-2">
                    <span className="text-xs font-bold text-slate-900 flex items-center gap-1.5">
                      <Sparkles className="w-3.5 h-3.5 text-amber-500" /> Câu Trả Lời Của Bot RAG
                    </span>
                    <span className="text-[11px] text-slate-400 font-mono">Top-k: {queryResult.matchedChunks?.length || 0} Chunks</span>
                  </div>

                  {/* Nội dung câu trả lời */}
                  <div className="text-xs text-slate-800 leading-relaxed whitespace-pre-wrap">
                    {queryResult.answer}
                  </div>

                  {/* Danh Sách Nguồn Trích Dẫn (Citations) */}
                  {queryResult.matchedChunks && queryResult.matchedChunks.length > 0 && (
                    <div className="border-t border-slate-200/80 pt-3 space-y-2">
                      <div className="text-[11px] font-semibold text-slate-600 flex items-center gap-1">
                        <CheckCircle2 className="w-3 h-3 text-emerald-600" /> Nguồn trích dẫn đối chiếu từ Supabase:
                      </div>
                      <div className="space-y-1.5">
                        {queryResult.matchedChunks.map((chunk, cIdx) => (
                          <div key={cIdx} className="p-2.5 bg-white border border-slate-200 rounded-lg text-xs space-y-1">
                            <div className="flex justify-between items-center font-medium text-slate-800">
                              <span className="truncate max-w-sm text-[11px] text-blue-700">
                                📄 {chunk.metadata?.title || chunk.metadata?.fileName || 'Tài liệu'}
                              </span>
                              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 font-bold border border-emerald-200">
                                Sim: {(chunk.similarity ? (chunk.similarity * 100).toFixed(1) : '90')}%
                              </span>
                            </div>
                            <p className="text-[11px] text-slate-600 line-clamp-2 italic">
                              "{chunk.content}"
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </section>

            {/* Khối Thanh Tra Dữ Liệu Supabase (Vector Inspector) */}
            <section className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm space-y-3">
              <div className="flex items-center justify-between border-b border-slate-100 pb-2.5">
                <div className="flex items-center gap-2">
                  <Database className="w-4 h-4 text-blue-600" />
                  <h3 className="font-semibold text-sm text-slate-900">
                    Bản Ghi Supabase Mới Nhất ({dbStats.totalChunks.toLocaleString()} đoạn)
                  </h3>
                </div>
                <button
                  onClick={fetchStats}
                  disabled={isLoadingStats}
                  className="text-xs text-slate-500 hover:text-slate-900 flex items-center gap-1 px-2.5 py-1 rounded bg-slate-50 border border-slate-200 transition-all cursor-pointer"
                >
                  <RefreshCw className={`w-3 h-3 ${isLoadingStats ? 'animate-spin' : ''}`} />
                  <span>Làm mới</span>
                </button>
              </div>

              {/* Bảng Dữ Liệu */}
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-slate-200 text-slate-500 text-[11px]">
                      <th className="py-2.5 px-2 font-medium">Tiêu đề / Nguồn</th>
                      <th className="py-2.5 px-2 font-medium">Nội dung tóm tắt</th>
                      <th className="py-2.5 px-2 font-medium">Vector</th>
                      <th className="py-2.5 px-2 font-medium">Thời gian</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-slate-700">
                    {dbStats.recentRecords.length > 0 ? (
                      dbStats.recentRecords.map((rec, rIdx) => (
                        <tr key={rIdx} className="hover:bg-slate-50/80 transition-colors">
                          <td className="py-2.5 px-2 font-medium text-slate-800 max-w-[160px] truncate" title={rec.title || rec.source_url}>
                            {rec.title || rec.source_url || 'Bản ghi không tên'}
                          </td>
                          <td className="py-2.5 px-2 text-slate-500 max-w-[240px] truncate" title={rec.content}>
                            {rec.content}
                          </td>
                          <td className="py-2.5 px-2 font-mono text-[11px] text-blue-600">
                            3072D
                          </td>
                          <td className="py-2.5 px-2 text-slate-400 text-[11px] whitespace-nowrap">
                            {rec.created_at ? new Date(rec.created_at).toLocaleTimeString('vi-VN') : 'Vừa xong'}
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={4} className="py-6 text-center text-slate-400 italic">
                          Chưa có bản ghi nào trong Supabase. Hãy kích hoạt cào hoặc nạp tài liệu.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>

          </div>

        </div>
      </main>

      {/* Footer Nhẹ Nhàng */}
      <footer className="border-t border-slate-200/80 bg-white py-3.5 text-center text-xs text-slate-500">
        <p>ABF Knowledge Hub &bull; Thiết kế giao diện theo chuẩn mực <strong>evondevKit ui-ux</strong> &bull; Supabase pgvector</p>
      </footer>
    </div>
  );
}
