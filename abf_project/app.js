/* ==========================================================================
   ABF EXECUTIVE DATA INTELLIGENCE DASHBOARD - APPLICATION LOGIC
   Minimalist Linear/Vercel Design Architecture (taste-skill + minimalist-skill)
   ========================================================================== */

const SUPABASE_URL = "https://azpvcqpnecljsosamnot.supabase.co";
const SUPABASE_ANON_KEY = "sb_publishable_4JgOUmiY71dG8yOAcUoAiw_lMZL8d5r";

let supabaseClient = null;
let rawCommentsData = [];
let insightsData = [];
let chartCategory = null;
let chartBanks = null;

// State Phân Trang & Bộ Lọc
let currentPage = 1;
let pageSize = 10;
let currentModalItem = null;

document.addEventListener('DOMContentLoaded', async () => {
  if (window.lucide) lucide.createIcons();
  initSupabase();
  initSparklines();
  await fetchDashboardData();
  setupRealtimeSubscription();
  setupEventListeners();
  setupModalListeners();
  setupImportModalListeners();
});

function initSupabase() {
  try {
    supabaseClient = supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
    console.log("✅ Supabase Client initialized successfully.");
  } catch (err) {
    console.error("❌ Supabase init error:", err);
  }
}

async function fetchDashboardData() {
  let rawList = [];
  let insightList = [];

  if (supabaseClient) {
    try {
      // Fetch all raw_comments using loop pagination (Supabase PostgREST default cap is 1000 per request)
      let from = 0;
      const step = 1000;
      let hasMoreRaw = true;

      while (hasMoreRaw) {
        const { data: rawChunk, error: rawError } = await supabaseClient
          .from('raw_comments')
          .select('*')
          .order('id', { ascending: false })
          .range(from, from + step - 1);

        if (rawError) {
          console.warn("⚠️ Raw comments fetch error:", rawError);
          break;
        }
        if (rawChunk && rawChunk.length > 0) {
          rawList = rawList.concat(rawChunk);
          if (rawChunk.length < step) {
            hasMoreRaw = false;
          } else {
            from += step;
          }
        } else {
          hasMoreRaw = false;
        }
      }

      // Fetch all insights
      let fromInsight = 0;
      let hasMoreInsight = true;
      while (hasMoreInsight) {
        const { data: insightChunk, error: insightError } = await supabaseClient
          .from('insights')
          .select('*')
          .range(fromInsight, fromInsight + step - 1);

        if (insightError) {
          console.warn("⚠️ Insights fetch error:", insightError);
          break;
        }
        if (insightChunk && insightChunk.length > 0) {
          insightList = insightList.concat(insightChunk);
          if (insightChunk.length < step) {
            hasMoreInsight = false;
          } else {
            fromInsight += step;
          }
        } else {
          hasMoreInsight = false;
        }
      }
    } catch (e) {
      console.warn("⚠️ Cannot query Supabase:", e);
    }
  }

  rawCommentsData = rawList;
  insightsData = insightList;

  populateAllFilterDropdowns();
  updateKPICards();
  renderCharts();
  renderTable();
  if (window.lucide) lucide.createIcons();
}

function populateAllFilterDropdowns() {
  populatePlatformDropdown();
  populateGroupDropdown();
  populateCategoryDropdown();
  populateBankDropdown();
  populateStatusDropdown();
}

function populatePlatformDropdown() {
  const select = document.getElementById('platformFilter');
  if (!select) return;
  const currentVal = select.value;
  const set = new Set();
  rawCommentsData.forEach(c => { if (c.platform) set.add(c.platform.trim()); });

  const map = { tiktok: 'TikTok', facebook: 'Facebook', zalo: 'Zalo Groups' };
  const items = Array.from(set).sort();

  select.innerHTML = `<option value="all">Tất cả Nền tảng (${items.length})</option>`;
  items.forEach(p => {
    const opt = document.createElement('option');
    opt.value = p;
    opt.textContent = map[p] || p;
    select.appendChild(opt);
  });
  if (currentVal && Array.from(select.options).some(o => o.value === currentVal)) select.value = currentVal;
}

function populateGroupDropdown() {
  const select = document.getElementById('groupFilter');
  if (!select) return;
  const currentVal = select.value;
  const set = new Set();
  rawCommentsData.forEach(c => { if (c.group_or_page) set.add(c.group_or_page.trim()); });

  const items = Array.from(set).sort((a, b) => {
    // Ưu tiên các nhóm Zalo lên đầu
    if (a.includes('Zalo') && !b.includes('Zalo')) return -1;
    if (!a.includes('Zalo') && b.includes('Zalo')) return 1;
    return a.localeCompare(b);
  });

  select.innerHTML = `<option value="all">Tất cả Nhóm & Kênh (${items.length})</option>`;
  items.forEach(g => {
    const opt = document.createElement('option');
    opt.value = g;
    // Format hiển thị ngắn gọn đẹp mắt
    let displayLabel = g;
    if (g.includes('Cardfind')) displayLabel = 'Zalo: Cardfind - Làm thẻ tín dụng';
    else if (g.includes('Bào thẻ')) displayLabel = 'Zalo: Bào thẻ thông minh';
    else if (g.includes('baothetindung')) displayLabel = 'TikTok: @baothetindung.abf';
    
    opt.textContent = displayLabel;
    select.appendChild(opt);
  });
  if (currentVal && Array.from(select.options).some(o => o.value === currentVal)) select.value = currentVal;
}

