"""Flask web app for Amazon ASIN scraping with grouped session tracking."""

from __future__ import annotations

import json
import logging
import os
import queue
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.request
import uuid
import webbrowser
from datetime import datetime
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from flask import Flask, Response, jsonify, render_template, request, send_file

BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)
logger = logging.getLogger(__name__)

APP_VERSION = "20260807-edge-scraper"
scrape_lock = threading.Lock()
current_sessions: dict[str, dict] = {}
NEXT_SESSION_ID = 0
EXCEL_ILLEGAL_CHARS_RE = re.compile(r"[\x00-\x08\x0B-\x0C\x0E-\x1F]")
INVENTORY_THRESHOLD = 10
INVENTORY_PERSON_DEPARTMENT = os.environ.get("AMZ_INVENTORY_PERSON_DEPARTMENT", "指定部门").strip() or "指定部门"
DEFAULT_DATA_DIR = (
    Path.home() / "AppData" / "Local" / "AmazonASINDashboard"
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent / "data"
)
DATA_DIR = Path(os.environ.get("AMZ_DASHBOARD_DATA_DIR", DEFAULT_DATA_DIR))
INVENTORY_CACHE_PATH = DATA_DIR / "erp_inventory_cache.json"
SKU_MAP_CACHE_PATH = DATA_DIR / "sku_map_cache.json"
LAST_RESULTS_CACHE_PATH = DATA_DIR / "last_results_cache.json"
ERP_CONFIG_PATH = DATA_DIR / "erp_auto_config.json"
ERP_DOWNLOAD_DIR = DATA_DIR / "erp_downloads"
ERP_DEBUG_DIR = DATA_DIR / "erp_debug"
ERP_LOGIN_URL = os.environ.get("AMZ_ERP_LOGIN_URL", "").strip()
ERP_TARGET_URL = os.environ.get("AMZ_ERP_TARGET_URL", "").strip()
ERP_MENU_TARGET = "库存管理"
ERP_DOWNLOAD_TARGET = "导出,下载,Excel,库存"
ERP_API_BASE_URL = os.environ.get("AMZ_ERP_API_BASE_URL", "").strip()
ERP_STOCK_EXPORT_API = os.environ.get("AMZ_ERP_STOCK_EXPORT_API", "/api/stock/erp-stock/export").strip()
ERP_TASK_LIST_API = os.environ.get("AMZ_ERP_TASK_LIST_API", "/api/task/list?page=1&perPage=20").strip()
inventory_lock = threading.Lock()
last_results_lock = threading.Lock()
inventory_context: dict = {
    "inventory": {},
    "inventory_by_person": {},
    "inventory_people": [],
    "inventory_person_filter": "",
    "inventory_meta": None,
    "common_to_actual": {},
    "actual_to_common": {},
    "sku_map_meta": None,
}
last_results_context: dict = {
    "time": "",
    "results": [],
}


def _new_session_id() -> str:
    global NEXT_SESSION_ID
    NEXT_SESSION_ID += 1
    return str(NEXT_SESSION_ID)


def _clean_excel_value(value) -> str:
    if value is None:
        return ""
    text = str(value)
    return EXCEL_ILLEGAL_CHARS_RE.sub("", text)


def _join_excel_values(values, fallback="") -> str:
    if not values:
        values = [fallback]
    elif isinstance(values, (str, int, float)):
        values = [values]
    cleaned = [_clean_excel_value(value).strip() for value in values if _clean_excel_value(value).strip()]
    return " / ".join(cleaned)


def _normalize_sku(value) -> str:
    return re.sub(r"\s+", "", str(value or "").strip()).upper()


def _to_int(value) -> int:
    if value is None:
        return 0
    text = str(value).strip().replace(",", "")
    if not text:
        return 0
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return 0
    try:
        return int(float(match.group(0)))
    except ValueError:
        return 0


def _find_column(columns, candidates: list[str], contains: list[str] | None = None):
    contains = contains or []
    normalized = {str(col).strip().lower(): col for col in columns}
    for candidate in candidates:
        match = normalized.get(candidate.lower())
        if match is not None:
            return match
    for col in columns:
        col_lower = str(col).strip().lower()
        if any(key.lower() in col_lower for key in contains):
            return col
    return None


def _split_skus(value) -> list[str]:
    parts = re.split(r"\s*/\s*|[,，;；\n\r]+", str(value or ""))
    skus = []
    for part in parts:
        sku = _normalize_sku(part)
        if sku and sku not in skus:
            skus.append(sku)
    return skus


def _inventory_status_payload() -> dict:
    inventory_meta = inventory_context.get("inventory_meta")
    sku_map_meta = inventory_context.get("sku_map_meta")
    return {
        "inventory_loaded": bool(inventory_context.get("inventory")),
        "sku_map_loaded": bool(inventory_context.get("common_to_actual")),
        "inventory": inventory_meta,
        "inventory_people": inventory_context.get("inventory_people") or [],
        "inventory_person_filter": inventory_context.get("inventory_person_filter") or "",
        "inventory_person_department": INVENTORY_PERSON_DEPARTMENT,
        "sku_map": sku_map_meta,
        "threshold": INVENTORY_THRESHOLD,
    }


