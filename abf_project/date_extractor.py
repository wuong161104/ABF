# -*- coding: utf-8 -*-
"""
=============================================================================
ABF UNIVERSAL DATE & METADATA EXTRACTOR
-----------------------------------------------------------------------------
Module trích xuất thời gian thông minh đa tầng cho:
1. Trang web HTML (Meta tags, JSON-LD, thẻ <time>, cấu trúc DOM bài viết)
2. Văn bản tiếng Việt tự nhiên (Regex ngày tháng, '25 Tháng 8, 2026', '10/01/2026')
3. File tài liệu PDF (HTTP Last-Modified, PDF CreationDate/ModDate)
4. File tài liệu Word (.docx / .doc Core Properties modified/created)
=============================================================================
"""

import re
import json
import email.utils
from datetime import datetime, timezone
from typing import Optional, Tuple, Dict, Any
from bs4 import BeautifulSoup

# Ánh xạ tên tháng tiếng Việt sang số
VN_MONTH_MAP = {
    '1': 1, '01': 1, 'một': 1, 'giêng': 1, 'jan': 1, 'january': 1,
    '2': 2, '02': 2, 'hai': 2, 'feb': 2, 'february': 2,
    '3': 3, '03': 3, 'ba': 3, 'mar': 3, 'march': 3,
    '4': 4, '04': 4, 'bốn': 4, 'tư': 4, 'apr': 4, 'april': 4,
    '5': 5, '05': 5, 'năm': 5, 'may': 5,
    '6': 6, '06': 6, 'sáu': 6, 'jun': 6, 'june': 6,
    '7': 7, '07': 7, 'bảy': 7, 'bẩy': 7, 'jul': 7, 'july': 7,
    '8': 8, '08': 8, 'tám': 8, 'aug': 8, 'august': 8,
    '9': 9, '09': 9, 'chín': 9, 'sep': 9, 'september': 9,
    '10': 10, 'mười': 10, 'oct': 10, 'october': 10,
    '11': 11, 'mười một': 11, 'nov': 11, 'november': 11,
    '12': 12, 'mười hai': 12, 'chạp': 12, 'dec': 12, 'december': 12
}