const CANONICAL_CATEGORIES = {
  'mua_sam_online': 'Mua sắm & Hoàn tiền',
  'mua sắm & hoàn tiền': 'Mua sắm & Hoàn tiền',
  'mua sắm online': 'Mua sắm & Hoàn tiền',
  'mua sắm': 'Mua sắm & Hoàn tiền',
  'hoan_tien': 'Mua sắm & Hoàn tiền',
  'hoàn tiền': 'Mua sắm & Hoàn tiền',
  'cashback': 'Mua sắm & Hoàn tiền',
  'han_muc_phi': 'Hạn mức & Biểu phí',
  'hạn mức & biểu phí': 'Hạn mức & Biểu phí',
  'biểu phí': 'Hạn mức & Biểu phí',
  'hạn mức': 'Hạn mức & Biểu phí',
  'mo_the_sang_ngang': 'Mở thẻ & Sang ngang',
  'mở thẻ & sang ngang': 'Mở thẻ & Sang ngang',
  'sang_ngang_the': 'Mở thẻ & Sang ngang',
  'mở & sang ngang thẻ': 'Mở thẻ & Sang ngang',
  'sang ngang thẻ': 'Mở thẻ & Sang ngang',
  'tra_gop': 'Trả góp 0% & Sao kê',
  'trả góp 0% & sao kê': 'Trả góp 0% & Sao kê',
  'trả góp 0%': 'Trả góp 0% & Sao kê',
  'trả góp': 'Trả góp 0% & Sao kê',
  'du_lich': 'Du lịch & Ngoại tệ',
  'du lịch & ngoại tệ': 'Du lịch & Ngoại tệ',
  'du lịch / vé máy bay': 'Du lịch & Ngoại tệ',
  'du lịch': 'Du lịch & Ngoại tệ',
  'an_uong': 'Ẩm thực & Di chuyển',
  'ẩm thực & di chuyển': 'Ẩm thực & Di chuyển',
  'ẩm thực / nhà hàng': 'Ẩm thực & Di chuyển',
  'ẩm thực': 'Ẩm thực & Di chuyển',
  'rut_tien': 'Rút tiền & Đáo hạn POS',
  'rút tiền & đáo hạn pos': 'Rút tiền & Đáo hạn POS',
  'rút tiền & đáo hạn': 'Rút tiền & Đáo hạn POS',
  'rút tiền mặt': 'Rút tiền & Đáo hạn POS',
  'rút tiền': 'Rút tiền & Đáo hạn POS',
  'danh_gia_cskh': 'Đánh giá & Trải nghiệm CSKH',
  'đánh giá & trải nghiệm cskh': 'Đánh giá & Trải nghiệm CSKH',
  'khac': 'Tư vấn & Thắc mắc khác',
  'khác': 'Tư vấn & Thắc mắc khác',
  'tư vấn & thắc mắc khác': 'Tư vấn & Thắc mắc khác'
};

function normalizeCategory(cat) {
  if (!cat) return 'Tư vấn & Thắc mắc khác';
  const k = cat.trim().toLowerCase();
  return CANONICAL_CATEGORIES[k] || 'Tư vấn & Thắc mắc khác';
}

function populateCategoryDropdown() {
  const select = document.getElementById('categoryFilter');
  if (!select) return;
  const currentVal = select.value;

  const categories = [
    'Mua sắm & Hoàn tiền',
    'Hạn mức & Biểu phí',
    'Mở thẻ & Sang ngang',
    'Ẩm thực & Di chuyển',
    'Trả góp 0% & Sao kê',
    'Du lịch & Ngoại tệ',
    'Rút tiền & Đáo hạn POS',
    'Đánh giá & Trải nghiệm CSKH',
    'Tư vấn & Thắc mắc khác'
  ];

  select.innerHTML = `<option value="all">Tất cả Lĩnh Vực Chi Tiêu (${categories.length})</option>`;
  categories.forEach(cat => {
    const opt = document.createElement('option');
    opt.value = cat;
    opt.textContent = cat;
    select.appendChild(opt);
  });
  if (currentVal && Array.from(select.options).some(o => o.value === currentVal)) select.value = currentVal;
}

function normalizeBank(b) {
  if (!b) return null;
  const s = b.trim();
  if (!s || s === '-' || s.toLowerCase() === 'null' || s.toLowerCase() === 'chưa xác định') return null;
  const low = s.toLowerCase();
  if (low === 'mb' || low === 'mb bank' || low === 'mbbank') return 'MB Bank';
  if (low === 'vietinbank' || low === 'vietin') return 'VietinBank';
  if (low === 'vietcombank' || low === 'vcb') return 'Vietcombank';
  if (low === 'shinhan' || low === 'shinhan bank') return 'Shinhan Bank';
  if (low === 'techcom' || low === 'techcombank') return 'Techcombank';
  if (low === 'vp' || low === 'vpbank' || low === 'vp bank') return 'VPBank';
  if (low === 'vib') return 'VIB';
  if (low === 'hsbc') return 'HSBC';
  if (low === 'msb' || low === 'hàng hải') return 'MSB';
  if (low === 'tpbank' || low === 'tp bank' || low === 'tp') return 'TPBank';
  if (low === 'ocb') return 'OCB';
  if (low === 'shb') return 'SHB';
  if (low === 'sacombank') return 'Sacombank';
  if (low === 'eximbank') return 'Eximbank';
  if (low === 'woori bank' || low === 'woori') return 'Woori Bank';
  if (low === 'seabank') return 'SeABank';
  if (low === 'vikki') return 'Vikki';
  if (low === 'hdbank' || low === 'hd bank') return 'HDBank';
  if (low === 'bidv') return 'BIDV';
  if (low === 'acb') return 'ACB';
  if (low === 'nam a bank' || low === 'nam a') return 'Nam A Bank';
  if (low === 'pvcombank') return 'PVcomBank';
  return s;
}

function populateBankDropdown() {
  const select = document.getElementById('bankFilter');
  if (!select) return;
  const currentVal = select.value;
  const set = new Set();

  const mergedList = getMergedCommentsList();
  mergedList.forEach(i => { 
    const b = normalizeBank(i.target_bank);
    if (b) set.add(b); 
  });

  const items = Array.from(set).sort();
  select.innerHTML = `<option value="all">Tất cả Ngân Hàng (${items.length})</option>`;
  items.forEach(b => {
    const opt = document.createElement('option');
    opt.value = b;
    opt.textContent = b;
    select.appendChild(opt);
  });
  if (currentVal && Array.from(select.options).some(o => o.value === currentVal)) select.value = currentVal;
}

function populateStatusDropdown() {
  const select = document.getElementById('statusFilter');
  if (!select) return;
  const currentVal = select.value;
  const set = new Set();
  rawCommentsData.forEach(c => { if (c.status) set.add(c.status.trim()); });

  const statusMap = { processed: 'Processed (Đã xử lý)', pending: 'Pending (Đang chờ)', error: 'Error (Lỗi)' };
  const items = Array.from(set).sort();
  select.innerHTML = `<option value="all">Tất cả Trạng Thái AI (${items.length})</option>`;
  items.forEach(s => {
    const opt = document.createElement('option');
    opt.value = s;
    opt.textContent = statusMap[s] || s;
    select.appendChild(opt);
  });
  if (currentVal && Array.from(select.options).some(o => o.value === currentVal)) select.value = currentVal;
}