def _save_json_cache(path: Path, payload: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with open(temp_path, "w", encoding="utf-8") as cache_file:
        json.dump(payload, cache_file, ensure_ascii=False)
    os.replace(temp_path, path)


def _load_json_cache(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as cache_file:
            return json.load(cache_file)
    except Exception as exc:
        logger.warning("Failed to load cache %s: %s", path, exc)
        return None


def _save_inventory_cache():
    _save_json_cache(
        INVENTORY_CACHE_PATH,
        {
            "inventory": inventory_context.get("inventory") or {},
            "inventory_by_person": inventory_context.get("inventory_by_person") or {},
            "inventory_people": inventory_context.get("inventory_people") or [],
            "inventory_person_filter": inventory_context.get("inventory_person_filter") or "",
            "inventory_meta": inventory_context.get("inventory_meta"),
        },
    )


def _save_sku_map_cache():
    _save_json_cache(
        SKU_MAP_CACHE_PATH,
        {
            "common_to_actual": inventory_context.get("common_to_actual") or {},
            "actual_to_common": inventory_context.get("actual_to_common") or {},
            "sku_map_meta": inventory_context.get("sku_map_meta"),
        },
    )


def _load_inventory_caches():
    inventory_payload = _load_json_cache(INVENTORY_CACHE_PATH)
    sku_map_payload = _load_json_cache(SKU_MAP_CACHE_PATH)
    with inventory_lock:
        if inventory_payload:
            inventory_context["inventory"] = inventory_payload.get("inventory") or {}
            inventory_context["inventory_by_person"] = inventory_payload.get("inventory_by_person") or {}
            inventory_context["inventory_people"] = inventory_payload.get("inventory_people") or []
            person_filter = inventory_payload.get("inventory_person_filter") or ""
            inventory_context["inventory_person_filter"] = person_filter if person_filter in inventory_context["inventory_people"] else ""
            inventory_context["inventory_meta"] = inventory_payload.get("inventory_meta")
        if sku_map_payload:
            inventory_context["common_to_actual"] = sku_map_payload.get("common_to_actual") or {}
            inventory_context["actual_to_common"] = sku_map_payload.get("actual_to_common") or {}
            inventory_context["sku_map_meta"] = sku_map_payload.get("sku_map_meta")


def _last_results_payload() -> dict:
    results = last_results_context.get("results") or []
    return {
        "time": last_results_context.get("time") or "",
        "results": results,
        "count": len(results),
    }


def _save_last_results_cache(results: list[dict], saved_time: str | None = None):
    payload = {
        "time": saved_time or datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
        "results": results,
    }
    _save_json_cache(LAST_RESULTS_CACHE_PATH, payload)
    last_results_context["time"] = payload["time"]
    last_results_context["results"] = payload["results"]


def _load_last_results_cache():
    payload = _load_json_cache(LAST_RESULTS_CACHE_PATH)
    if not payload:
        return
    results = payload.get("results")
    if not isinstance(results, list):
        results = []
    with last_results_lock:
        last_results_context["time"] = payload.get("time") or ""
        last_results_context["results"] = results


def _load_erp_config() -> dict:
    payload = _load_json_cache(ERP_CONFIG_PATH) or {}
    target_url = str(payload.get("target_url") or ERP_TARGET_URL).strip() or ERP_TARGET_URL
    if "/sale/sale-data" in target_url:
        target_url = ERP_TARGET_URL
    return {
        "login_url": str(payload.get("login_url") or ERP_LOGIN_URL).strip() or ERP_LOGIN_URL,
        "target_url": target_url,
        "menu_target": str(payload.get("menu_target") or ERP_MENU_TARGET).strip() or ERP_MENU_TARGET,
        "download_target": str(payload.get("download_target") or ERP_DOWNLOAD_TARGET).strip() or ERP_DOWNLOAD_TARGET,
        "username": str(payload.get("username") or "").strip(),
        "password": str(payload.get("password") or ""),
    }


def _erp_config_payload() -> dict:
    config = _load_erp_config()
    return {
        "login_url": config["login_url"],
        "target_url": config["target_url"],
        "menu_target": config["menu_target"],
        "download_target": config["download_target"],
        "username": config["username"],
        "password_saved": bool(config["password"]),
    }


def _save_erp_config(payload: dict) -> dict:
    current = _load_erp_config()
    login_url = str(payload.get("login_url") or current["login_url"] or ERP_LOGIN_URL).strip()
    target_url = str(payload.get("target_url") or current["target_url"] or ERP_TARGET_URL).strip()
    menu_target = str(payload.get("menu_target") or current["menu_target"] or ERP_MENU_TARGET).strip()
    download_target = str(payload.get("download_target") or current["download_target"] or ERP_DOWNLOAD_TARGET).strip()
    username = str(payload.get("username") or "").strip()
    password = str(payload.get("password") or "")
    if not password and payload.get("keep_password"):
        password = current.get("password", "")
    if not login_url:
        login_url = ERP_LOGIN_URL
    if not target_url:
        target_url = ERP_TARGET_URL
    if not menu_target:
        menu_target = ERP_MENU_TARGET
    if not download_target:
        download_target = ERP_DOWNLOAD_TARGET
    if not username:
        raise ValueError("请填写 ERP 账号。")
    if not password:
        raise ValueError("请填写 ERP 密码。")
    saved = {
        "login_url": login_url,
        "target_url": target_url,
        "menu_target": menu_target,
        "download_target": download_target,
        "username": username,
        "password": password,
    }
    _save_json_cache(ERP_CONFIG_PATH, saved)
    return saved


def _detect_chrome_binary() -> str | None:
    for path in [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]:
        if os.path.exists(path):
            return path
    return None


def _detect_chromedriver() -> str | None:
    candidates: list[Path] = []
    env_path = os.environ.get("AMZ_CHROMEDRIVER")
    if env_path:
        candidates.append(Path(env_path))
    base_dir = Path(__file__).resolve().parent
    candidates.extend(
        [
            base_dir / "chromedriver.exe",
            base_dir / "drivers" / "chromedriver.exe",
            base_dir / "_internal" / "chromedriver.exe",
        ]
    )
    candidates.extend(Path.home().glob(".wdm/drivers/chromedriver/win64/*/chromedriver-win64/chromedriver.exe"))
    candidates.extend(Path.home().glob(".cache/selenium/chromedriver/win64/*/chromedriver.exe"))
    path_from_env = shutil.which("chromedriver")
    if path_from_env:
        candidates.append(Path(path_from_env))
    existing = [path for path in candidates if path and path.exists()]
    if not existing:
        return None
    existing.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return str(existing[0])


def _visible_elements(driver, by, selector):
    try:
        return [element for element in driver.find_elements(by, selector) if element.is_displayed()]
    except Exception:
        return []


def _first_visible(driver, selectors: list[tuple], timeout: float = 12):
    from selenium.webdriver.support.ui import WebDriverWait

    def find(_driver):
        for by, selector in selectors:
            elements = _visible_elements(_driver, by, selector)
            if elements:
                return elements[0]
        return False

    return WebDriverWait(driver, timeout).until(find)


def _click_by_text(driver, keywords: list[str], timeout: float = 20):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait

    lowered = [keyword.lower().replace(" ", "") for keyword in keywords if keyword]

    def find(_driver):
        candidates = _driver.find_elements(By.CSS_SELECTOR, "button, a, span, div, i, svg")
        for element in candidates:
            try:
                if not element.is_displayed():
                    continue
                parts = [
                    element.text or "",
                    element.get_attribute("title") or "",
                    element.get_attribute("aria-label") or "",
                    element.get_attribute("data-original-title") or "",
                    element.get_attribute("class") or "",
                ]
                text = re.sub(r"\s+", "", " ".join(parts)).lower()
                if text and any(keyword in text for keyword in lowered):
                    return element
            except Exception:
                continue
        return False

    target = WebDriverWait(driver, timeout).until(find)
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target)
    time.sleep(0.2)
    try:
        target.click()
    except Exception:
        driver.execute_script("arguments[0].click();", target)
    return target


def _click_by_target(driver, target_text: str, timeout: float = 20):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait

    target_text = str(target_text or "").strip()
    if target_text.lower().startswith("css:"):
        selector = target_text[4:].strip()
        target = WebDriverWait(driver, timeout).until(
            lambda d: next((element for element in d.find_elements(By.CSS_SELECTOR, selector) if element.is_displayed()), False)
        )
    elif target_text.lower().startswith("xpath:"):
        selector = target_text[6:].strip()
        target = WebDriverWait(driver, timeout).until(
            lambda d: next((element for element in d.find_elements(By.XPATH, selector) if element.is_displayed()), False)
        )
    else:
        keywords = [part.strip() for part in re.split(r"[,，;；\n\r]+", target_text) if part.strip()]
        return _click_by_text(driver, keywords or ["导出", "下载", "Excel", "库存"], timeout=timeout)

    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target)
    time.sleep(0.2)
    try:
        target.click()
    except Exception:
        driver.execute_script("arguments[0].click();", target)
    return target


def _save_erp_debug(driver, label: str) -> dict:
    ERP_DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_label = re.sub(r"[^a-zA-Z0-9_-]+", "_", label).strip("_") or "erp"
    screenshot_path = ERP_DEBUG_DIR / f"{safe_label}_{stamp}.png"
    html_path = ERP_DEBUG_DIR / f"{safe_label}_{stamp}.html"
    payload = {"current_url": "", "screenshot": str(screenshot_path), "html": str(html_path)}
    try:
        payload["current_url"] = driver.current_url or ""
    except Exception:
        pass
    try:
        driver.save_screenshot(str(screenshot_path))
    except Exception as exc:
        payload["screenshot_error"] = str(exc)
    try:
        html_path.write_text(driver.page_source or "", encoding="utf-8")
    except Exception as exc:
        payload["html_error"] = str(exc)
    return payload


def _click_erp_login(driver, password_input, timeout: float = 12):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait

    selectors = [
        (By.CSS_SELECTOR, "button.login-btn"),
        (By.CSS_SELECTOR, "button.el-button--primary"),
        (By.XPATH, "//button[contains(., '验证并登录') or contains(., '登录') or contains(., 'login')]"),
    ]

    def find(_driver):
        for by, selector in selectors:
            for element in _driver.find_elements(by, selector):
                try:
                    if element.is_displayed() and element.is_enabled():
                        return element
                except Exception:
                    continue
        return False

    try:
        target = WebDriverWait(driver, timeout).until(find)
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target)
        time.sleep(0.3)
        try:
            target.click()
        except Exception:
            driver.execute_script("arguments[0].click();", target)
    except Exception:
        password_input.submit()


def _wait_erp_login_finished(driver, timeout: float = 35):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait

    error_keywords = ["密码错误", "账号错误", "登录失败", "验证码", "不能为空", "无效", "过期", "异常"]

    def check(_driver):
        url = (_driver.current_url or "").lower()
        try:
            body_text = _driver.find_element(By.TAG_NAME, "body").text
        except Exception:
            body_text = ""
        if "/login" not in url and "验证并登录" not in body_text:
            return True
        matched_errors = [keyword for keyword in error_keywords if keyword in body_text]
        if matched_errors:
            raise RuntimeError("ERP登录失败：" + "；".join(matched_errors))
        return False

    return WebDriverWait(driver, timeout).until(check)


def _latest_downloaded_excel(before: set[Path], timeout: int = 90) -> Path:
    deadline = time.time() + timeout
    invalid_download_seen_at: float | None = None
    while time.time() < deadline:
        candidates = [
            path
            for path in ERP_DOWNLOAD_DIR.glob("*")
            if path.suffix.lower() in {".xlsx", ".xls"} and path not in before
        ]
        invalid_downloads = [
            path
            for path in ERP_DOWNLOAD_DIR.glob("*")
            if path not in before
            and path.suffix.lower() not in {".xlsx", ".xls", ".crdownload", ".tmp"}
        ]
        temp_files = list(ERP_DOWNLOAD_DIR.glob("*.crdownload")) + list(ERP_DOWNLOAD_DIR.glob("*.tmp"))
        if candidates and not temp_files:
            candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
            return candidates[0]
        invalid_temp_files = [
            path
            for path in temp_files
            if path not in before and not path.name.lower().endswith((".xlsx.crdownload", ".xls.crdownload"))
        ]
        if invalid_downloads or invalid_temp_files:
            if invalid_download_seen_at is None:
                invalid_download_seen_at = time.time()
            elif time.time() - invalid_download_seen_at >= 12:
                names = ", ".join(path.name for path in invalid_downloads + invalid_temp_files)
                raise RuntimeError(f"ERP返回的下载文件不是Excel：{names}")
        else:
            invalid_download_seen_at = None
        time.sleep(1)
    raise TimeoutError("等待 ERP 库存 Excel 下载超时。")