def parse_iso_or_standard_date(date_str: str) -> Optional[datetime]:
    """Parse chuỗi ngày chuẩn ISO-8601 hoặc các định dạng quốc tế phổ biến"""
    if not date_str:
        return None
    s = date_str.strip()
    # Loại bỏ dấu ngoặc, comment
    s = re.sub(r'^[(\[{]|[)\]}]$', '', s).strip()
    
    # Thử ISO format
    try:
        clean_iso = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass

    # Thử RFC 2822 (Last-Modified format)
    try:
        dt = email.utils.parsedate_to_datetime(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass

    # Thử định dạng ngày cơ bản
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%d-%m-%Y %H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y/%m/%d"
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(s[:19], fmt)
            return dt.replace(tzinfo=timezone.utc)
        except Exception:
            continue

    return None


def extract_date_from_text(text: str) -> Tuple[Optional[datetime], Optional[str]]:
    """
    Trích xuất ngày tháng từ văn bản tự nhiên tiếng Việt hoặc số.
    Ví dụ:
    - "25 Tháng 8, 2026" -> (datetime(2026, 8, 25), "25 Tháng 8, 2026")
    - "10/01/2026" -> (datetime(2026, 1, 10), "10/01/2026")
    - "ngày 15 tháng 09 năm 2026" -> (datetime(2026, 9, 15), "ngày 15 tháng 09 năm 2026")
    """
    if not text:
        return None, None

    # Pattern 1: Dạng "25 Tháng 8, 2026" hoặc "25 Tháng Tám, 2026"
    p1 = re.search(
        r'(\d{1,2})\s+[Tt]háng\s+([0-9]{1,2}|[A-Za-zÀ-ỹ]+)(?:,)?\s+(20\d{2})',
        text
    )
    if p1:
        raw_match = p1.group(0)
        day = int(p1.group(1))
        month_str = p1.group(2).lower().strip()
        year = int(p1.group(3))
        month = VN_MONTH_MAP.get(month_str)
        if month and 1 <= day <= 31 and 2000 <= year <= 2099:
            try:
                return datetime(year, month, day, tzinfo=timezone.utc), raw_match
            except Exception:
                pass

    # Pattern 2: Dạng "ngày DD tháng MM năm YYYY"
    p2 = re.search(
        r'[Nn]gày\s+(\d{1,2})\s+tháng\s+(\d{1,2}|[A-Za-zÀ-ỹ]+)\s+năm\s+(20\d{2})',
        text
    )
    if p2:
        raw_match = p2.group(0)
        day = int(p2.group(1))
        month_str = p2.group(2).lower().strip()
        year = int(p2.group(3))
        month = VN_MONTH_MAP.get(month_str)
        if month and 1 <= day <= 31 and 2000 <= year <= 2099:
            try:
                return datetime(year, month, day, tzinfo=timezone.utc), raw_match
            except Exception:
                pass

    # Pattern 3: Dạng DD/MM/YYYY hoặc DD-MM-YYYY kèm giờ HH:MM nếu có
    p3 = re.search(
        r'(?:(?:đăng|cập nhật|ngày|lúc)?\s*:?\s*)?(\d{1,2})[/\.-](\d{1,2})[/\.-](20\d{2})(?:\s+(\d{1,2}):(\d{2}))?',
        text
    )
    if p3:
        raw_match = p3.group(0)
        day = int(p3.group(1))
        month = int(p3.group(2))
        year = int(p3.group(3))
        hour = int(p3.group(4)) if p3.group(4) else 0
        minute = int(p3.group(5)) if p3.group(5) else 0
        if 1 <= month <= 12 and 1 <= day <= 31 and 2000 <= year <= 2099 and 0 <= hour <= 23 and 0 <= minute <= 59:
            try:
                return datetime(year, month, day, hour, minute, tzinfo=timezone.utc), raw_match.strip()
            except Exception:
                pass

    # Pattern 4: Dạng ISO trong text (YYYY-MM-DD)
    p4 = re.search(r'\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b', text)
    if p4:
        raw_match = p4.group(0)
        year = int(p4.group(1))
        month = int(p4.group(2))
        day = int(p4.group(3))
        if 1 <= month <= 12 and 1 <= day <= 31 and 2000 <= year <= 2099:
            try:
                return datetime(year, month, day, tzinfo=timezone.utc), raw_match
            except Exception:
                pass

    return None, None


def extract_date_from_html(html: str) -> Tuple[Optional[datetime], Optional[str]]:
    """
    Bóc tách thời gian đăng / cập nhật từ HTML trang web:
    1. Meta tags (article:published_time, article:modified_time, pubdate...)
    2. JSON-LD Schema (datePublished, dateModified)
    3. Thẻ <time datetime="...">
    4. Các class CSS chứa ngày (date, time, post-date, news-date...)
    5. Regex quét phần đầu bài viết
    """
    if not html:
        return None, None

    soup = BeautifulSoup(html, 'html.parser')

    # 1. Quét Meta Tags
    meta_keys = [
        ('property', 'article:published_time'),
        ('property', 'article:modified_time'),
        ('property', 'og:updated_time'),
        ('property', 'og:published_time'),
        ('name', 'pubdate'),
        ('name', 'publishdate'),
        ('name', 'date'),
        ('name', 'dc.date'),
        ('name', 'sailthru.date'),
        ('itemprop', 'datePublished'),
        ('itemprop', 'dateModified'),
    ]
    for attr_name, attr_val in meta_keys:
        tag = soup.find('meta', attrs={attr_name: attr_val})
        if tag and tag.get('content'):
            raw_val = tag['content'].strip()
            parsed = parse_iso_or_standard_date(raw_val)
            if parsed:
                return parsed, raw_val
            # Thử regex text
            parsed, match_text = extract_date_from_text(raw_val)
            if parsed:
                return parsed, match_text

    # 2. Quét JSON-LD
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            if not script.string:
                continue
            data = json.loads(script.string)
            # Support cả list hoặc object
            items = data if isinstance(data, list) else [data]
            for item in items:
                if not isinstance(item, dict):
                    continue
                for date_key in ['datePublished', 'dateModified', 'uploadDate']:
                    val = item.get(date_key)
                    if val and isinstance(val, str):
                        parsed = parse_iso_or_standard_date(val)
                        if parsed:
                            return parsed, val
        except Exception:
            pass

    # 3. Quét thẻ <time>
    for t_tag in soup.find_all('time'):
        dt_attr = t_tag.get('datetime') or t_tag.get('content')
        if dt_attr:
            parsed = parse_iso_or_standard_date(dt_attr)
            if parsed:
                return parsed, dt_attr
        t_text = t_tag.get_text(strip=True)
        if t_text:
            parsed, match_text = extract_date_from_text(t_text)
            if parsed:
                return parsed, match_text

    # 4. Quét các phần tử có class ngày tháng
    date_selectors = [
        '.post-date', '.entry-date', '.date', '.published',
        '.article-date', '.created-date', '.time', '.news-date',
        '.publish-date', '.meta-date', '.date-time', '.blog-date'
    ]
    for sel in date_selectors:
        found = soup.select_one(sel)
        if found:
            txt = found.get_text(strip=True)
            if txt:
                parsed, match_text = extract_date_from_text(txt)
                if parsed:
                    return parsed, match_text

    # 5. Quét 2000 ký tự đầu của bài viết bằng Regex tiếng Việt
    main_text = soup.get_text()[:2500]
    parsed, match_text = extract_date_from_text(main_text)
    if parsed:
        return parsed, match_text

    return None, None


def extract_pdf_date(resp_headers: dict = None, pdf_bytes: bytes = None) -> Tuple[Optional[datetime], Optional[str]]:
    """
    Trích xuất ngày cập nhật của file PDF:
    1. HTTP Header 'Last-Modified'
    2. Thuộc tính nội tại của PDF: /ModDate hoặc /CreationDate
    """
    # 1. Thử HTTP Header Last-Modified
    if resp_headers:
        last_mod = resp_headers.get('Last-Modified') or resp_headers.get('last-modified')
        if last_mod:
            parsed = parse_iso_or_standard_date(last_mod)
            if parsed:
                return parsed, last_mod

    # 2. Thử đọc metadata PDF
    if pdf_bytes:
        try:
            import pypdf
            import io
            reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
            meta = reader.metadata
            if meta:
                # PDF metadata date format: D:YYYYMMDDHHmmSSOHH'mm'
                raw_mod = meta.get('/ModDate') or meta.get('/CreationDate')
                if raw_mod and str(raw_mod).startswith("D:"):
                    clean = str(raw_mod)[2:16]
                    try:
                        dt = datetime.strptime(clean[:14], "%Y%m%d%H%M%S")
                        return dt.replace(tzinfo=timezone.utc), str(raw_mod)
                    except Exception:
                        pass
        except Exception:
            pass

    return None, None


def extract_word_date(resp_headers: dict = None, word_bytes: bytes = None) -> Tuple[Optional[datetime], Optional[str]]:
    """
    Trích xuất ngày cập nhật của file Word:
    1. HTTP Header 'Last-Modified'
    2. Core Properties của file .docx (modified hoặc created)
    """
    if resp_headers:
        last_mod = resp_headers.get('Last-Modified') or resp_headers.get('last-modified')
        if last_mod:
            parsed = parse_iso_or_standard_date(last_mod)
            if parsed:
                return parsed, last_mod

    if word_bytes:
        try:
            import docx
            import io
            doc = docx.Document(io.BytesIO(word_bytes))
            props = doc.core_properties
            if props.modified:
                dt = props.modified
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt, dt.isoformat()
            if props.created:
                dt = props.created
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt, dt.isoformat()
        except Exception:
            pass

    return None, None