function detectBankFromText(content) {
  if (!content) return null;
  const txt = content.toLowerCase();
  if (txt.includes('vib')) return 'VIB';
  if (txt.includes('vpbank') || txt.includes('vp bank')) return 'VPBank';
  if (txt.includes('techcombank') || txt.includes('techcom')) return 'Techcombank';
  if (txt.includes('hsbc')) return 'HSBC';
  if (txt.includes('mb bank') || txt.includes('mbbank') || txt.includes(' mb ')) return 'MB Bank';
  if (txt.includes('shb')) return 'SHB';
  if (txt.includes('vietcombank') || txt.includes('vcb')) return 'Vietcombank';
  if (txt.includes('vietinbank')) return 'VietinBank';
  if (txt.includes('sacombank')) return 'Sacombank';
  if (txt.includes('eximbank')) return 'Eximbank';
  if (txt.includes('msb')) return 'MSB';
  if (txt.includes('shinhan')) return 'Shinhan Bank';
  return null;
}

function detectCategoryFromText(content) {
  if (!content) return 'Tư vấn & Thắc mắc khác';
  const txt = content.toLowerCase();

  if (txt.includes('hạn mức') || txt.includes('hmuc') || txt.includes('phí thường niên') || txt.includes('phí duy trì') || txt.includes('hủy thẻ') || txt.includes('huỷ thẻ') || txt.includes('biểu phí') || txt.includes('lãi suất') || txt.includes('mất phí') || txt.includes('thu phí') || txt.includes('free phí') || txt.includes('0đ') || txt.includes('1tr') || txt.includes('100k') || txt.includes('khoá thẻ') || txt.includes('đóng thẻ')) {
    return 'Hạn mức & Biểu phí';
  }
  if (txt.includes('shopee') || txt.includes('lazada') || txt.includes('tiki') || txt.includes('tiktok shop') || txt.includes('online') || txt.includes('mua sắm') || txt.includes('hoàn tiền') || txt.includes('cashback') || txt.includes('hoàn max') || txt.includes('hoàn 10%') || txt.includes('hoàn 15%') || txt.includes('voucher') || txt.includes('giảm giá') || txt.includes('chào mừng') || txt.includes('được hoàn') || txt.includes('quẹt pos')) {
    return 'Mua sắm & Hoàn tiền';
  }
  if (txt.includes('sang ngang') || txt.includes('mở thẻ') || txt.includes('làm thẻ') || txt.includes('điều kiện') || txt.includes('chứng minh thu nhập') || txt.includes('hồ sơ') || txt.includes('duyệt') || txt.includes('thủ tục') || txt.includes('đk thẻ') || txt.includes('đăng ký thẻ') || txt.includes('phát hành')) {
    return 'Mở thẻ & Sang ngang';
  }
  if (txt.includes('đi ăn') || txt.includes('ăn uống') || txt.includes('nhà hàng') || txt.includes('grab') || txt.includes('be') || txt.includes('food') || txt.includes('shopeefood') || txt.includes('quán ăn') || txt.includes('ẩm thực') || txt.includes('cafe') || txt.includes('phúc long') || txt.includes('starbucks') || txt.includes('giảm 300k') || txt.includes('giảm giá ăn') || txt.includes('vừa ăn') || txt.includes('tính đi aen')) {
    return 'Ẩm thực & Di chuyển';
  }
  if (txt.includes('trả góp') || txt.includes('0%') || txt.includes('sao kê') || txt.includes('kỳ sao kê') || txt.includes('kì sao kê') || txt.includes('chuyển đổi trả góp') || txt.includes('kỳ hạn') || txt.includes('dư nợ') || txt.includes('chu kỳ sao kê')) {
    return 'Trả góp 0% & Sao kê';
  }
  if (txt.includes('du lịch') || txt.includes('du học') || txt.includes('ngoại tệ') || txt.includes('phí ngoại tệ') || txt.includes('tỷ giá') || txt.includes('nước ngoài') || txt.includes('trung quốc') || txt.includes('tq') || txt.includes('hàn') || txt.includes('singapore') || txt.includes('thái') || txt.includes('vé máy bay') || txt.includes('khách sạn') || txt.includes('bay')) {
    return 'Du lịch & Ngoại tệ';
  }
  if (txt.includes('rút tiền') || txt.includes('đáo hạn') || txt.includes('bào thẻ') || txt.includes('rút mặt') || txt.includes('pos rút') || txt.includes('cây atm') || txt.includes('rút pos') || txt.includes('đáo')) {
    return 'Rút tiền & Đáo hạn POS';
  }
  if (txt.includes('chăm sóc') || txt.includes('tổng đài') || txt.includes('nhân viên') || txt.includes('gọi điện') || txt.includes('hỗ trợ') || txt.includes('trải nghiệm') || txt.includes('lừa đảo') || txt.includes('ám ảnh') || txt.includes('né')) {
    return 'Đánh giá & Trải nghiệm CSKH';
  }
  return 'Tư vấn & Thắc mắc khác';
}

function updateKPICards() {
  const total = rawCommentsData.length;
  const tiktokCount = rawCommentsData.filter(c => (c.platform || '').toLowerCase().trim() === 'tiktok').length;
  const fbCount = rawCommentsData.filter(c => (c.platform || '').toLowerCase().trim() === 'facebook').length;
  const zaloCount = rawCommentsData.filter(c => (c.platform || '').toLowerCase().trim() === 'zalo').length;

  animateNumber('metricTotalComments', total);
  animateNumber('metricTiktok', tiktokCount);
  animateNumber('metricFacebook', fbCount);
  animateNumber('metricZalo', zaloCount);
}