def _erp_base_url(config: dict) -> str:
    parsed = urlparse(config.get("login_url") or ERP_LOGIN_URL)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    parsed = urlparse(config.get("target_url") or ERP_TARGET_URL)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return ""


def _erp_api_base_url(config: dict) -> str:
    parsed = urlparse(config.get("target_url") or config.get("login_url") or ERP_LOGIN_URL)
    if ERP_API_BASE_URL:
        return ERP_API_BASE_URL
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return ""


def _erp_api_request(session: requests.Session, api_base: str, method: str, path: str, **kwargs) -> dict:
    url = urljoin(api_base.rstrip("/") + "/", path.lstrip("/"))
    response = session.request(method, url, timeout=kwargs.pop("timeout", 45), **kwargs)
    response.raise_for_status()
    try:
        payload = response.json()
    except Exception as exc:
        raise RuntimeError(f"ERP API returned non-JSON response from {path}: {response.text[:180]}") from exc
    return payload


def _erp_api_get(session: requests.Session, api_base: str, path: str, **kwargs) -> dict:
    return _erp_api_request(session, api_base, "GET", path, **kwargs)


def _create_erp_api_session(config: dict) -> tuple[requests.Session, str]:
    api_base = _erp_api_base_url(config)
    browser_base = _erp_base_url(config)
    if not api_base:
        raise RuntimeError("ERP API base URL is not configured. Set AMZ_ERP_API_BASE_URL or configure it locally.")
    if not browser_base:
        raise RuntimeError("ERP login/target URL is not configured. Set AMZ_ERP_LOGIN_URL and AMZ_ERP_TARGET_URL locally.")
    fingerprint = str(uuid.uuid4())
    session = requests.Session()
    session.trust_env = False
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Origin": browser_base,
            "Referer": config.get("target_url") or ERP_TARGET_URL,
            "X-Device-Fingerprint": fingerprint,
        }
    )
    login_payload = _erp_api_request(
        session,
        api_base,
        "POST",
        "/api/login",
        json={"account": config["username"], "password": config["password"]},
        timeout=30,
    )
    if int(login_payload.get("code", -1)) != 0:
        raise RuntimeError(login_payload.get("msg") or "ERP API login failed")
    token = ((login_payload.get("data") or {}).get("token") or "").strip()
    if not token:
        raise RuntimeError("ERP API login succeeded but did not return a token")
    session.headers.update({"Authorization": f"Bearer {token}", "Local": "zh_CN"})
    basic_payload = _erp_api_get(session, api_base, "/api/basic", timeout=30)
    if int(basic_payload.get("code", -1)) != 0:
        raise RuntimeError(basic_payload.get("msg") or "ERP API permission check failed")
    return session, api_base


def _read_json_page(driver, url: str, timeout: float = 30) -> dict:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait

    driver.get(url)

    def read_body(_driver):
        try:
            text = _driver.find_element(By.TAG_NAME, "body").text.strip()
        except Exception:
            text = ""
        return text or False

    text = WebDriverWait(driver, timeout).until(read_body)
    try:
        return json.loads(text)
    except Exception as exc:
        raise RuntimeError(f"ERP接口返回不是JSON：{text[:180]}") from exc


def _task_is_erp_stock_export(task: dict, min_task_id: int | None = None) -> bool:
    module = str(task.get("module") or task.get("module_name") or task.get("name") or "")
    title = json.dumps(task, ensure_ascii=False)
    task_id = _to_int(task.get("task_id") or task.get("id"))
    if min_task_id is not None and task_id and task_id <= min_task_id:
        return False
    return (
        int(task.get("type") or 0) == 1
        and int(task.get("status") or 0) == 1
        and bool(task.get("oss"))
        and ("erp" in module.lower() or "ERP库存" in title or "erp-stock" in title.lower())
    )


def _extract_erp_task_items(payload: dict) -> list[dict]:
    data = payload.get("data") or {}
    if isinstance(data, dict):
        items = data.get("data") or data.get("list") or []
    elif isinstance(data, list):
        items = data
    else:
        items = []
    return items if isinstance(items, list) else []


def _download_url_to_file(file_url: str, filename_hint: str = "erp_stock") -> Path:
    ERP_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    parsed_name = Path(urlparse(file_url).path).name
    suffix = Path(parsed_name).suffix if parsed_name else ".xlsx"
    if suffix.lower() not in {".xlsx", ".xls"}:
        suffix = ".xlsx"
    output_path = ERP_DOWNLOAD_DIR / f"{filename_hint}_{datetime.now().strftime('%Y%m%d%H%M%S')}{suffix}"
    with urllib.request.urlopen(file_url, timeout=90) as response:
        data = response.read()
    if not data:
        raise RuntimeError("ERP库存文件下载为空。")
    output_path.write_bytes(data)
    return output_path


def _auto_export_erp_stock_from_api(config: dict) -> Path:
    session, api_base = _create_erp_api_session(config)
    task_payload = _erp_api_get(session, api_base, ERP_TASK_LIST_API, timeout=30)
    existing_tasks = _extract_erp_task_items(task_payload)
    max_task_id = max((_to_int(task.get("task_id") or task.get("id")) for task in existing_tasks), default=0)

    export_payload = _erp_api_get(session, api_base, ERP_STOCK_EXPORT_API, timeout=45)
    if int(export_payload.get("code", -1)) != 0:
        raise RuntimeError(export_payload.get("msg") or "ERP stock export task creation failed")

    deadline = time.time() + 180
    last_error = ""
    while time.time() < deadline:
        task_payload = _erp_api_get(session, api_base, ERP_TASK_LIST_API, timeout=30)
        for task in _extract_erp_task_items(task_payload):
            task_id = _to_int(task.get("task_id") or task.get("id"))
            if _task_is_erp_stock_export(task, max_task_id):
                return _download_url_to_file(str(task["oss"]), "erp_stock_auto")
            if task_id > max_task_id and int(task.get("status") or 0) == -1:
                last_error = str(task.get("error") or task.get("msg") or "")
        time.sleep(5)

    raise TimeoutError(f"ERP stock export task did not finish in download center. {last_error}")


def _auto_export_erp_stock_from_task_center(driver, config: dict) -> Path:
    base_url = _erp_base_url(config)
    task_payload = _read_json_page(driver, urljoin(base_url, ERP_TASK_LIST_API), timeout=25)
    existing_tasks = ((task_payload.get("data") or {}).get("data") or task_payload.get("data") or [])
    max_task_id = max((_to_int(task.get("task_id") or task.get("id")) for task in existing_tasks), default=0)

    export_payload = _read_json_page(driver, urljoin(base_url, ERP_STOCK_EXPORT_API), timeout=25)
    if int(export_payload.get("code", -1)) != 0:
        raise RuntimeError(export_payload.get("msg") or "ERP库存导出任务创建失败。")

    deadline = time.time() + 150
    last_error = ""
    while time.time() < deadline:
        task_payload = _read_json_page(driver, urljoin(base_url, ERP_TASK_LIST_API), timeout=25)
        tasks = ((task_payload.get("data") or {}).get("data") or task_payload.get("data") or [])
        for task in tasks:
            if _task_is_erp_stock_export(task, max_task_id):
                return _download_url_to_file(str(task["oss"]), "erp_stock_auto")
            if _to_int(task.get("task_id") or task.get("id")) > max_task_id and int(task.get("status") or 0) == -1:
                last_error = str(task.get("error") or task.get("msg") or "")
        time.sleep(5)

    raise TimeoutError(f"ERP库存导出任务未在下载中心完成。{last_error}")


