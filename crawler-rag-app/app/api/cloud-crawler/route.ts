import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

const GITHUB_REPO = 'wuong161104/ABF';
const WORKFLOW_ID = 'crawler.yml';

// Token resolution purely from secure environment variables
const getGitHubToken = (): string => {
  const envToken = process.env.GITHUB_TOKEN || process.env.GH_TOKEN;
  if (!envToken) {
    throw new Error('Thiếu GITHUB_TOKEN: Vui lòng cấu hình biến môi trường GITHUB_TOKEN.');
  }
  return envToken.trim();
};

/**
 * GET: Lấy trạng thái của các tiến trình Cloud Runner đang chạy ngầm trên GitHub Actions
 */
export async function GET() {
  try {
    const token = getGitHubToken();
    const resp = await fetch(
      `https://api.github.com/repos/${GITHUB_REPO}/actions/workflows/${WORKFLOW_ID}/runs?per_page=5`,
      {
        headers: {
          'User-Agent': 'ABF-Crawler-App',
          Authorization: `Bearer ${token}`,
          Accept: 'application/vnd.github+json',
        },
        cache: 'no-store',
      }
    );

    if (!resp.ok) {
      const errText = await resp.text();
      return NextResponse.json({
        success: false,
        error: `GitHub API error (${resp.status}): ${errText.slice(0, 100)}`,
        isRunning: false,
        runs: [],
      });
    }

    const data = await resp.json();
    const runs = (data.workflow_runs || []).map((r: any) => ({
      id: r.id,
      name: r.name,
      status: r.status, // 'queued' | 'in_progress' | 'completed'
      conclusion: r.conclusion, // 'success' | 'failure' | 'cancelled' | null
      createdAt: r.created_at,
      updatedAt: r.updated_at,
      htmlUrl: r.html_url,
      runNumber: r.run_number,
      actor: r.actor?.login,
      event: r.event,
    }));

    const isRunning = runs.some(
      (r: any) => r.status === 'in_progress' || r.status === 'queued'
    );
    const activeRun = runs.find(
      (r: any) => r.status === 'in_progress' || r.status === 'queued'
    );

    return NextResponse.json({
      success: true,
      isRunning,
      activeRun: activeRun || null,
      latestRun: runs[0] || null,
      runs,
    });
  } catch (err: any) {
    return NextResponse.json({
      success: false,
      error: err.message,
      isRunning: false,
      runs: [],
    });
  }
}

/**
 * POST: Kích hoạt Cloud Runner chạy ngầm trực tiếp trên GitHub Actions (6 tiếng liên tục)
 */
export async function POST(req: NextRequest) {
  try {
    const body = await req.json().catch(() => ({}));
    const {
      targetUrl,
      maxPages = '0', // 0 = cào toàn bộ 100%
      saveToSupabase = true,
      forceRecrawl = false,
    } = body;

    if (!targetUrl || !targetUrl.startsWith('http')) {
      return NextResponse.json(
        { success: false, error: 'Vui lòng cung cấp URL website hợp lệ' },
        { status: 400 }
      );
    }

    const token = getGitHubToken();

    // Trigger workflow_dispatch via GitHub REST API
    const dispatchUrl = `https://api.github.com/repos/${GITHUB_REPO}/actions/workflows/${WORKFLOW_ID}/dispatches`;
    const resp = await fetch(dispatchUrl, {
      method: 'POST',
      headers: {
        'User-Agent': 'ABF-Crawler-App',
        Authorization: `Bearer ${token}`,
        Accept: 'application/vnd.github+json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        ref: 'main',
        inputs: {
          target_url: targetUrl.trim(),
          max_pages: String(maxPages),
          save_to_supabase: Boolean(saveToSupabase),
          force_recrawl: Boolean(forceRecrawl),
        },
      }),
    });

    if (resp.status !== 204) {
      const errText = await resp.text();
      return NextResponse.json(
        {
          success: false,
          error: `Không thể kích hoạt GitHub Actions (${resp.status}): ${errText}`,
        },
        { status: resp.status }
      );
    }

    return NextResponse.json({
      success: true,
      message: `Đã kích hoạt Cloud Runner thành công! Máy chủ đang cào ngầm liên tục (tối đa 6 tiếng) và đồng bộ trực tiếp vào Supabase.`,
      targetUrl,
      maxPages: maxPages === '0' ? 'Toàn bộ website (100%)' : maxPages,
      actionsUrl: `https://github.com/${GITHUB_REPO}/actions/workflows/${WORKFLOW_ID}`,
    });
  } catch (err: any) {
    return NextResponse.json(
      { success: false, error: `Lỗi kích hoạt: ${err.message}` },
      { status: 500 }
    );
  }
}