function animateNumber(elementId, targetNumber) {
  const el = document.getElementById(elementId);
  if (!el) return;
  
  const currentText = (el.textContent || '0').replace(/\./g, '').replace(/,/g, '');
  const startNumber = parseInt(currentText, 10) || 0;
  
  if (startNumber === targetNumber) {
    el.textContent = targetNumber.toLocaleString('vi-VN');
    return;
  }

  const duration = 600;
  const startTime = performance.now();

  function updateFrame(now) {
    const elapsed = now - startTime;
    const progress = Math.min(elapsed / duration, 1);
    // Ease out quad
    const easeProgress = 1 - (1 - progress) * (1 - progress);
    const currentVal = Math.round(startNumber + (targetNumber - startNumber) * easeProgress);
    el.textContent = currentVal.toLocaleString('vi-VN');

    if (progress < 1) {
      requestAnimationFrame(updateFrame);
    } else {
      el.textContent = targetNumber.toLocaleString('vi-VN');
    }
  }

  requestAnimationFrame(updateFrame);
}

function initSparklines() {
  const sparklineOptions = {
    type: 'line',
    data: {
      labels: ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN'],
      datasets: [{
        data: [14, 20, 16, 28, 25, 36, 48],
        borderColor: '#059669',
        borderWidth: 1.8,
        tension: 0.3,
        pointRadius: 0,
        fill: false
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      layout: { padding: { top: 2, bottom: 2, left: 2, right: 2 } },
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
      scales: { x: { display: false }, y: { display: false } }
    }
  };

  ['sparklineTotal', 'sparklineTiktok', 'sparklineFacebook', 'sparklineZalo'].forEach(id => {
    const el = document.getElementById(id);
    if (el) new Chart(el, sparklineOptions);
  });
}

function getMergedCommentsList() {
  let list = [...rawCommentsData];

  return list.map((item, index) => {
    let insight = insightsData.find(i => i.comment_id === item.id || i.raw_comment_id === item.id);
    if (!insight && index < insightsData.length) {
      insight = insightsData[index];
    }

    const detectedCategory = detectCategoryFromText(item.content);
    const rawCat = (insight && insight.spending_category && insight.spending_category !== 'khac')
      ? insight.spending_category 
      : detectedCategory;
    const finalCategory = normalizeCategory(rawCat);

    const detectedBank = detectBankFromText(item.content);
    const rawBank = (insight && insight.target_bank) ? insight.target_bank : detectedBank;
    const finalBank = normalizeBank(rawBank);

    return {
      id: item.id || (index + 1),
      platform: item.platform || 'tiktok',
      group_or_page: item.group_or_page || '',
      author: item.author || 'User',
      content: item.content || '',
      comment_created_at: item.comment_created_at || new Date().toISOString(),
      source_url: item.source_url || '',
      status: item.status || 'processed',
      spending_category: finalCategory,
      target_bank: finalBank,
      target_card: insight?.target_card || null,
      intent: insight?.intent || 'hoi_uu_dai',
      summary: insight?.summary || null,
      director_action: insight?.director_action || null
    };
  });
}

function renderCharts() {
  const mergedList = getMergedCommentsList();

  // 1. Phân Bổ Nhu Cầu Chi Tiêu Thẻ Tín Dụng (ĐẦY ĐỦ 100% TẤT CẢ 9 LĨNH VỰC - Biểu đồ Cột Dọc)
  const categoryCounts = {
    'Tư vấn & Thắc mắc khác': 0,
    'Mua sắm & Hoàn tiền': 0,
    'Hạn mức & Biểu phí': 0,
    'Du lịch & Ngoại tệ': 0,
    'Mở thẻ & Sang ngang': 0,
    'Trả góp 0% & Sao kê': 0,
    'Ẩm thực & Di chuyển': 0,
    'Đánh giá & Trải nghiệm CSKH': 0,
    'Rút tiền & Đáo hạn POS': 0
  };

  let totalCommentsCount = mergedList.length;
  mergedList.forEach(item => {
    const cat = normalizeCategory(item.spending_category);
    categoryCounts[cat] = (categoryCounts[cat] || 0) + 1;
  });

  // Sort descending by volume
  const sortedCategories = Object.entries(categoryCounts)
    .filter(([_, count]) => count > 0)
    .sort((a, b) => b[1] - a[1]);

  const catLabels = sortedCategories.map(c => c[0]);
  const catValues = sortedCategories.map(c => c[1]);

  // Gradient 9 sắc thái Xanh (Tương tự ảnh mẫu của user)
  const SHADES_OF_BLUE_9 = [
    '#2563EB', // Xanh chủ đạo đậm
    '#3B82F6', 
    '#4A88BD', 
    '#60A5FA', 
    '#6FA4D0', 
    '#93C5FD', 
    '#98BFE0', 
    '#BFDBFE', 
    '#CBD5E1'  // Xám xanh nhạt
  ];

  const ctxCategory = document.getElementById('chartSpendingCategory');
  if (ctxCategory) {
    if (chartCategory) chartCategory.destroy();

    chartCategory = new Chart(ctxCategory, {
      type: 'bar',
      data: {
        labels: catLabels,
        datasets: [{
          label: 'Số lượt bình luận',
          data: catValues,
          backgroundColor: SHADES_OF_BLUE_9.slice(0, catLabels.length),
          hoverBackgroundColor: '#1D4ED8',
          borderRadius: 4,
          borderSkipped: false,
          barPercentage: 0.68,
          categoryPercentage: 0.85
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        layout: {
          padding: { top: 12, bottom: 2, left: 2, right: 6 }
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#0F172A',
            padding: 10,
            cornerRadius: 6,
            titleFont: { family: 'Plus Jakarta Sans', size: 12, weight: 'bold' },
            bodyFont: { family: 'Inter', size: 12 },
            callbacks: {
              label: (ctx) => {
                const val = ctx.raw || 0;
                const pct = totalCommentsCount > 0 ? ((val / totalCommentsCount) * 100).toFixed(1) : '0';
                return ` ${val.toLocaleString('vi-VN')} bình luận (${pct}%)`;
              }
            }
          }
        },
        scales: {
          x: { 
            grid: { display: false }, 
            ticks: { 
              font: { family: 'Inter', size: window.innerWidth < 640 ? 8.5 : 10, weight: '600' }, 
              color: '#334155',
              maxRotation: 0,
              minRotation: 0,
              autoSkip: false,
              padding: 6,
              callback: function(val) {
                const label = this.getLabelForValue(val);
                if (label === 'Tư vấn & Thắc mắc khác') return ['Tư vấn &', 'Thắc mắc khác'];
                if (label === 'Mua sắm & Hoàn tiền') return ['Mua sắm &', 'Hoàn tiền'];
                if (label === 'Hạn mức & Biểu phí') return ['Hạn mức &', 'Biểu phí'];
                if (label === 'Du lịch & Ngoại tệ') return ['Du lịch &', 'Ngoại tệ'];
                if (label === 'Mở thẻ & Sang ngang') return ['Mở thẻ &', 'Sang ngang'];
                if (label === 'Trả góp 0% & Sao kê') return ['Trả góp 0% &', 'Sao kê'];
                if (label === 'Ẩm thực & Di chuyển') return ['Ẩm thực &', 'Di chuyển'];
                if (label === 'Đánh giá & Trải nghiệm CSKH') return ['Đánh giá &', 'CSKH'];
                if (label === 'Rút tiền & Đáo hạn POS') return ['Rút tiền &', 'Đáo hạn POS'];
                if (label.includes(' & ')) {
                  return label.split(' & ').map((part, i) => i === 0 ? part + ' &' : part);
                }
                return label;
              }
            } 
          },
          y: { 
            grid: { color: '#F1F5F9' }, 
            ticks: { 
              font: { family: 'Inter', size: 11 }, 
              color: '#64748B',
              precision: 0
            } 
          }
        }
      }
    });
  }

  // 2. Top Ngân Hàng Được Đề Cập (ĐẦY ĐỦ 100% TẤT CẢ CÁC NGÂN HÀNG)
  const bankCounts = {};
  let totalBankMentions = 0;
  mergedList.forEach(item => {
    const b = normalizeBank(item.target_bank);
    if (b) {
      bankCounts[b] = (bankCounts[b] || 0) + 1;
      totalBankMentions++;
    }
  });

  const sortedAllBanks = Object.entries(bankCounts)
    .sort((a, b) => b[1] - a[1]);

  const displayBankData = sortedAllBanks;
  const bankLabels = displayBankData.map(b => b[0]);
  const bankValues = displayBankData.map(b => b[1]);
  
  const BANK_COLORS = [
    '#0F172A', '#059669', '#2563EB', '#D97706', '#7C3AED', 
    '#DC2626', '#0284C7', '#0D9488', '#EA580C', '#E11D48', 
    '#4F46E5', '#16A34A', '#0891B2', '#CA8A04', '#9333EA', 
    '#0369A1', '#475569', '#B45309', '#65A30D', '#C026D3',
    '#6B7280', '#F59E0B', '#10B981', '#6366F1', '#EC4899'
  ];

  const ctxBank = document.getElementById('chartTopBanks');
  if (ctxBank) {
    if (chartBanks) chartBanks.destroy();

    chartBanks = new Chart(ctxBank, {
      type: 'doughnut',
      data: {
        labels: bankLabels.length ? bankLabels : ['MB Bank', 'VIB', 'VPBank', 'Techcombank', 'Vietcombank'],
        datasets: [{
          data: bankValues.length ? bankValues : [35, 25, 20, 10, 6],
          backgroundColor: BANK_COLORS.slice(0, Math.max(1, bankLabels.length)),
          borderWidth: 2,
          borderColor: '#FFFFFF',
          hoverOffset: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#0F172A',
            padding: 8,
            cornerRadius: 4,
            titleFont: { family: 'Plus Jakarta Sans', size: 12, weight: 'bold' },
            bodyFont: { family: 'Inter', size: 12 },
            callbacks: {
              label: (ctx) => {
                const val = ctx.raw || 0;
                const pct = totalBankMentions > 0 ? ((val / totalBankMentions) * 100).toFixed(1) : '0';
                return ` ${ctx.label}: ${val.toLocaleString('vi-VN')} lượt (${pct}%)`;
              }
            }
          }
        },
        cutout: '66%'
      }
    });

    // Render Clean 2-Column Structured Legend Grid (Thẳng hàng ngang, thẳng hàng dọc, cuộn tinh tế)
    const legendContainer = document.getElementById('chartTopBanksLegend');
    if (legendContainer) {
      legendContainer.innerHTML = '';
      displayBankData.forEach(([bankName, count], idx) => {
        const color = BANK_COLORS[idx % BANK_COLORS.length];
        const pct = totalBankMentions > 0 ? ((count / totalBankMentions) * 100).toFixed(1) : '0';
        
        const itemEl = document.createElement('div');
        itemEl.className = 'bank-legend-item';
        itemEl.innerHTML = `
          <div class="bank-legend-left">
            <span class="bank-legend-dot" style="background-color: ${color};"></span>
            <span class="bank-legend-name" title="${bankName} (${count} lượt)">${bankName}</span>
          </div>
          <span class="bank-legend-percent">${pct}%</span>
        `;
        legendContainer.appendChild(itemEl);
      });
    }
  }
}

function renderTable() {
  const tbody = document.getElementById('commentsTableBody');
  const searchVal = document.getElementById('searchInput')?.value.toLowerCase().trim() || '';
  const platformVal = document.getElementById('platformFilter')?.value || 'all';
  const groupVal = document.getElementById('groupFilter')?.value || 'all';
  const categoryVal = document.getElementById('categoryFilter')?.value || 'all';
  const bankVal = document.getElementById('bankFilter')?.value || 'all';
  const statusVal = document.getElementById('statusFilter')?.value || 'all';

  if (!tbody) return;
  tbody.innerHTML = '';

  const mergedList = getMergedCommentsList();
  const hasActiveFilter = (platformVal !== 'all' || groupVal !== 'all' || categoryVal !== 'all' || bankVal !== 'all' || statusVal !== 'all' || searchVal !== '');

  const scoredList = mergedList.map(item => {
    let score = 0;
    let isMatched = true;

    if (platformVal !== 'all') {
      if (item.platform === platformVal) score += 100;
      else isMatched = false;
    }
    if (groupVal !== 'all') {
      if (item.group_or_page === groupVal) score += 100;
      else isMatched = false;
    }
    if (categoryVal !== 'all') {
      if (normalizeCategory(item.spending_category) === normalizeCategory(categoryVal)) score += 100;
      else isMatched = false;
    }
    if (bankVal !== 'all') {
      if (item.target_bank && item.target_bank.toLowerCase() === bankVal.toLowerCase()) score += 100;
      else isMatched = false;
    }
    if (statusVal !== 'all') {
      if ((item.status || 'processed') === statusVal) score += 100;
      else isMatched = false;
    }
    if (searchVal !== '') {
      const matchSearch = (item.author && item.author.toLowerCase().includes(searchVal)) ||
                          (item.content && item.content.toLowerCase().includes(searchVal)) ||
                          (item.group_or_page && item.group_or_page.toLowerCase().includes(searchVal)) ||
                          (item.target_bank && item.target_bank.toLowerCase().includes(searchVal)) ||
                          (item.target_card && item.target_card.toLowerCase().includes(searchVal));
      if (matchSearch) score += 100;
      else isMatched = false;
    }

    return { ...item, _matchScore: score, _isMatched: isMatched };
  });

  const finalList = scoredList.sort((a, b) => {
    if (b._matchScore !== a._matchScore) {
      return b._matchScore - a._matchScore;
    }
    return b.id - a.id;
  });

  const matchedCount = scoredList.filter(i => i._isMatched).length;
  const totalRecords = finalList.length;
  const totalPages = Math.max(1, Math.ceil(totalRecords / pageSize));
  
  if (currentPage > totalPages) currentPage = totalPages;
  if (currentPage < 1) currentPage = 1;

  const startIndex = (currentPage - 1) * pageSize;
  const endIndex = Math.min(startIndex + pageSize, totalRecords);
  const pageData = finalList.slice(startIndex, endIndex);

  const countBadge = document.getElementById('tableRecordCount');
  if (countBadge) {
    countBadge.textContent = hasActiveFilter 
      ? `Đã tìm thấy ${matchedCount} kết quả khớp` 
      : `${totalRecords} bản ghi thực tế`;
  }

  document.getElementById('paginationInfo').textContent = totalRecords > 0 
    ? `Hiển thị ${startIndex + 1} - ${endIndex} trong tổng số ${totalRecords} bản ghi` 
    : `Hiển thị 0 bản ghi`;

  document.getElementById('pageIndicator').textContent = `Trang ${currentPage} / ${totalPages}`;
  
  const prevBtn = document.getElementById('btnPrevPage');
  const nextBtn = document.getElementById('btnNextPage');

  if (prevBtn) prevBtn.disabled = (currentPage <= 1);
  if (nextBtn) nextBtn.disabled = (currentPage >= totalPages);

  if (pageData.length === 0) {
    tbody.innerHTML = `<tr><td colspan="10" style="text-align: center; color: var(--text-muted); padding: 32px;">Không có bản ghi nào phù hợp với bộ lọc.</td></tr>`;
    return;
  }

  const categoryMap = {
    'mua_sam_online': 'Mua Sắm Online',
    'du_lich': 'Du Lịch / Vé Máy Bay',
    'tra_gop': 'Trả Góp 0%',
    'rut_tien': 'Rút Tiền Mặt',
    'an_uong': 'Ẩm Thực / Nhà Hàng',
    'sang_ngang_the': 'Sang Ngang Thẻ',
    'khac': 'Khác'
  };

  pageData.forEach(item => {
    const tr = document.createElement('tr');
    
    if (hasActiveFilter && item._matchScore > 0) {
      tr.style.backgroundColor = '#F0FDF4';
    }

    let platformBadge = `<span class="badge badge-tiktok">TikTok</span>`;
    if (item.platform === 'facebook') platformBadge = `<span class="badge badge-facebook">Facebook</span>`;
    if (item.platform === 'zalo') platformBadge = `<span class="badge badge-zalo">Zalo</span>`;

    const groupText = item.group_or_page ? `<span class="group-pill" title="${escapeHtml(item.group_or_page)}">${escapeHtml(item.group_or_page)}</span>` : '<span style="color: var(--text-muted);">-</span>';

    const categoryName = categoryMap[item.spending_category] || item.spending_category || 'Khác';
    const categoryText = `<span class="tag-pill">${categoryName}</span>`;

    let bankCardText = '<span style="color: var(--text-muted);">-</span>';
    if (item.target_bank || item.target_card) {
      const bankLabel = item.target_bank ? `<strong style="color: var(--text-primary);">${escapeHtml(item.target_bank)}</strong>` : '';
      const cardLabel = item.target_card ? `<span style="color: var(--text-muted); font-size: 11.5px; margin-left: 4px;">(${escapeHtml(item.target_card)})</span>` : '';
      bankCardText = `${bankLabel}${cardLabel}`;
    }

    const statusBadge = item.status === 'pending' 
      ? `<span class="badge badge-pending">pending</span>` 
      : `<span class="badge badge-processed">processed</span>`;

    const createdDate = item.comment_created_at ? new Date(item.comment_created_at).toLocaleDateString('vi-VN') : 'Mới';
    const actionBtn = `<button class="btn-view-comment" onclick="openCommentModal(${item.id})">🔍 Xem</button>`;

    tr.innerHTML = `
      <td style="font-weight: 600; color: var(--text-muted);">#${item.id}</td>
      <td>${platformBadge}</td>
      <td>${groupText}</td>
      <td class="author-cell">${escapeHtml(item.author || 'User')}</td>
      <td class="content-cell" title="${escapeHtml(item.content || '')}">${escapeHtml(item.content || '')}</td>
      <td>${categoryText}</td>
      <td>${bankCardText}</td>
      <td>${statusBadge}</td>
      <td style="color: var(--text-muted); font-size: 11.5px;">${createdDate}</td>
      <td>${actionBtn}</td>
    `;

    tbody.appendChild(tr);
  });
}

window.openCommentModal = function(id) {
  const mergedList = getMergedCommentsList();
  const item = mergedList.find(i => i.id === id);
  if (!item) return;

  currentModalItem = item;

  const modalBackdrop = document.getElementById('commentModalBackdrop');
  const modalAuthor = document.getElementById('modalAuthor');
  const modalContent = document.getElementById('modalContent');
  const modalCategory = document.getElementById('modalCategory');
  const modalBankCard = document.getElementById('modalBankCard');
  const modalPlatformBadge = document.getElementById('modalPlatformBadge');
  const modalGroupBadge = document.getElementById('modalGroupBadge');
  const modalSummary = document.getElementById('modalSummary');
  const modalDirectorAction = document.getElementById('modalDirectorAction');

  if (modalAuthor) modalAuthor.textContent = item.author || 'Tác giả ẩn danh';
  if (modalContent) modalContent.textContent = item.content || 'Nội dung rỗng';
  if (modalGroupBadge) modalGroupBadge.textContent = item.group_or_page ? `• ${item.group_or_page}` : '';
  
  const categoryMap = {
    'mua_sam_online': 'Mua Sắm Online',
    'du_lich': 'Du Lịch / Vé Máy Bay',
    'tra_gop': 'Trả Góp 0%',
    'rut_tien': 'Rút Tiền Mặt',
    'an_uong': 'Ẩm Thực / Nhà Hàng',
    'sang_ngang_the': 'Sang Ngang Thẻ',
    'khac': 'Khác'
  };

  if (modalCategory) modalCategory.textContent = categoryMap[item.spending_category] || item.spending_category || 'Khác';
  if (modalBankCard) modalBankCard.textContent = `${item.target_bank || 'Chưa xác định'} ${item.target_card ? `(${item.target_card})` : ''}`;
  
  if (modalSummary) {
    modalSummary.textContent = item.summary || 'Khách hàng đang quan tâm đến các chính sách ưu đãi và hạn mức thẻ tín dụng.';
  }

  if (modalDirectorAction) {
    modalDirectorAction.textContent = item.director_action || 'Đề xuất Ban Giám đốc chỉ đạo chuyên viên tư vấn liên hệ giải đáp điều kiện mở thẻ và ưu đãi dòng thẻ phù hợp.';
  }

  if (modalPlatformBadge) {
    modalPlatformBadge.textContent = item.platform.toUpperCase();
    modalPlatformBadge.className = `badge badge-${item.platform}`;
  }

  if (modalBackdrop) modalBackdrop.classList.add('active');
};

function setupModalListeners() {
  const modalBackdrop = document.getElementById('commentModalBackdrop');
  const closeBtn = document.getElementById('modalCloseBtn');
  const cancelBtn = document.getElementById('modalCancelBtn');
  const openLinkBtn = document.getElementById('modalOpenLinkBtn');

  const closeModal = () => {
    if (modalBackdrop) modalBackdrop.classList.remove('active');
  };

  closeBtn?.addEventListener('click', closeModal);
  cancelBtn?.addEventListener('click', closeModal);

  modalBackdrop?.addEventListener('click', (e) => {
    if (e.target === modalBackdrop) closeModal();
  });

  openLinkBtn?.addEventListener('click', () => {
    if (currentModalItem) {
      const targetUrl = currentModalItem.source_url || 'https://www.tiktok.com/@baothetindung.abf';
      window.open(targetUrl, '_blank');
    }
  });
}

function setupRealtimeSubscription() {
  if (!supabaseClient) return;

  try {
    const statusEl = document.getElementById('realtimeStatus');

    supabaseClient
      .channel('schema-db-changes')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'raw_comments' }, () => {
        fetchDashboardData();
      })
      .on('postgres_changes', { event: '*', schema: 'public', table: 'insights' }, () => {
        fetchDashboardData();
      })
      .subscribe((status) => {
        if (status === 'SUBSCRIBED' && statusEl) {
          statusEl.innerHTML = `<span class="pulse-dot"></span><span>Supabase Live Sync</span>`;
        }
      });
  } catch (err) {
    console.error("❌ Realtime subscription failed:", err);
  }
}

function setupEventListeners() {
  ['platformFilter', 'groupFilter', 'categoryFilter', 'bankFilter', 'statusFilter'].forEach(id => {
    document.getElementById(id)?.addEventListener('change', () => {
      currentPage = 1;
      renderTable();
    });
  });

  document.getElementById('searchInput')?.addEventListener('input', () => {
    currentPage = 1;
    renderTable();
  });

  document.getElementById('pageSizeSelect')?.addEventListener('change', (e) => {
    pageSize = parseInt(e.target.value, 10) || 10;
    currentPage = 1;
    renderTable();
  });

  document.getElementById('btnPrevPage')?.addEventListener('click', () => {
    if (currentPage > 1) {
      currentPage--;
      renderTable();
    }
  });

  document.getElementById('btnNextPage')?.addEventListener('click', () => {
    currentPage++;
    renderTable();
  });

  document.getElementById('btnRefresh')?.addEventListener('click', () => {
    fetchDashboardData();
  });
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

/* ==========================================================================
   IMPORT DATA FEATURE LOGIC
   ========================================================================== */
function setupImportModalListeners() {
  const btnImport = document.getElementById('btnImport');
  const importModal = document.getElementById('importModalBackdrop');
  const closeBtn = document.getElementById('importModalCloseBtn');
  const cancelBtn = document.getElementById('importModalCancelBtn');
  const dropzone = document.getElementById('importDropzone');
  const fileInput = document.getElementById('fileInput');
  const previewBox = document.getElementById('importPreviewBox');
  const fileNameEl = document.getElementById('importFileName');
  const fileSizeEl = document.getElementById('importFileSize');
  const fileStatusEl = document.getElementById('importFileStatus');
  const progressBar = document.getElementById('importProgressBar');
  const btnStartImport = document.getElementById('btnStartImport');
  const btnRemoveFile = document.getElementById('btnRemoveFile');

  let parsedRecords = [];

  const openModal = () => {
    resetImportState();
    importModal?.classList.add('active');
  };

  const closeModal = () => {
    importModal?.classList.remove('active');
  };

  const resetImportState = () => {
    parsedRecords = [];
    if (fileInput) fileInput.value = '';
    if (dropzone) dropzone.style.display = 'block';
    if (previewBox) previewBox.style.display = 'none';
    if (progressBar) progressBar.style.width = '0%';
    if (btnStartImport) {
      btnStartImport.disabled = true;
      btnStartImport.style.background = 'var(--border-subtle)';
      btnStartImport.style.color = 'var(--text-muted)';
      btnStartImport.style.cursor = 'not-allowed';
      btnStartImport.style.opacity = '0.6';
    }
  };

  btnImport?.addEventListener('click', openModal);
  closeBtn?.addEventListener('click', closeModal);
  cancelBtn?.addEventListener('click', closeModal);

  importModal?.addEventListener('click', (e) => {
    if (e.target === importModal) closeModal();
  });

  // Drag and Drop Zone triggers
  dropzone?.addEventListener('click', () => fileInput?.click());

  dropzone?.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.style.borderColor = 'var(--accent-blue)';
    dropzone.style.background = 'rgba(0, 0, 0, 0.03)';
  });

  ['dragleave', 'dragend'].forEach(type => {
    dropzone?.addEventListener(type, () => {
      dropzone.style.borderColor = 'var(--border-subtle)';
      dropzone.style.background = 'rgba(0, 0, 0, 0.01)';
    });
  });

  dropzone?.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.style.borderColor = 'var(--border-subtle)';
    dropzone.style.background = 'rgba(0, 0, 0, 0.01)';
    
    if (e.dataTransfer.files.length > 0) {
      handleFileSelection(e.dataTransfer.files[0]);
    }
  });

  fileInput?.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
      handleFileSelection(e.target.files[0]);
    }
  });

  btnRemoveFile?.addEventListener('click', (e) => {
    e.stopPropagation();
    resetImportState();
  });

  const handleFileSelection = (file) => {
    const ext = file.name.split('.').pop().toLowerCase();
    if (ext !== 'csv' && ext !== 'json') {
      alert('Định dạng file không được hỗ trợ! Chỉ hỗ trợ file .csv hoặc .json');
      return;
    }

    if (file.size > 5 * 1024 * 1024) {
      alert('Kích thước file vượt quá giới hạn 5MB!');
      return;
    }

    fileNameEl.textContent = file.name;
    fileSizeEl.textContent = (file.size / 1024).toFixed(1) + ' KB';
    
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const text = e.target.result;
        if (ext === 'json') {
          parsedRecords = JSON.parse(text);
          if (!Array.isArray(parsedRecords)) {
            parsedRecords = [parsedRecords];
          }
        } else {
          parsedRecords = parseCSV(text);
        }

        // Validate content
        if (parsedRecords.length === 0) {
          throw new Error('File không chứa dữ liệu hợp lệ.');
        }

        const first = parsedRecords[0];
        if (!first.content && !first.comment && !first.text) {
          throw new Error('Thiếu cột nội dung (content) bắt buộc.');
        }

        // Standardize keys
        parsedRecords = parsedRecords.map(item => {
          return {
            platform: item.platform || 'social',
            group_or_page: item.group_or_page || item.group || item.page || 'Imported Data',
            author: item.author || item.user || 'Ẩn danh',
            content: item.content || item.text || item.comment || '',
            comment_created_at: item.comment_created_at || item.created_at || new Date().toISOString(),
            status: 'pending'
          };
        }).filter(item => item.content.trim().length > 0);

        fileStatusEl.textContent = `Sẵn sàng nhập ${parsedRecords.length} dòng dữ liệu.`;
        fileStatusEl.style.color = 'var(--accent-green)';
        
        // Show preview, hide dropzone
        dropzone.style.display = 'none';
        previewBox.style.display = 'block';

        // Enable button
        btnStartImport.disabled = false;
        btnStartImport.style.background = 'var(--accent-blue)';
        btnStartImport.style.color = '#fff';
        btnStartImport.style.borderColor = 'var(--accent-blue)';
        btnStartImport.style.cursor = 'pointer';
        btnStartImport.style.opacity = '1';
      } catch (err) {
        alert('Lỗi đọc file: ' + err.message);
        resetImportState();
      }
    };
    reader.readAsText(file);
  };

  // Perform Supabase Insertion
  btnStartImport?.addEventListener('click', async () => {
    if (parsedRecords.length === 0 || !supabaseClient) return;

    btnStartImport.disabled = true;
    btnStartImport.style.opacity = '0.5';
    btnStartImport.style.cursor = 'not-allowed';
    btnRemoveFile.style.display = 'none';

    fileStatusEl.textContent = 'Đang kết nối tới Supabase và nạp dữ liệu...';
    fileStatusEl.style.color = 'var(--accent-blue)';

    const batchSize = 50;
    const total = parsedRecords.length;
    let successCount = 0;

    for (let i = 0; i < total; i += batchSize) {
      const batch = parsedRecords.slice(i, i + batchSize);
      try {
        const { error } = await supabaseClient.from('raw_comments').insert(batch);
        if (error) throw error;
        
        successCount += batch.length;
        const percent = Math.min(100, Math.round((successCount / total) * 100));
        progressBar.style.width = percent + '%';
        fileStatusEl.textContent = `Đang nạp: ${successCount}/${total} dòng (${percent}%)...`;
      } catch (err) {
        console.error('Lỗi khi nạp batch:', err);
        fileStatusEl.textContent = `Lỗi ở dòng ${i}: ${err.message || err}`;
        fileStatusEl.style.color = 'var(--accent-red)';
        btnStartImport.disabled = false;
        btnStartImport.style.opacity = '1';
        btnStartImport.style.cursor = 'pointer';
        btnRemoveFile.style.display = 'block';
        return;
      }
    }

    fileStatusEl.textContent = `🎉 Thành công! Đã nạp xong ${successCount} bình luận mới.`;
    fileStatusEl.style.color = 'var(--accent-green)';
    
    // Refresh Dashboard Data
    await fetchDashboardData();

    // Auto close modal after delay
    setTimeout(() => {
      closeModal();
      resetImportState();
      btnRemoveFile.style.display = 'block';
    }, 1500);
  });
}