def _auto_download_erp_inventory(config: dict) -> Path:
    target_url = config.get("target_url") or ERP_TARGET_URL
    if "/stock/erp-stock" in (target_url or ""):
        return _auto_export_erp_stock_from_api(config)

    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from webdriver_manager.chrome import ChromeDriverManager

    ERP_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    for temp_path in list(ERP_DOWNLOAD_DIR.glob("*.crdownload")) + list(ERP_DOWNLOAD_DIR.glob("*.tmp")):
        try:
            temp_path.unlink()
        except Exception:
            pass
    before = set(ERP_DOWNLOAD_DIR.glob("*"))

    options = Options()
    chrome_binary = _detect_chrome_binary()
    if chrome_binary:
        options.binary_location = chrome_binary
    options.page_load_strategy = "eager"
    chrome_user_data_dir = Path(tempfile.mkdtemp(prefix="amazon_erp_chrome_"))
    chrome_default_dir = chrome_user_data_dir / "Default"
    chrome_default_dir.mkdir(parents=True, exist_ok=True)
    local_state = {
        "browser": {"has_seen_welcome_page": True},
        "profile": {
            "last_used": "Default",
            "picker_shown": True,
            "info_cache": {
                "Default": {
                    "name": "Default",
                    "is_using_default_name": True,
                    "is_consented_primary_account": False,
                }
            },
        },
    }
    preferences = {
        "browser": {"has_seen_welcome_page": True},
        "profile": {
            "name": "Default",
            "exit_type": "Normal",
            "exited_cleanly": True,
        },
    }
    (chrome_user_data_dir / "Local State").write_text(json.dumps(local_state), encoding="utf-8")
    (chrome_default_dir / "Preferences").write_text(json.dumps(preferences), encoding="utf-8")
    # ERP inventory auto-update must stay in the background in distributed builds.
    # Do not allow local environment variables to switch Selenium back to a
    # visible blank Chrome window on another PC.
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1366,900")
    options.add_argument(f"--user-data-dir={chrome_user_data_dir}")
    options.add_argument("--profile-directory=Default")
    options.add_argument("--guest")
    options.add_argument("--disable-features=UserProfilePickerOnStartup,SigninIntercept,ChromeWhatsNewUI")
    options.add_argument("--disable-search-engine-choice-screen")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--lang=zh-CN")
    options.add_experimental_option(
        "prefs",
        {
            "download.default_directory": str(ERP_DOWNLOAD_DIR),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
        },
    )

    driver_path = _detect_chromedriver()
    service = Service(driver_path) if driver_path else Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(45)
    driver.set_script_timeout(15)
    try:
        try:
            driver.execute_cdp_cmd(
                "Page.setDownloadBehavior",
                {"behavior": "allow", "downloadPath": str(ERP_DOWNLOAD_DIR)},
            )
        except Exception:
            pass

        driver.get(config["login_url"])
        username_input = _first_visible(
            driver,
            [
                (By.CSS_SELECTOR, 'input[name="username"]'),
                (By.CSS_SELECTOR, 'input[name="userName"]'),
                (By.CSS_SELECTOR, 'input[name="account"]'),
                (By.CSS_SELECTOR, 'input[placeholder*="账号"]'),
                (By.CSS_SELECTOR, 'input[placeholder*="用户"]'),
                (By.CSS_SELECTOR, 'input[type="text"]'),
            ],
        )
        password_input = _first_visible(
            driver,
            [
                (By.CSS_SELECTOR, 'input[name="password"]'),
                (By.CSS_SELECTOR, 'input[type="password"]'),
                (By.CSS_SELECTOR, 'input[placeholder*="密码"]'),
            ],
        )
        username_input.clear()
        username_input.send_keys(config["username"])
        password_input.clear()
        password_input.send_keys(config["password"])

        _click_erp_login(driver, password_input)
        _wait_erp_login_finished(driver)
        if target_url:
            driver.get(target_url)
            time.sleep(2)

        if "/stock/erp-stock" in (target_url or ""):
            try:
                return _auto_export_erp_stock_from_task_center(driver, config)
            except Exception as exc:
                debug = _save_erp_debug(driver, "erp_stock_task_export_failed")
                raise RuntimeError(
                    "ERP库存接口导出失败。"
                    f"当前页面：{debug.get('current_url') or '未知'}；"
                    f"截图：{debug.get('screenshot')}；"
                    f"HTML：{debug.get('html')}；"
                    f"原因：{exc}"
                ) from exc

        try:
            _click_by_target(driver, config.get("download_target") or ERP_DOWNLOAD_TARGET, timeout=25)
        except Exception as exc:
            debug = _save_erp_debug(driver, "erp_download_button_not_found")
            raise RuntimeError(
                "登录成功，但没有找到ERP库存下载按钮。"
                f"当前页面：{debug.get('current_url') or '未知'}；"
                f"截图：{debug.get('screenshot')}；"
                f"HTML：{debug.get('html')}；"
                f"当前按钮定位：{config.get('download_target') or ERP_DOWNLOAD_TARGET}"
            ) from exc
        try:
            _click_by_text(driver, ["确定", "确认"], timeout=5)
        except Exception:
            pass
        try:
            return _latest_downloaded_excel(before)
        except Exception as exc:
            debug = _save_erp_debug(driver, "erp_download_timeout")
            raise RuntimeError(
                "已点击下载按钮，但没有等到Excel文件下载完成。"
                f"当前页面：{debug.get('current_url') or '未知'}；"
                f"截图：{debug.get('screenshot')}；"
                f"HTML：{debug.get('html')}"
            ) from exc
    except Exception as exc:
        if "截图：" in str(exc) or "HTML：" in str(exc):
            raise
        debug = _save_erp_debug(driver, "erp_auto_update_failed")
        raise RuntimeError(
            "ERP自动更新流程卡住。"
            f"当前页面：{debug.get('current_url') or '未知'}；"
            f"截图：{debug.get('screenshot')}；"
            f"HTML：{debug.get('html')}；"
            f"原因：{exc}"
        ) from exc
    finally:
        try:
            driver.quit()
        except Exception:
            pass
        shutil.rmtree(chrome_user_data_dir, ignore_errors=True)


def _replace_inventory_from_path(path: Path) -> dict:
    inventory, meta = _parse_inventory_file(path)
    inventory_by_person = meta.pop("_inventory_by_person", {})
    inventory_people = meta.pop("_inventory_people", [])
    with inventory_lock:
        inventory_context["inventory"] = inventory
        inventory_context["inventory_by_person"] = inventory_by_person
        inventory_context["inventory_people"] = inventory_people
        if inventory_context.get("inventory_person_filter") not in inventory_people:
            inventory_context["inventory_person_filter"] = ""
        inventory_context["inventory_meta"] = meta
        _save_inventory_cache()
    return _inventory_status_payload()