// RFC 4180-compliant simple CSV Parser
function parseCSV(text) {
  const lines = [];
  let row = [""];
  let inQuotes = false;

  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    const next = text[i+1];
    
    if (c === '"') {
      if (inQuotes && next === '"') {
        row[row.length - 1] += '"';
        i++;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (c === ',' && !inQuotes) {
      row.push("");
    } else if ((c === '\r' || c === '\n') && !inQuotes) {
      if (c === '\r' && next === '\n') {
        i++;
      }
      lines.push(row);
      row = [""];
    } else {
      row[row.length - 1] += c;
    }
  }
  if (row.length > 1 || row[0] !== "") {
    lines.push(row);
  }
  
  if (lines.length < 2) return [];
  
  // Clean headers (lowercase and trimmed)
  const headers = lines[0].map(h => h.trim().replace(/^["']|["']$/g, '').toLowerCase());
  const data = [];
  
  for (let i = 1; i < lines.length; i++) {
    const values = lines[i];
    if (values.length < headers.length) continue;
    const item = {};
    headers.forEach((header, index) => {
      let val = (values[index] || "").trim();
      // Remove enclosing quotes if any
      val = val.replace(/^["']|["']$/g, '');
      item[header] = val;
    });
    data.push(item);
  }
  return data;
}