def _open_browser(port: int):
    url = f"http://127.0.0.1:{port}"
    edge_candidates = [
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    for edge_path in edge_candidates:
        if not os.path.exists(edge_path):
            continue
        try:
            kwargs = {}
            if os.name == "nt":
                kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            subprocess.Popen([edge_path, "--new-window", url], **kwargs)
            _write_startup_log(f"Dashboard opened in Edge at {url}.")
            return
        except Exception as exc:
            _write_startup_log(f"Failed to open Edge at {url}: {exc}")
    _write_startup_log(f"Dashboard ready at {url}; Edge was not found, Chrome auto-opening was skipped.")


def _desktop_log_path() -> str:
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    if os.path.isdir(desktop):
        return os.path.join(desktop, "AmazonASINDashboard.log")
    return os.path.abspath("AmazonASINDashboard.log")


def _write_startup_log(message: str):
    try:
        with open(_desktop_log_path(), "a", encoding="utf-8") as log_file:
            log_file.write(f"[{datetime.now().isoformat(timespec='seconds')}] {message}\n")
    except Exception:
        pass


def _is_port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _is_dashboard_alive(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=0.6) as response:
            return response.status == 200
    except Exception:
        return False


def _choose_port(preferred_port: int) -> tuple[int, bool]:
    if _is_dashboard_alive(preferred_port):
        return preferred_port, True

    if not _is_port_open(preferred_port):
        return preferred_port, False

    for port in range(preferred_port + 1, preferred_port + 30):
        if not _is_port_open(port):
            return port, False

    raise RuntimeError("No available local port between 8080 and 8109.")


def _normalize_url(raw: str) -> str:
    parsed = urlparse(raw.strip())
    if not parsed.scheme or not parsed.netloc:
        return raw.strip()
    path = parsed.path.rstrip("/") or "/"
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{path}"


def _is_valid_asin(value: str) -> bool:
    text = str(value or "").strip().upper()
    return bool(re.fullmatch(r"[A-Z0-9]{10}", text) and re.search(r"\d", text))


def _extract_asin(input_str: str) -> str | None:
    text = input_str.strip()
    if _is_valid_asin(text):
        return text.upper()

    markdown_match = re.search(r"\[([A-Z0-9]{10})\]\((https?://[^)\s]+)\)", text, re.IGNORECASE)
    if markdown_match and _is_valid_asin(markdown_match.group(1)):
        return markdown_match.group(1).upper()

    standalone_match = re.search(r"(?<![A-Z0-9])([A-Z0-9]{10})(?![A-Z0-9])", text, re.IGNORECASE)
    if standalone_match and _is_valid_asin(standalone_match.group(1)) and not text.lower().startswith(("http://", "https://")):
        return standalone_match.group(1).upper()

    patterns = [
        r"/dp/([A-Z0-9]{10})",
        r"/gp/product/([A-Z0-9]{10})",
        r"/product/([A-Z0-9]{10})",
        r"/ASIN/([A-Z0-9]{10})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match and _is_valid_asin(match.group(1)):
            return match.group(1).upper()
    return None


def _extract_url(input_str: str) -> str:
    text = str(input_str or "").strip()
    markdown_match = re.search(r"\[[^\]]+\]\((https?://[^)\s]+)\)", text, re.IGNORECASE)
    if markdown_match:
        return markdown_match.group(1).strip()
    url_match = re.search(r"https?://[^\s)\]]+", text, re.IGNORECASE)
    return url_match.group(0).strip() if url_match else ""


def _source_label(raw: str, source_type: str) -> str:
    if source_type != "url":
        return "手动 ASIN"
    normalized = _normalize_url(_extract_url(raw) or raw)
    parsed = urlparse(normalized)
    tail = parsed.path.strip("/").split("/")
    suffix = tail[-1] if tail and tail[-1] else parsed.netloc
    return f"{parsed.netloc} / {suffix}"


def _parse_inventory_file(file) -> tuple[dict[str, dict], dict]:
    import pandas as pd

    if isinstance(file, (str, Path)):
        filename = Path(file).name
    else:
        filename = getattr(file, "filename", None) or "ERP库存.xlsx"
    df = pd.read_excel(file, dtype=str).fillna("")
    if df.empty:
        raise ValueError("ERP 库存表中没有可用数据。")

    sku_col = _find_column(df.columns, ["SKU", "sku"], ["sku"])
    total_col = _find_column(df.columns, ["总计", "total"], ["总计", "total"])
    person_col = _find_column(df.columns, ["负责人", "person"], ["负责人", "person"])
    department_col = _find_column(df.columns, ["部门", "department"], ["部门", "department"])
    if sku_col is None:
        raise ValueError("没有找到 SKU 列。")
    if total_col is None:
        raise ValueError("没有找到 总计 列。")

    sku_index = list(df.columns).index(sku_col)
    numeric_cols = [col for col in df.columns[sku_index + 1 :] if col != sku_col]
    if total_col not in numeric_cols:
        numeric_cols.insert(0, total_col)

    inventory: dict[str, dict] = {}
    inventory_by_person: dict[str, dict[str, dict]] = {}
    people: set[str] = set()
    source_rows = 0

    def add_inventory(target: dict[str, dict], sku: str, row):
        item = target.setdefault(
            sku,
            {
                "sku": sku,
                "total": 0,
                "warehouses": {},
                "row_count": 0,
            },
        )
        item["row_count"] += 1
        for col in numeric_cols:
            amount = _to_int(row.get(col, 0))
            item["warehouses"][str(col)] = item["warehouses"].get(str(col), 0) + amount
        item["total"] = item["warehouses"].get(str(total_col), item["total"])

    for _, row in df.iterrows():
        sku = _normalize_sku(row.get(sku_col, ""))
        if not sku:
            continue
        source_rows += 1
        add_inventory(inventory, sku, row)

        person = str(row.get(person_col, "") if person_col is not None else "").strip()
        department = str(row.get(department_col, "") if department_col is not None else "").strip()
        if person and department == INVENTORY_PERSON_DEPARTMENT:
            people.add(person)
            add_inventory(inventory_by_person.setdefault(person, {}), sku, row)

    meta = {
        "filename": filename,
        "rows": int(len(df)),
        "matched_rows": source_rows,
        "sku_count": len(inventory),
        "person_count": len(people),
        "person_department": INVENTORY_PERSON_DEPARTMENT,
        "columns": [str(col) for col in df.columns],
        "total_column": str(total_col),
        "imported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    meta["_inventory_by_person"] = inventory_by_person
    meta["_inventory_people"] = sorted(people)
    return inventory, meta


def _parse_sku_map_file(file) -> tuple[dict[str, list[str]], dict[str, str], dict]:
    import pandas as pd

    df = pd.read_excel(file, dtype=str).fillna("")
    if df.empty:
        raise ValueError("SKU 映射表中没有可用数据。")

    actual_col = _find_column(df.columns, ["实际SKU", "实际 SKU", "actual sku"], ["实际", "actual"])
    common_col = _find_column(df.columns, ["通用SKU", "通用 SKU", "common sku"], ["通用", "common"])
    if actual_col is None or common_col is None:
        raise ValueError("映射表需要包含 实际SKU、通用SKU 两列。")

    common_to_actual: dict[str, set[str]] = {}
    actual_to_common: dict[str, str] = {}
    mapped_rows = 0
    for _, row in df.iterrows():
        actual_sku = _normalize_sku(row.get(actual_col, ""))
        common_sku = _normalize_sku(row.get(common_col, ""))
        if not actual_sku or not common_sku:
            continue
        mapped_rows += 1
        common_to_actual.setdefault(common_sku, set()).add(actual_sku)
        actual_to_common.setdefault(actual_sku, common_sku)

    common_map = {common: sorted(skus) for common, skus in common_to_actual.items()}
    meta = {
        "filename": file.filename,
        "rows": int(len(df)),
        "mapped_rows": mapped_rows,
        "actual_sku_count": len(actual_to_common),
        "common_sku_count": len(common_map),
        "columns": [str(col) for col in df.columns],
        "imported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    return common_map, actual_to_common, meta


def _sum_inventory_for_skus(inventory: dict[str, dict], skus: list[str]) -> tuple[int, list[str]]:
    total = 0
    matched = []
    for sku in skus:
        item = inventory.get(sku)
        if not item:
            continue
        total += int(item.get("total") or 0)
        matched.append(sku)
    return total, matched


def _evaluate_single_erp_sku(sku: str, context: dict) -> dict:
    inventory = context.get("inventory") or {}
    common_to_actual = context.get("common_to_actual") or {}
    actual_to_common = context.get("actual_to_common") or {}

    common_sku = sku if sku in common_to_actual else actual_to_common.get(sku, "")
    group_skus: list[str] = []
    if common_sku:
        group_skus.append(common_sku)
        group_skus.extend(common_to_actual.get(common_sku, []))
    else:
        group_skus.append(sku)
    if sku not in group_skus:
        group_skus.insert(0, sku)

    unique_group_skus: list[str] = []
    for group_sku in group_skus:
        normalized = _normalize_sku(group_sku)
        if normalized and normalized not in unique_group_skus:
            unique_group_skus.append(normalized)

    components = []
    for group_sku in unique_group_skus:
        item = inventory.get(group_sku)
        components.append(
            {
                "sku": group_sku,
                "total": int(item.get("total") or 0) if item else 0,
                "matched": bool(item),
            }
        )

    matched_skus = [component["sku"] for component in components if component["matched"]]
    total_stock = sum(component["total"] for component in components)
    own_item = inventory.get(sku)
    display_own_stock = int(own_item.get("total") or 0) if own_item else 0
    substitute_components = [
        component
        for component in components
        if component["matched"] and component["sku"] != sku
    ]
    display_substitute_stock = sum(component["total"] for component in substitute_components)
    display_substitute_skus = [component["sku"] for component in substitute_components]
    risk = "normal"
    label = "ERP库存正常"
    if not matched_skus:
        risk = "unmatched"
        label = "ERP未匹配"
    elif total_stock <= 0:
        risk = "out"
        label = "ERP缺货"
    elif total_stock <= INVENTORY_THRESHOLD:
        risk = "low"
        label = "ERP即将缺货"

    return {
        "sku": sku,
        "common_sku": common_sku,
        "actual_skus": matched_skus,
        "erp_stock": display_own_stock,
        "own_stock": display_own_stock,
        "substitute_skus": display_substitute_skus,
        "substitute_stock": display_substitute_stock,
        "total_stock": total_stock,
        "group_skus": unique_group_skus,
        "risk": risk,
        "label": label,
        "matched": bool(matched_skus),
    }


def _apply_inventory_risk(result: dict, erp_sku_text: str, inventory_person_filter: str | None = None):
    with inventory_lock:
        full_inventory = inventory_context.get("inventory") or {}
        selected_person = str(
            inventory_person_filter
            if inventory_person_filter is not None
            else inventory_context.get("inventory_person_filter") or ""
        ).strip()
        inventory_by_person = inventory_context.get("inventory_by_person") or {}
        active_inventory = (
            inventory_by_person.get(selected_person, {})
            if selected_person
            else full_inventory
        )
        context = {
            "inventory": dict(active_inventory or {}),
            "inventory_loaded": bool(full_inventory),
            "common_to_actual": dict(inventory_context.get("common_to_actual") or {}),
            "actual_to_common": dict(inventory_context.get("actual_to_common") or {}),
            "inventory_person_filter": selected_person,
        }

    result["erp_inventory_loaded"] = bool(context["inventory_loaded"])
    result["erp_map_loaded"] = bool(context["common_to_actual"])
    result["erp_inventory_person_filter"] = context["inventory_person_filter"]
    result["erp_sku_stock"] = ""
    result["erp_common_sku"] = ""
    result["erp_actual_skus"] = []
    result["erp_substitute_skus"] = []
    result["erp_substitute_stock"] = ""
    result["erp_total_stock"] = ""
    result["erp_inventory_risk"] = "未导入ERP库存" if not context["inventory_loaded"] else "未填写ERP SKU"
    result["erp_inventory_note"] = result["erp_inventory_risk"]
    _apply_business_risk(result)

    if not context["inventory_loaded"]:
        return

    skus = _split_skus(erp_sku_text)
    if not skus:
        return

    evaluations = [_evaluate_single_erp_sku(sku, context) for sku in skus]
    priority = {"out": 4, "low": 3, "unmatched": 1, "normal": 0}
    selected = max(evaluations, key=lambda item: priority.get(item["risk"], 0))
    result["erp_sku_stock"] = selected["erp_stock"]
    result["erp_common_sku"] = selected["common_sku"]
    result["erp_actual_skus"] = selected["actual_skus"]
    result["erp_substitute_skus"] = selected["substitute_skus"]
    result["erp_substitute_stock"] = selected["substitute_stock"]
    result["erp_total_stock"] = int(selected["total_stock"] or 0)
    result["erp_inventory_risk"] = selected["label"]
    detail_parts = [f"{component_sku}" for component_sku in selected.get("actual_skus", [])]
    result["erp_inventory_note"] = (
        f"ERP SKU {selected['sku']}；"
        f"通用SKU {selected['common_sku'] or selected['sku']}；"
        f"ERP库存合计 {result['erp_total_stock']}；"
        f"匹配SKU {' / '.join(detail_parts) if detail_parts else '-'}"
        + (f"；库存负责人 {context['inventory_person_filter']}" if context["inventory_person_filter"] else "")
    )

    erp_status_map = {
        "out": ("erp_out_of_stock", "ERP缺货"),
        "low": ("erp_low_stock", "ERP即将缺货"),
    }
    _apply_business_risk(result)
    if selected["risk"] not in erp_status_map:
        return

    # Keep Amazon-side hard failures and marketplace warnings as the primary status.
    overridable_statuses = {"success", "price_warn"}
    if result.get("status") in overridable_statuses:
        result["amazon_status"] = result.get("status")
        result["amazon_status_label"] = result.get("status_label")
        result["amazon_error_message"] = result.get("error_message", "")
        result["status"], result["status_label"] = erp_status_map[selected["risk"]]
        if result.get("error_message"):
            result["error_message"] += f"；{result['erp_inventory_note']}"
        else:
            result["error_message"] = result["erp_inventory_note"]

    _apply_business_risk(result)


def _amazon_status_for_business_risk(result: dict) -> str:
    if result.get("amazon_status"):
        return str(result.get("amazon_status") or "")
    if result.get("status") in {"erp_out_of_stock", "erp_low_stock", "erp_substitute_available"}:
        return "success"
    return str(result.get("status") or "")


def _apply_business_risk(result: dict):
    amazon_status = _amazon_status_for_business_risk(result)
    erp_risk = str(result.get("erp_inventory_risk") or "")
    erp_total_raw = result.get("erp_total_stock")
    try:
        erp_total = int(erp_total_raw) if erp_total_raw not in {"", None} else None
    except Exception:
        erp_total = None

    result["business_risk"] = "not_judged"
    result["business_risk_label"] = "未判断业务风险"
    result["business_risk_note"] = "需要先完成 Amazon 抓取并导入 ERP 库存。"
    result["business_risk_level"] = 0

    if erp_risk in {"未导入ERP库存", "未填写ERP SKU", "ERP未匹配"} or erp_total is None:
        result["business_risk_note"] = erp_risk or result["business_risk_note"]
        return

    amazon_sellable = amazon_status in {"success", "price_warn"}
    amazon_unavailable = amazon_status in {"out_of_stock", "low_stock"}
    amazon_quote_abnormal = amazon_status == "price_compare"

    if amazon_sellable and erp_total <= 0:
        result["business_risk"] = "oversell"
        result["business_risk_label"] = "超卖风险"
        result["business_risk_note"] = "Amazon 前台仍可售卖，但 ERP 总库存为 0。"
        result["business_risk_level"] = 5
    elif amazon_sellable and 0 < erp_total <= INVENTORY_THRESHOLD:
        result["business_risk"] = "near_oversell"
        result["business_risk_label"] = "即将超卖"
        result["business_risk_note"] = f"Amazon 前台仍可售卖，但 ERP 总库存仅 {erp_total}。"
        result["business_risk_level"] = 4
    elif amazon_unavailable and erp_total > INVENTORY_THRESHOLD:
        result["business_risk"] = "replenish_opportunity"
        result["business_risk_label"] = "可补货机会"
        result["business_risk_note"] = f"Amazon 显示缺货或即将缺货，但 ERP 总库存还有 {erp_total}。"
        result["business_risk_level"] = 4
    elif amazon_unavailable and 0 < erp_total <= INVENTORY_THRESHOLD:
        result["business_risk"] = "low_stock_unavailable"
        result["business_risk_label"] = "低库存缺货"
        result["business_risk_note"] = f"Amazon 显示缺货或即将缺货，ERP 总库存也仅 {erp_total}。"
        result["business_risk_level"] = 3
    elif amazon_quote_abnormal and erp_total > 0:
        result["business_risk"] = "quote_abnormal"
        result["business_risk_label"] = "报价异常"
        result["business_risk_note"] = f"Amazon 当前为比价/无 Featured Offer 状态，但 ERP 总库存还有 {erp_total}。"
        result["business_risk_level"] = 3
    elif amazon_sellable and erp_total > INVENTORY_THRESHOLD:
        result["business_risk"] = "normal"
        result["business_risk_label"] = "库存一致"
        result["business_risk_note"] = f"Amazon 可售，ERP 总库存 {erp_total}。"
        result["business_risk_level"] = 1
    else:
        result["business_risk"] = "observe"
        result["business_risk_label"] = "观察"
        result["business_risk_note"] = f"Amazon 状态 {result.get('status_label') or amazon_status}，ERP 总库存 {erp_total}。"
        result["business_risk_level"] = 1


def _reapply_inventory_risk(result: dict, inventory_person_filter: str | None = None) -> dict:
    updated = dict(result or {})
    if updated.get("amazon_status"):
        updated["status"] = updated.get("amazon_status")
        updated["status_label"] = updated.get("amazon_status_label") or updated.get("amazon_status")
        updated["error_message"] = updated.get("amazon_error_message", "")
    elif updated.get("status") in {"erp_out_of_stock", "erp_low_stock", "erp_substitute_available"}:
        updated["status"] = "success"
        updated["status_label"] = "成功"
        updated["error_message"] = ""

    _apply_inventory_risk(updated, updated.get("note", ""), inventory_person_filter)
    return updated


def _prepare_items(payload: dict) -> list[dict]:
    raw_items = payload.get("items")
    if isinstance(raw_items, list):
        items_in = raw_items
    else:
        items_in = payload.get("urls", [])

    prepared: list[dict] = []
    merged: dict[str, dict] = {}

    for entry in items_in:
        if isinstance(entry, dict):
            raw_value = str(entry.get("raw") or entry.get("asin") or "").strip()
            asin = str(entry.get("asin") or "").strip().upper()
            note = str(entry.get("name") or "").strip()
            expected_price = str(entry.get("price") or "").strip()
            category = str(entry.get("category") or "").strip()
            source_type = str(entry.get("source_type") or "").strip() or (
                "url" if raw_value.lower().startswith("http") else "asin"
            )
            source_key = str(entry.get("source_key") or "").strip()
            source_url = str(entry.get("source_url") or "").strip()
            source_label = str(entry.get("source_label") or "").strip()
        else:
            raw_value = str(entry or "").strip()
            asin = _extract_asin(raw_value) or ""
            note = ""
            expected_price = ""
            category = ""
            source_type = "url" if raw_value.lower().startswith("http") else "asin"
            source_key = ""
            source_url = raw_value if source_type == "url" else ""
            source_label = ""

        if not raw_value:
            continue

        if not asin:
            asin = _extract_asin(raw_value) or ""
        if not asin:
            continue

        candidate_source_url = source_url or _extract_url(raw_value)
        normalized_source_url = _normalize_url(candidate_source_url) if source_type == "url" and candidate_source_url else ""
        source_url_asin = _extract_asin(candidate_source_url) if normalized_source_url else ""
        source_warning = ""
        if source_url_asin and source_url_asin.upper() != asin.upper():
            source_warning = f"录入 ASIN {asin} 与链接 ASIN {source_url_asin} 不一致，已按录入 ASIN 抓取。"
            normalized_source_url = ""
            source_type = "asin"

        normalized_source_key = source_key or normalized_source_url or asin
        display_category = category or _source_label(candidate_source_url or raw_value, source_type)
        display_source_label = source_label or _source_label(candidate_source_url or raw_value, source_type)

        item = {
            "asin": asin,
            "raw": raw_value,
            "name": note,
            "price": expected_price,
            "category": display_category,
            "source_type": source_type,
            "source_key": normalized_source_key,
            "source_url": normalized_source_url,
            "source_label": display_source_label,
            "source_warning": source_warning,
        }

        existing = merged.get(asin)
        if not existing:
            merged[asin] = {
                **item,
                "names": [note] if note else [],
                "categories": [display_category] if display_category else [],
                "source_labels": [display_source_label] if display_source_label else [],
                "source_urls": [normalized_source_url] if normalized_source_url else [],
                "source_warnings": [source_warning] if source_warning else [],
                "raw_inputs": [raw_value],
                "row_count": 1,
            }
            prepared.append(merged[asin])
            continue

        existing["row_count"] += 1
        existing["raw_inputs"].append(raw_value)
        if note and note not in existing["names"]:
            existing["names"].append(note)
        if display_category and display_category not in existing["categories"]:
            existing["categories"].append(display_category)
        if display_source_label and display_source_label not in existing["source_labels"]:
            existing["source_labels"].append(display_source_label)
        if normalized_source_url and normalized_source_url not in existing["source_urls"]:
            existing["source_urls"].append(normalized_source_url)
        if source_warning and source_warning not in existing["source_warnings"]:
            existing["source_warnings"].append(source_warning)

    return prepared


@app.route("/")
def index():
    return render_template("index.html", app_version=APP_VERSION)


@app.route("/api/scrape", methods=["POST"])
def api_scrape():
    data = request.get_json(silent=True) or {}
    items = _prepare_items(data)
    carry_results = data.get("carry_results", [])
    inventory_person_filter = str(data.get("inventory_person_filter") or "").strip()
    if not isinstance(carry_results, list):
        carry_results = []

    with inventory_lock:
        people = set(inventory_context.get("inventory_people") or [])
    if inventory_person_filter and inventory_person_filter not in people:
        return jsonify({"error": f"库存负责人不在{INVENTORY_PERSON_DEPARTMENT}筛选列表中：{inventory_person_filter}"}), 400

    if not items:
        return jsonify({"error": "请至少输入一个有效的 ASIN 或亚马逊链接。"}), 400

    with scrape_lock:
        active_session = next(
            (
                session_id
                for session_id, session in current_sessions.items()
                if not session.get("complete")
            ),
            "",
        )
        if active_session:
            return jsonify({"error": "已有抓取任务正在运行，请等待完成或先点击“停止剩余任务”。"}), 409

        sid = _new_session_id()
        msg_queue: queue.Queue = queue.Queue()
        current_sessions[sid] = {
            "queue": msg_queue,
            "results": carry_results,
            "complete": False,
            "cancelled": False,
            "total": len(items),
            "items": items,
            "inventory_person_filter": inventory_person_filter,
        }

    def _run():
        engine = None
        try:
            from scraper import ScraperEngine

            engine = ScraperEngine()
            for index, item in enumerate(items, start=1):
                if current_sessions[sid]["cancelled"]:
                    msg_queue.put(
                        {
                            "event": "stopped",
                            "data": {"session_id": sid, "processed": len(current_sessions[sid]["results"])},
                        }
                    )
                    break

                msg_queue.put(
                    {
                        "event": "progress",
                        "data": {
                            "current": index,
                            "total": len(items),
                            "asin": item["asin"],
                            "category": item["category"],
                        },
                    }
                )

                result = engine.scrape_single(item["asin"], source_url=item["source_url"] or None)
                result.update(
                    {
                        "category": item["category"],
                        "categories": item["categories"],
                        "source_type": item["source_type"],
                        "source_key": item["source_key"],
                        "source_label": item["source_label"],
                        "source_labels": item["source_labels"],
                        "source_url": item["source_url"],
                        "source_urls": item["source_urls"],
                        "source_warning": item.get("source_warning", ""),
                        "source_warnings": item.get("source_warnings", []),
                        "note": " / ".join(item["names"]),
                        "expected_price": item["price"],
                        "raw_input": item["raw"],
                        "raw_inputs": item["raw_inputs"],
                        "duplicate_count": item["row_count"],
                    }
                )
                _apply_inventory_risk(result, result.get("note", ""), inventory_person_filter)
                current_sessions[sid]["results"].append(result)
                msg_queue.put({"event": "result", "data": result})
            else:
                msg_queue.put({"event": "complete", "data": {"session_id": sid}})
        except Exception as exc:
            logger.exception("Batch scrape error: %s", exc)
            msg_queue.put({"event": "error", "data": {"message": str(exc)}})
        finally:
            if engine:
                try:
                    engine.quit()
                except Exception:
                    pass
            with scrape_lock:
                current_sessions[sid]["complete"] = True

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"status": "started", "session_id": sid, "total": len(items)})


@app.route("/api/stop", methods=["POST"])
def api_stop():
    data = request.get_json(silent=True) or {}
    sid = str(data.get("session_id") or "")
    session = current_sessions.get(sid)
    if not session:
        return jsonify({"error": "会话不存在。"}), 404
    session["cancelled"] = True
    return jsonify({"status": "stopping"})


@app.route("/api/stream")
def api_stream():
    sid = request.args.get("session_id", "")
    session = current_sessions.get(sid)
    if not session:
        return Response(
            f"event: error\ndata: {json.dumps({'message': '会话不存在。'}, ensure_ascii=False)}\n\n",
            mimetype="text/event-stream",
        )

    def _generate():
        while True:
            try:
                msg = session["queue"].get(timeout=30)
                yield f"event: {msg['event']}\ndata: {json.dumps(msg['data'], ensure_ascii=False)}\n\n"
                if msg["event"] in {"complete", "stopped", "error"}:
                    break
            except queue.Empty:
                yield ": keepalive\n\n"

    return Response(_generate(), mimetype="text/event-stream")


@app.route("/api/export")
def api_export():
    sid = request.args.get("session_id", "")
    session = current_sessions.get(sid)
    if not session or not session.get("results"):
        return jsonify({"error": "没有可导出的数据。"}), 400

    try:
        rows = []
        for result in session["results"]:
            rows.append(
                {
                    "店铺链接名": _join_excel_values(result.get("categories"), result.get("category", "")),
                    "ASIN": _clean_excel_value(result.get("asin", "")),
                    "实际页面 ASIN": _clean_excel_value(result.get("resolved_asin", "")),
                    "ERP SKU": _clean_excel_value(result.get("note", "")),
                    "商品标题": _clean_excel_value(result.get("title", "")),
                    "品牌": _clean_excel_value(result.get("brand", "")),
                    "当前店铺": _clean_excel_value(result.get("seller", "")),
                    "抓取价格": _clean_excel_value(result.get("price", "")),
                    "当前库存": _clean_excel_value(result.get("stock_left", "")),
                    "库存提示": _clean_excel_value(result.get("stock_message", "")),
                    "预期价格": _clean_excel_value(result.get("expected_price", "")),
                    "ERP SKU库存": _clean_excel_value(result.get("erp_sku_stock", "")),
                    "ERP库存合计": _clean_excel_value(result.get("erp_total_stock", "")),
                    "通用SKU": _clean_excel_value(result.get("erp_common_sku", "")),
                    "实际SKU": _join_excel_values(result.get("erp_actual_skus"), ""),
                    "可替代SKU": _join_excel_values(result.get("erp_substitute_skus"), ""),
                    "可替代库存": _clean_excel_value(result.get("erp_substitute_stock", "")),
                    "ERP库存风险": _clean_excel_value(result.get("erp_inventory_risk", "")),
                    "库存匹配说明": _clean_excel_value(result.get("erp_inventory_note", "")),
                    "业务风险": _clean_excel_value(result.get("business_risk_label", "")),
                    "业务风险说明": _clean_excel_value(result.get("business_risk_note", "")),
                    "状态": _clean_excel_value(result.get("status_label", result.get("status", ""))),
                    "错误信息": _clean_excel_value(result.get("error_message", "")),
                    "诊断证据": _clean_excel_value(result.get("diagnostic_evidence", "")),
                    "输入ASIN链接": _clean_excel_value(result.get("input_url", "")),
                    "页面ASIN候选": _join_excel_values(result.get("asin_candidates"), ""),
                    "ASIN复抓记录": _join_excel_values(result.get("asin_check_attempts"), ""),
                    "页面库存/购买框文案": _clean_excel_value(result.get("availability_text", "")),
                    "来源类型": _clean_excel_value(result.get("source_type", "")),
                    "来源标识": _join_excel_values(result.get("source_labels"), result.get("source_label", "")),
                    "来源链接": _join_excel_values(
                        result.get("source_urls"),
                        result.get("source_url", ""),
                    ),
                    "录入值": _join_excel_values(result.get("raw_inputs"), result.get("raw_input", "")),
                    "重复次数": _clean_excel_value(result.get("duplicate_count", 1)),
                    "抓取时间": _clean_excel_value(result.get("timestamp", "")),
                    "商品链接": _clean_excel_value(result.get("input_url") or result.get("url", "")),
                    "实际页面链接": _clean_excel_value(result.get("resolved_url") or ""),
                    "店铺链接": _clean_excel_value(result.get("seller_url", "")),
                }
            )

        import pandas as pd

        output = BytesIO()
        df = pd.DataFrame(rows)
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="ASIN结果")
        output.seek(0)

        filename = f"Amazon_ASIN_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return send_file(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename,
        )
    except Exception as exc:
        logger.exception("Export failed: %s", exc)
        return jsonify({"error": f"导出失败：{exc}"}), 500


@app.route("/api/inventory/import", methods=["POST"])
def api_inventory_import():
    if "file" not in request.files:
        return jsonify({"error": "请上传 ERP 库存 Excel 文件。"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "文件名为空。"}), 400

    try:
        inventory, meta = _parse_inventory_file(file)
    except Exception as exc:
        logger.exception("Inventory import failed: %s", exc)
        return jsonify({"error": f"ERP库存导入失败：{exc}"}), 400

    inventory_by_person = meta.pop("_inventory_by_person", {})
    inventory_people = meta.pop("_inventory_people", [])
    with inventory_lock:
        inventory_context["inventory"] = inventory
        inventory_context["inventory_by_person"] = inventory_by_person
        inventory_context["inventory_people"] = inventory_people
        if inventory_context.get("inventory_person_filter") not in inventory_people:
            inventory_context["inventory_person_filter"] = ""
        inventory_context["inventory_meta"] = meta
        _save_inventory_cache()

    return jsonify({"status": "ok", **_inventory_status_payload()})


@app.route("/api/erp/config", methods=["GET", "POST"])
def api_erp_config():
    if request.method == "GET":
        return jsonify(_erp_config_payload())

    data = request.get_json(silent=True) or {}
    try:
        config = _save_erp_config(data)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(
        {
            "status": "ok",
            "login_url": config["login_url"],
            "target_url": config["target_url"],
            "menu_target": config["menu_target"],
            "download_target": config["download_target"],
            "username": config["username"],
            "password_saved": bool(config["password"]),
        }
    )


@app.route("/api/inventory/auto-update", methods=["POST"])
def api_inventory_auto_update():
    config = _load_erp_config()
    if not config.get("username") or not config.get("password"):
        return jsonify({"error": "请先保存 ERP 账号和密码。"}), 400

    try:
        downloaded_path = _auto_download_erp_inventory(config)
        payload = _replace_inventory_from_path(downloaded_path)
    except Exception as exc:
        logger.exception("ERP inventory auto update failed: %s", exc)
        return jsonify({"error": f"自动更新ERP库存失败：{exc}"}), 500

    return jsonify(
        {
            "status": "ok",
            "downloaded_file": downloaded_path.name,
            **payload,
        }
    )


@app.route("/api/sku-map/import", methods=["POST"])
def api_sku_map_import():
    if "file" not in request.files:
        return jsonify({"error": "请上传 SKU 映射 Excel 文件。"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "文件名为空。"}), 400

    try:
        common_to_actual, actual_to_common, meta = _parse_sku_map_file(file)
    except Exception as exc:
        logger.exception("SKU map import failed: %s", exc)
        return jsonify({"error": f"SKU映射导入失败：{exc}"}), 400

    with inventory_lock:
        inventory_context["common_to_actual"] = common_to_actual
        inventory_context["actual_to_common"] = actual_to_common
        inventory_context["sku_map_meta"] = meta
        _save_sku_map_cache()

    return jsonify({"status": "ok", **_inventory_status_payload()})


@app.route("/api/inventory/status")
def api_inventory_status():
    with inventory_lock:
        payload = _inventory_status_payload()
    return jsonify(payload)


@app.route("/api/inventory/person-filter", methods=["POST"])
def api_inventory_person_filter():
    data = request.get_json(silent=True) or {}
    person = str(data.get("person") or "").strip()
    with inventory_lock:
        people = inventory_context.get("inventory_people") or []
        if person and person not in people:
            return jsonify({"error": f"负责人不在{INVENTORY_PERSON_DEPARTMENT}库存列表中：{person}"}), 400
        inventory_context["inventory_person_filter"] = person
        _save_inventory_cache()
        payload = _inventory_status_payload()
    return jsonify({"status": "ok", **payload})


@app.route("/api/inventory/reapply", methods=["POST"])
def api_inventory_reapply():
    data = request.get_json(silent=True) or {}
    person = str(data.get("person") or "").strip()
    results = data.get("results") or []
    sid = str(data.get("session_id") or "").strip()
    if not isinstance(results, list):
        return jsonify({"error": "结果数据格式不正确。"}), 400

    with inventory_lock:
        people = set(inventory_context.get("inventory_people") or [])
    if person and person not in people:
        return jsonify({"error": f"负责人不在{INVENTORY_PERSON_DEPARTMENT}库存列表中：{person}"}), 400

    updated_results = [_reapply_inventory_risk(result, person) for result in results]
    if sid and sid in current_sessions:
        current_sessions[sid]["results"] = updated_results
        current_sessions[sid]["inventory_person_filter"] = person
    return jsonify({"status": "ok", "results": updated_results, "inventory_person_filter": person})


@app.route("/api/previous-results", methods=["GET", "POST"])
def api_previous_results():
    if request.method == "GET":
        with last_results_lock:
            payload = _last_results_payload()
        return jsonify(payload)

    data = request.get_json(silent=True) or {}
    results = data.get("results", [])
    if not isinstance(results, list):
        return jsonify({"error": "上次结果格式不正确。"}), 400
    saved_time = str(data.get("time") or "").strip() or None
    try:
        with last_results_lock:
            _save_last_results_cache(results, saved_time=saved_time)
            payload = _last_results_payload()
    except Exception as exc:
        logger.exception("Previous results save failed: %s", exc)
        return jsonify({"error": f"上次结果保存失败：{exc}"}), 500
    return jsonify({"status": "ok", **payload})


@app.route("/api/import", methods=["POST"])
def api_import():
    if "file" not in request.files:
        return jsonify({"error": "请上传 Excel 文件。"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "文件名为空。"}), 400

    try:
        import pandas as pd

        df = pd.read_excel(file, dtype=str).fillna("")
    except Exception as exc:
        return jsonify({"error": f"无法读取文件：{exc}"}), 400

    if df.empty:
        return jsonify({"error": "Excel 中没有可用数据。"}), 400

    asin_col = None
    name_col = None
    price_col = None
    category_col = None

    for col in df.columns:
        col_lower = str(col).lower()
        if asin_col is None and any(key in col_lower for key in ["asin", "链接", "url"]):
            asin_col = col
        elif name_col is None and any(key in col_lower for key in ["erp sku", "erp_sku", "sku", "msku", "名称", "name", "备注", "title", "商品"]):
            name_col = col
        elif price_col is None and any(key in col_lower for key in ["价格", "price", "目标", "预期"]):
            price_col = col
        elif category_col is None and any(key in col_lower for key in ["店铺链接名", "店铺链接", "分类", "分组", "category", "group", "批次"]):
            category_col = col

    if asin_col is None:
        asin_col = df.columns[0]
    if name_col is None and len(df.columns) > 1:
        name_col = df.columns[1]
    if price_col is None and len(df.columns) > 2:
        price_col = df.columns[2]
    if category_col is None and len(df.columns) > 3:
        category_col = df.columns[3]

    rows = []
    for _, row in df.iterrows():
        asin_raw = str(row.get(asin_col, "")).strip() if asin_col else ""
        if not asin_raw:
            continue
        rows.append(
            {
                "asin": asin_raw,
                "name": str(row.get(name_col, "")).strip() if name_col else "",
                "price": str(row.get(price_col, "")).strip() if price_col else "",
                "category": str(row.get(category_col, "")).strip() if category_col else "",
            }
        )

    return jsonify(
        {
            "rows": rows,
            "columns_used": [str(col) for col in [asin_col, name_col, price_col, category_col] if col is not None],
        }
    )


@app.route("/api/health")
def api_health():
    return jsonify(
        {
            "status": "ok",
            "version": APP_VERSION,
            "active_sessions": len(current_sessions),
        }
    )


_load_inventory_caches()
_load_last_results_cache()


if __name__ == "__main__":
    import argparse

    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("--port", type=int, default=8080)
        args = parser.parse_args()

        port, already_running = _choose_port(args.port)
        if already_running:
            _write_startup_log(f"Existing dashboard found on port {port}; automatic browser opening is disabled.")
            _open_browser(port)
            sys.exit(0)

        _write_startup_log(f"Starting dashboard on port {port}.")
        print("=" * 60)
        print(" Amazon ASIN Scraper Dashboard")
        print(f" Open http://127.0.0.1:{port} in your browser")
        print("=" * 60)
        threading.Timer(1.2, _open_browser, args=[port]).start()
        app.run(host="127.0.0.1", port=port, debug=False, threaded=True, use_reloader=False)
    except Exception:
        _write_startup_log("Startup failed:\n" + traceback.format_exc())
        raise
