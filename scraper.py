"""Amazon product scraper engine used by the Flask dashboard."""

from __future__ import annotations

import logging
import os
import json
import random
import re
import shutil
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

PAGE_LOAD_WAIT = 0
REQUEST_DELAY_MIN = 0
REQUEST_DELAY_MAX = 0
# Published builds should never show the Selenium-controlled Chrome window.
# Keeping this forced prevents a stray AMZ_SCRAPER_VISIBLE environment variable
# on another PC from opening a blank about:blank Chrome during scraping.
SCRAPER_VISIBLE = False
HEADLESS = True
PAGE_LOAD_STRATEGY = os.environ.get("AMZ_PAGE_LOAD_STRATEGY", "none").strip().lower()
PAGE_LOAD_TIMEOUT = int(os.environ.get("AMZ_PAGE_TIMEOUT", "12"))
SCRIPT_TIMEOUT = int(os.environ.get("AMZ_SCRIPT_TIMEOUT", "5"))
ELEMENT_WAIT = float(os.environ.get("AMZ_ELEMENT_WAIT", "2.5"))
ASIN_MISMATCH_RETRY = int(os.environ.get("AMZ_ASIN_MISMATCH_RETRY", "2"))
MISMATCH_RETRY_DELAY = float(os.environ.get("AMZ_MISMATCH_RETRY_DELAY", "0.25"))
STOP_LOADING_AFTER_SIGNAL = os.environ.get("AMZ_STOP_AFTER_SIGNAL", "1").strip().lower() not in {"0", "false", "no"}


class ScraperEngine:
    """Chrome scraper for Amazon pages."""

    def __init__(self):
        self.driver = None
        self._chrome_user_data_dir = None
        self._last_price_asin = None
        self._asin_candidates_cache: dict[str, list[str]] = {}
        self._init_driver()

    def _hidden_subprocess_kwargs(self, timeout: int = 3) -> dict:
        kwargs = {"stderr": subprocess.DEVNULL, "text": True, "timeout": timeout}
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
            kwargs["startupinfo"] = startupinfo
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        return kwargs

    def _check_output_hidden(self, command, timeout: int = 3) -> str:
        return subprocess.check_output(command, **self._hidden_subprocess_kwargs(timeout=timeout))

    def _make_chrome_service(self, driver_path: str) -> Service:
        try:
            service = Service(driver_path, log_output=subprocess.DEVNULL)
        except TypeError:
            service = Service(driver_path)
        if os.name == "nt":
            service.creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        return service

    def _make_edge_service(self) -> EdgeService:
        try:
            service = EdgeService(log_output=subprocess.DEVNULL)
        except TypeError:
            service = EdgeService()
        if os.name == "nt":
            service.creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        return service

    def _prepare_chrome_profile_dir(self) -> str:
        profile_root = Path(tempfile.mkdtemp(prefix="amazon_asin_chrome_"))
        default_dir = profile_root / "Default"
        default_dir.mkdir(parents=True, exist_ok=True)
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
        (profile_root / "Local State").write_text(json.dumps(local_state), encoding="utf-8")
        (default_dir / "Preferences").write_text(json.dumps(preferences), encoding="utf-8")
        self._chrome_user_data_dir = str(profile_root)
        return str(profile_root)

    def _detect_chrome_binary(self) -> str | None:
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        return None

    def _detect_edge_binary(self) -> str | None:
        candidates = [
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        return None

    def _detect_chrome_major_version(self, chrome_binary: str | None = None) -> str | None:
        candidates = []
        if chrome_binary:
            candidates.append([chrome_binary, "--version"])
        candidates.extend(
            [
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "(Get-Item 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe').VersionInfo.ProductVersion",
                ],
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "(Get-Item 'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe').VersionInfo.ProductVersion",
                ],
            ]
        )
        for command in candidates:
            try:
                output = self._check_output_hidden(command, timeout=3)
            except Exception:
                continue
            match = re.search(r"(\d+)\.", output or "")
            if match:
                return match.group(1)
        return None

    def _chromedriver_major_version(self, path: Path) -> str | None:
        try:
            output = self._check_output_hidden([str(path), "--version"], timeout=3)
        except Exception:
            return None
        match = re.search(r"ChromeDriver\s+(\d+)\.", output or "", re.IGNORECASE)
        return match.group(1) if match else None

    def _detect_chromedriver(self, chrome_major: str | None = None) -> str | None:
        """Prefer a driver that matches the installed Chrome major version."""
        env_path = os.environ.get("AMZ_CHROMEDRIVER")
        candidates = []
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

        user_home = Path.home()
        candidates.extend(user_home.glob(".wdm/drivers/chromedriver/win64/*/chromedriver-win64/chromedriver.exe"))
        candidates.extend(user_home.glob(".cache/selenium/chromedriver/win64/*/chromedriver.exe"))

        path_from_env = shutil.which("chromedriver")
        if path_from_env:
            candidates.append(Path(path_from_env))

        existing = [path for path in candidates if path and path.exists()]
        if not existing:
            return None
        if chrome_major:
            matching = []
            for path in existing:
                driver_major = self._chromedriver_major_version(path)
                if driver_major == chrome_major:
                    matching.append(path)
            if matching:
                matching.sort(key=lambda path: path.stat().st_mtime, reverse=True)
                return str(matching[0])
            logger.warning("No local ChromeDriver matches Chrome major version %s.", chrome_major)
            return None
        existing.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        return str(existing[0])

    def _init_driver(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass

        if os.environ.get("AMZ_FORCE_CHROME", "").strip().lower() not in {"1", "true", "yes"}:
            try:
                edge_options = EdgeOptions()
                edge_options.page_load_strategy = PAGE_LOAD_STRATEGY if PAGE_LOAD_STRATEGY in {"normal", "eager", "none"} else "none"
                edge_binary = self._detect_edge_binary()
                if edge_binary:
                    edge_options.binary_location = edge_binary
                edge_options.add_argument("--headless=new")
                edge_options.add_argument("--window-size=1366,900")
                edge_options.add_argument(f"--user-data-dir={self._prepare_chrome_profile_dir()}")
                edge_options.add_argument("--profile-directory=Default")
                edge_options.add_argument("--guest")
                edge_options.add_argument("--disable-features=msEdgeUserFeedback,EdgeShoppingAssistant")
                edge_options.add_argument("--disable-search-engine-choice-screen")
                edge_options.add_argument("--disable-blink-features=AutomationControlled")
                edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
                edge_options.add_experimental_option("useAutomationExtension", False)
                edge_options.add_argument("--no-sandbox")
                edge_options.add_argument("--disable-dev-shm-usage")
                edge_options.add_argument("--disable-gpu")
                edge_options.add_argument("--disable-extensions")
                edge_options.add_argument("--disable-notifications")
                edge_options.add_argument("--disable-popup-blocking")
                edge_options.add_argument("--disable-crash-reporter")
                edge_options.add_argument("--disable-background-networking")
                edge_options.add_argument("--disable-renderer-backgrounding")
                edge_options.add_argument("--no-first-run")
                edge_options.add_argument("--no-default-browser-check")
                edge_options.add_argument("--log-level=3")
                edge_options.add_argument("--silent")
                edge_options.add_argument("--lang=en-US")
                edge_options.add_argument(
                    "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                )
                edge_options.add_experimental_option(
                    "prefs",
                    {
                        "profile.managed_default_content_settings.images": 2,
                        "profile.default_content_setting_values.notifications": 2,
                        "profile.default_content_setting_values.plugins": 2,
                        "profile.default_content_setting_values.popups": 2,
                    },
                )
                self.driver = webdriver.Edge(service=self._make_edge_service(), options=edge_options)
                self.driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
                self.driver.set_script_timeout(SCRIPT_TIMEOUT)
                self._enable_fast_network()
                self.driver.execute_script(
                    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
                )
                logger.info("Edge driver started, headless=True, strategy=%s", edge_options.page_load_strategy)
                return
            except Exception as exc:
                logger.warning("Edge driver startup failed, falling back to Chrome: %s", exc)
                if self._chrome_user_data_dir:
                    shutil.rmtree(self._chrome_user_data_dir, ignore_errors=True)
                    self._chrome_user_data_dir = None

        options = Options()
        options.page_load_strategy = PAGE_LOAD_STRATEGY if PAGE_LOAD_STRATEGY in {"normal", "eager", "none"} else "none"
        chrome_binary = self._detect_chrome_binary()
        if chrome_binary:
            options.binary_location = chrome_binary
        chrome_major = self._detect_chrome_major_version(chrome_binary)

        options.add_argument("--headless=new")
        options.add_argument("--window-size=1366,900")
        options.add_argument(f"--user-data-dir={self._prepare_chrome_profile_dir()}")
        options.add_argument("--profile-directory=Default")
        options.add_argument("--guest")
        options.add_argument("--disable-features=UserProfilePickerOnStartup,SigninIntercept,ChromeWhatsNewUI")
        options.add_argument("--disable-search-engine-choice-screen")

        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-crash-reporter")
        options.add_argument("--disable-background-networking")
        options.add_argument("--disable-renderer-backgrounding")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--log-level=3")
        options.add_argument("--silent")
        options.add_argument("--lang=en-US")
        options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        options.add_experimental_option(
            "prefs",
            {
                "profile.managed_default_content_settings.images": 2,
                "profile.default_content_setting_values.notifications": 2,
                "profile.default_content_setting_values.plugins": 2,
                "profile.default_content_setting_values.popups": 2,
            },
        )

        driver_path = self._detect_chromedriver(chrome_major)
        if driver_path:
            logger.info("Using local ChromeDriver: %s", driver_path)
            service = self._make_chrome_service(driver_path)
        else:
            logger.info(
                "No matching local ChromeDriver found for Chrome %s; falling back to webdriver_manager download.",
                chrome_major or "unknown",
            )
            if chrome_major:
                service = self._make_chrome_service(ChromeDriverManager(driver_version=chrome_major).install())
            else:
                service = self._make_chrome_service(ChromeDriverManager().install())
        try:
            self.driver = webdriver.Chrome(service=service, options=options)
        except WebDriverException as exc:
            message = str(exc)
            if "session not created" in message.lower() and "only supports chrome version" in message.lower():
                raise RuntimeError(
                    "ChromeDriver 与当前 Chrome 浏览器版本不匹配。"
                    f"当前 Chrome 主版本：{chrome_major or '未知'}。"
                    "请使用最新版压缩包，或删除旧驱动缓存目录 C:\\Users\\当前用户\\.wdm 后重试。"
                ) from exc
            raise
        self.driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
        self.driver.set_script_timeout(SCRIPT_TIMEOUT)
        self._enable_fast_network()
        self.driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        logger.info("Chrome driver started, headless=%s, strategy=%s", HEADLESS, options.page_load_strategy)

    def _enable_fast_network(self):
        blocked_urls = [
            "*.bmp",
            "*.gif",
            "*.jpeg",
            "*.jpg",
            "*.png",
            "*.svg",
            "*.webp",
            "*.ico",
            "*.mp4",
            "*.webm",
            "*.woff",
            "*.woff2",
            "*.ttf",
            "*.otf",
        ]
        try:
            self.driver.execute_cdp_cmd("Network.enable", {})
            self.driver.execute_cdp_cmd("Network.setBlockedURLs", {"urls": blocked_urls})
        except Exception:
            pass

    def _open_product_page(self, url: str):
        self._asin_candidates_cache = {}
        self.driver.get(url)
        if PAGE_LOAD_WAIT:
            time.sleep(PAGE_LOAD_WAIT)
        self._wait_for_product_signal()
        if STOP_LOADING_AFTER_SIGNAL:
            self._stop_page_loading()

    def _stop_page_loading(self):
        try:
            self.driver.execute_script("window.stop();")
        except Exception:
            pass

    def quit(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
        if self._chrome_user_data_dir:
            try:
                shutil.rmtree(self._chrome_user_data_dir, ignore_errors=True)
            except Exception:
                pass
            self._chrome_user_data_dir = None

    @staticmethod
    def _is_valid_asin(value: str) -> bool:
        text = str(value or "").strip().upper()
        return bool(re.fullmatch(r"[A-Z0-9]{10}", text) and re.search(r"\d", text))

    @staticmethod
    def extract_asin(input_str: str) -> str | None:
        text = input_str.strip()
        if ScraperEngine._is_valid_asin(text):
            return text.upper()

        markdown_match = re.search(r"\[([A-Z0-9]{10})\]\((https?://[^)\s]+)\)", text, re.IGNORECASE)
        if markdown_match and ScraperEngine._is_valid_asin(markdown_match.group(1)):
            return markdown_match.group(1).upper()

        standalone_match = re.search(r"(?<![A-Z0-9])([A-Z0-9]{10})(?![A-Z0-9])", text, re.IGNORECASE)
        if (
            standalone_match
            and ScraperEngine._is_valid_asin(standalone_match.group(1))
            and not text.lower().startswith(("http://", "https://"))
        ):
            return standalone_match.group(1).upper()

        patterns = [
            r"/dp/([A-Z0-9]{10})",
            r"/gp/product/([A-Z0-9]{10})",
            r"/product/([A-Z0-9]{10})",
            r"/ASIN/([A-Z0-9]{10})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match and ScraperEngine._is_valid_asin(match.group(1)):
                return match.group(1).upper()
        return None

    @staticmethod
    def _extract_all_asins(input_str: str) -> list[str]:
        text = str(input_str or "")
        matches: list[str] = []
        for pattern in [
            r"/(?:dp|gp/product|product|ASIN)/([A-Z0-9]{10})",
            r"(?<![A-Z0-9])([A-Z0-9]{10})(?![A-Z0-9])",
        ]:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                asin = match.group(1).upper()
                if ScraperEngine._is_valid_asin(asin) and asin not in matches:
                    matches.append(asin)
        return matches

    def scrape_single(self, asin: str, source_url: str | None = None) -> dict:
        url = f"https://www.amazon.com/dp/{asin}"
        result = {
            "asin": asin,
            "url": source_url or url,
            "input_url": url,
            "resolved_url": url,
            "resolved_asin": asin,
            "title": None,
            "brand": None,
            "seller": None,
            "seller_url": None,
            "price": None,
            "stock_left": None,
            "stock_message": None,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "status": "error",
            "status_label": "失败",
            "error_message": None,
            "diagnostic_evidence": "",
            "availability_text": "",
            "asin_candidates": [],
        }

        try:
            time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))
            self._open_product_page(url)

            for _ in range(2):
                self._dismiss_popups()

            current_url = self.driver.current_url or url
            result["resolved_url"] = current_url
            resolved_asin = self._resolve_actual_asin(asin, current_url)
            result["resolved_asin"] = resolved_asin

            if resolved_asin.upper() != asin.upper():
                retry_url, retry_asin, stable_mismatch, attempts = self._retry_original_asin(asin, url, resolved_asin)
                result["resolved_url"] = retry_url
                result["resolved_asin"] = retry_asin
                result["asin_check_attempts"] = attempts
                if retry_asin.upper() == asin.upper():
                    current_url = retry_url
                else:
                    self._attach_diagnostic_evidence(result, asin, retry_url)
                    if stable_mismatch:
                        self._mark_out_of_stock(result, retry_asin)
                    else:
                        self._mark_needs_review(result, retry_asin)
                    return result

            result["title"] = self._get_title()
            result["brand"] = self._get_brand_from_title(result["title"])
            result["price"] = self._get_price()
            if self._last_price_asin and self._last_price_asin.upper() != asin.upper():
                retry_url, retry_asin, stable_mismatch, attempts = self._retry_original_asin(asin, url, self._last_price_asin)
                result["resolved_url"] = retry_url
                result["resolved_asin"] = retry_asin
                result["asin_check_attempts"] = attempts
                if retry_asin.upper() == asin.upper():
                    current_url = retry_url
                    result["title"] = self._get_title()
                    result["brand"] = self._get_brand_from_title(result["title"])
                    result["price"] = self._get_price()
                else:
                    self._attach_diagnostic_evidence(result, asin, retry_url)
                    if stable_mismatch:
                        self._mark_out_of_stock(result, retry_asin)
                    else:
                        self._mark_needs_review(result, retry_asin)
                    return result
            result["seller"], result["seller_url"] = self._get_seller()
            result["stock_left"], result["stock_message"] = self._get_low_stock()
            self._attach_diagnostic_evidence(result, asin, self.driver.current_url or current_url)

            post_price_url = self.driver.current_url or current_url
            result["resolved_url"] = post_price_url
            post_price_asin = self._resolve_actual_asin(asin, post_price_url)
            result["resolved_asin"] = post_price_asin
            if post_price_asin.upper() != asin.upper():
                retry_url, retry_asin, stable_mismatch, attempts = self._retry_original_asin(asin, url, post_price_asin)
                result["resolved_url"] = retry_url
                result["resolved_asin"] = retry_asin
                result["asin_check_attempts"] = attempts
                if retry_asin.upper() != asin.upper():
                    self._attach_diagnostic_evidence(result, asin, retry_url)
                    if stable_mismatch:
                        self._mark_out_of_stock(result, retry_asin)
                    else:
                        self._mark_needs_review(result, retry_asin)
                    return result

            price_compare_reason = self._get_price_compare_indicator()
            if price_compare_reason:
                result["status"] = "price_compare"
                result["status_label"] = "比价"
                result["price"] = None
                result["error_message"] = f"页面提示 {price_compare_reason}，未显示可抓取价格"
            elif result["price"]:
                if result["stock_left"]:
                    result["status"] = "low_stock"
                    result["status_label"] = "即将缺货"
                    result["error_message"] = result["stock_message"] or f"仅剩 {result['stock_left']} 件库存"
                elif self._has_price_higher_than_typical():
                    result["status"] = "price_warn"
                    result["status_label"] = "价格偏高"
                    result["error_message"] = "页面提示 Price higher than typical"
                else:
                    result["status"] = "success"
                    result["status_label"] = "成功"
            else:
                unavailable_reason = self._get_unavailable_indicator()
                if unavailable_reason:
                    result["status"] = "out_of_stock"
                    result["status_label"] = "缺货"
                    result["error_message"] = f"页面未显示主商品价格：{unavailable_reason}"
                else:
                    result["error_message"] = "未抓取到当前商品主价格"

        except TimeoutException:
            try:
                timeout_url = self.driver.current_url or result["resolved_url"] or url
                result["resolved_url"] = timeout_url
                timeout_asin = self._resolve_actual_asin(asin, timeout_url)
                result["resolved_asin"] = timeout_asin
                if timeout_asin.upper() != asin.upper():
                    self._attach_diagnostic_evidence(result, asin, timeout_url)
                    self._mark_needs_review(result, timeout_asin)
                    return result
            except Exception:
                pass
            result["error_message"] = "页面加载超时"
        except WebDriverException as exc:
            result["error_message"] = f"浏览器异常: {str(exc)[:140]}"
        except Exception as exc:
            result["error_message"] = str(exc)[:200]

        if result["status"] == "error":
            result["status_label"] = "失败"

        logger.info("[%s] status=%s price=%s", asin, result["status"], result["price"])
        return result

    def _mark_out_of_stock(self, result: dict, actual_asin: str):
        result["status"] = "out_of_stock"
        result["status_label"] = "缺货"
        result["price"] = None
        result["error_message"] = f"输入 ASIN 与实际抓取页面链接 ASIN 不一致，页面 ASIN 为 {actual_asin}"

    def _mark_needs_review(self, result: dict, actual_asin: str):
        result["status"] = "needs_review"
        result["status_label"] = "待复查"
        result["price"] = None
        result["error_message"] = (
            f"ASIN 跳转结果不稳定，未采用跳转页面价格；最后页面 ASIN 为 {actual_asin}"
        )

    def _retry_original_asin(self, input_asin: str, url: str, first_actual_asin: str) -> tuple[str, str, bool, list[str]]:
        """Re-open the original ASIN. Stable repeated mismatch means the original ASIN is unavailable."""
        attempts = [str(first_actual_asin or "").upper()]
        last_url = self.driver.current_url or url
        last_asin = attempts[0] or input_asin

        for _ in range(max(0, ASIN_MISMATCH_RETRY)):
            try:
                time.sleep(MISMATCH_RETRY_DELAY)
                self._open_product_page(url)
                for _popup_try in range(2):
                    self._dismiss_popups()
                last_url = self.driver.current_url or url
                last_asin = self._resolve_actual_asin(input_asin, last_url)
            except TimeoutException:
                last_url = self.driver.current_url or last_url or url
                last_asin = self._resolve_actual_asin(input_asin, last_url)
            except Exception:
                last_asin = ""

            attempts.append(str(last_asin or "").upper())
            if str(last_asin or "").upper() == input_asin.upper():
                return last_url, input_asin.upper(), False, attempts

        non_empty_mismatches = [
            asin for asin in attempts if asin and asin != input_asin.upper()
        ]
        stable_mismatch = bool(non_empty_mismatches) and len(set(non_empty_mismatches)) == 1 and len(non_empty_mismatches) >= 2
        final_asin = non_empty_mismatches[-1] if non_empty_mismatches else (last_asin or input_asin)
        return last_url, final_asin, stable_mismatch, attempts

    def _get_compact_text(self, selectors: list[str], limit: int = 500) -> str:
        snippets: list[str] = []
        for selector in selectors:
            try:
                for element in self.driver.find_elements(By.CSS_SELECTOR, selector):
                    if not element.is_displayed():
                        continue
                    text = re.sub(r"\s+", " ", element.get_attribute("textContent") or element.text or "").strip()
                    if text and text not in snippets:
                        snippets.append(text)
            except Exception:
                continue
        value = " | ".join(snippets)
        return value[:limit]

    def _attach_diagnostic_evidence(self, result: dict, input_asin: str, current_url: str):
        """Keep the page evidence from scrape time, because out-of-stock pages may be hard to reopen later."""
        try:
            candidates = self._get_actual_page_asin_candidates(current_url)
        except Exception:
            candidates = []
        availability_text = self._get_compact_text(
            [
                "#availability",
                "#availability_feature_div",
                "#outOfStock",
                "#desktop_buybox",
                "#buybox",
                "#buyBoxAccordion",
                "#exports_desktop_qualifiedBuybox",
            ],
            limit=700,
        )
        result["input_url"] = result.get("input_url") or f"https://www.amazon.com/dp/{input_asin}"
        result["resolved_url"] = current_url or result.get("resolved_url") or result["input_url"]
        result["asin_candidates"] = candidates
        result["availability_text"] = availability_text
        result["diagnostic_evidence"] = (
            f"输入链接：{result['input_url']}；"
            f"实际页面：{result.get('resolved_url') or '-'}；"
            f"页面ASIN候选：{', '.join(candidates) if candidates else '-'}；"
            f"库存/购买框文案：{availability_text or '-'}；"
            f"抓取价格：{result.get('price') or '无价格'}"
        )

    def _resolve_actual_asin(self, input_asin: str, current_url: str) -> str:
        """Return a mismatched authoritative page ASIN first, if one exists."""
        candidates = self._get_actual_page_asin_candidates(current_url)
        for candidate in candidates:
            if candidate.upper() != input_asin.upper():
                return candidate
        return candidates[0] if candidates else input_asin

    def _get_actual_page_asin_candidates(self, current_url: str) -> list[str]:
        """Read ASINs from authoritative product URL/metadata sources."""
        cache_key = current_url or self.driver.current_url or ""
        if cache_key in self._asin_candidates_cache:
            return self._asin_candidates_cache[cache_key][:]

        candidates: list[str] = []

        def add_candidate(value: str):
            for candidate in self._extract_all_asins(value or ""):
                if candidate not in candidates:
                    candidates.append(candidate)

        def add_candidates_from_elements(selectors: list[str], attributes: list[str]):
            for selector in selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        for attribute in attributes:
                            value = element.get_attribute(attribute) or ""
                            add_candidate(value)
                        add_candidate(element.text or "")
                except Exception:
                    continue

        # Amazon variation pages can keep the requested ASIN in the URL while the
        # offer/price modules already point at the actually selected child ASIN.
        primary_page_asin_selectors = [
            "#all-offers-display-params",
            "#averageCustomerReviews",
            "#desktop_buybox [data-asin]",
            "#buybox [data-asin]",
            "#corePriceDisplay_desktop_feature_div [data-asin]",
            "#corePrice_feature_div [data-asin]",
            "#title_feature_div [data-asin]",
            "#availability [data-asin]",
            "#merchant-info [data-asin]",
            "#addToCart [data-asin]",
            "#addToCart input[name='ASIN']",
            "#desktop_buybox input[name='ASIN']",
            "#buybox input[name='ASIN']",
            "#twister_feature_div .selected [data-asin]",
            '#twister_feature_div [aria-checked="true"][data-asin]',
            '#twister_feature_div [aria-selected="true"][data-asin]',
        ]
        add_candidates_from_elements(
            primary_page_asin_selectors,
            [
                "data-asin",
                "data-csa-c-item-id",
                "data-dp-url",
                "href",
                "value",
                "content",
            ],
        )

        add_candidate(current_url or "")

        value_selectors = [
            "input#ASIN",
            'input[name="ASIN"]',
            'input[name="asin"]',
            "#ASIN",
        ]
        add_candidates_from_elements(value_selectors, ["value", "content", "data-asin"])

        selectors = [
            'link[rel="canonical"]',
            'meta[property="og:url"]',
            'meta[name="twitter:url"]',
            'meta[property="al:web:url"]',
        ]
        add_candidates_from_elements(selectors, ["href", "content"])

        detail_xpaths = [
            "//th[contains(translate(normalize-space(.), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'ASIN')]/following-sibling::td[1]",
            "//span[contains(translate(normalize-space(.), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'ASIN')]/following-sibling::span[1]",
            "//*[@id='detailBullets_feature_div']//span[contains(translate(normalize-space(.), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'ASIN')]",
            "//*[@id='productDetails_detailBullets_sections1']//tr[.//th[contains(translate(normalize-space(.), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'ASIN')]]",
        ]
        for xpath in detail_xpaths:
            try:
                for element in self.driver.find_elements(By.XPATH, xpath):
                    text = re.sub(r"\s+", " ", element.get_attribute("textContent") or element.text or "").strip()
                    if text and len(text) < 300:
                        add_candidate(text)
            except Exception:
                continue

        self._asin_candidates_cache[cache_key] = candidates[:]
        return candidates

    def _wait_for_product_signal(self):
        selectors = [
            "#productTitle",
            "#title",
            ".a-price-whole",
            "span.a-price span.a-offscreen",
            "#corePrice_feature_div span.a-offscreen",
        ]
        try:
            WebDriverWait(self.driver, ELEMENT_WAIT).until(
                lambda driver: any(driver.find_elements(By.CSS_SELECTOR, selector) for selector in selectors)
            )
        except Exception:
            pass

    def _dismiss_popups(self):
        xpaths = [
            '//span[contains(text(), "Continue shopping")]',
            '//a[contains(text(), "Continue shopping")]',
            '//button[contains(text(), "Continue shopping")]',
            '//span[text()="Continue"]',
            '//button[contains(text(), "Continue")]',
            '//input[@data-action-type="DISMISS"]',
            '//button[@data-action-type="DISMISS"]',
            '//span[contains(text(), "Dismiss")]',
        ]
        for xpath in xpaths:
            try:
                button = self.driver.find_element(By.XPATH, xpath)
                if button.is_displayed():
                    button.click()
            except Exception:
                continue

    def _get_title(self) -> str | None:
        for selector in ["#productTitle", "#title"]:
            try:
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                text = element.text.strip()
                if text and "Amazon.com" not in text and len(text) > 5:
                    return text
            except Exception:
                continue
        return None

    @staticmethod
    def _get_brand_from_title(title: str | None) -> str | None:
        """Use the first word of the product title as the brand."""
        if not title:
            return None
        words = title.strip().split()
        return words[0] if words else None

    def _clean_seller_text(self, text: str | None) -> str | None:
        if not text:
            return None
        value = re.sub(r"\s+", " ", text).strip(" :-\n\t")
        if not value:
            return None
        lower = value.lower()
        blocked = [
            "returns",
            "payment",
            "secure transaction",
            "refund",
            "replacement",
            "learn more",
            "details",
        ]
        if any(word in lower for word in blocked):
            return None
        prefixes = [
            "sold by",
            "seller",
            "shipper / seller",
            "ships from / sold by",
            "ships from and sold by",
        ]
        for prefix in prefixes:
            if lower.startswith(prefix):
                value = value[len(prefix):].strip(" :-")
                lower = value.lower()
        return value[:80] if value else None

    def _seller_from_element(self, element) -> tuple[str | None, str | None]:
        text = self._clean_seller_text((element.get_attribute("textContent") or element.text or "").strip())
        href = element.get_attribute("href") or ""
        if text:
            return text, urljoin("https://www.amazon.com", href) if href else None
        return None, None

    def _get_seller(self) -> tuple[str | None, str | None]:
        selectors = [
            "#sellerProfileTriggerId",
            "#merchant-info a",
            "#merchant-info",
            "#tabular-buybox [tabular-attribute-name='Sold by'] .tabular-buybox-text a",
            "#tabular-buybox [tabular-attribute-name='Sold by'] .tabular-buybox-text",
            "#tabular-buybox [tabular-attribute-name*='Seller'] .tabular-buybox-text a",
            "#tabular-buybox [tabular-attribute-name*='Seller'] .tabular-buybox-text",
            "#shipsFromSoldBy_feature_div a",
            "#offerDisplayFeature_soldBy a",
            "#seller-info a",
        ]
        for selector in selectors:
            try:
                for element in self.driver.find_elements(By.CSS_SELECTOR, selector):
                    if not element.is_displayed():
                        continue
                    seller, seller_url = self._seller_from_element(element)
                    if seller:
                        return seller, seller_url
            except Exception:
                continue

        label_xpaths = [
            "//*[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'shipper / seller')]",
            "//*[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'sold by')]",
            "//*[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'seller')]",
        ]
        for xpath in label_xpaths:
            try:
                labels = self.driver.find_elements(By.XPATH, xpath)
                for label in labels:
                    if not label.is_displayed():
                        continue
                    candidates = label.find_elements(By.XPATH, ".//a | ./following::a[1] | ./following::span[1] | ./following::div[1]")
                    for element in candidates:
                        if not element.is_displayed():
                            continue
                        seller, seller_url = self._seller_from_element(element)
                        if seller:
                            return seller, seller_url
            except Exception:
                continue

        return None, None

    def _normalize_price_text(self, text: str | None) -> str | None:
        if not text:
            return None
        value = re.sub(r"\s+", "", text).strip()
        match = re.search(r"\$?\d{1,5}(?:,\d{3})*(?:\.\d{2})?", value)
        if not match:
            return None
        price = match.group(0)
        if "." not in price and len(price.replace("$", "").replace(",", "")) > 5:
            return None
        return price if price.startswith("$") else f"${price}"

    def _visible_price_text(self, element) -> str | None:
        try:
            if not element.is_displayed():
                return None
            return self._normalize_price_text(element.get_attribute("textContent") or element.text)
        except Exception:
            return None

    def _resolve_container_asin(self, container) -> str | None:
        candidates: list[str] = []

        def add(value: str):
            for candidate in self._extract_all_asins(value or ""):
                if candidate not in candidates:
                    candidates.append(candidate)

        try:
            current = container
            for _ in range(6):
                for attribute in ["data-asin", "data-csa-c-item-id", "data-dp-url", "href", "value", "action"]:
                    add(current.get_attribute(attribute) or "")
                current = current.find_element(By.XPATH, "./parent::*")
        except Exception:
            pass

        selectors = [
            "[data-asin]",
            "input[name='ASIN']",
            "input[name='asin']",
            "a[href*='/dp/']",
            "a[href*='/gp/product/']",
            "form[action*='/dp/']",
            "form[action*='/gp/product/']",
        ]
        for selector in selectors:
            try:
                for element in container.find_elements(By.CSS_SELECTOR, selector):
                    for attribute in ["data-asin", "data-csa-c-item-id", "data-dp-url", "href", "value", "action"]:
                        add(element.get_attribute(attribute) or "")
                    add(element.text or "")
            except Exception:
                continue

        return candidates[0] if candidates else None

    def _get_price_from_container(self, container) -> tuple[str | None, str | None]:
        selectors = [
            "span.a-price:not(.a-text-price) span.a-offscreen",
            ".a-price:not(.a-text-price) .a-price-whole",
            "#priceblock_ourprice",
            "#priceblock_dealprice",
            "#priceblock_saleprice",
            "#newBuyBoxPrice",
        ]
        for selector in selectors:
            try:
                for element in container.find_elements(By.CSS_SELECTOR, selector):
                    price = self._visible_price_text(element)
                    if price:
                        if selector.endswith(".a-price-whole"):
                            try:
                                parent = element.find_element(By.XPATH, "./ancestor::*[contains(concat(' ', normalize-space(@class), ' '), ' a-price ')][1]")
                                fraction = parent.find_element(By.CSS_SELECTOR, ".a-price-fraction")
                                fraction_text = (fraction.get_attribute("textContent") or fraction.text or "").strip()
                                if fraction_text:
                                    return f"{price}.{fraction_text}", self._resolve_container_asin(container)
                            except Exception:
                                return price, self._resolve_container_asin(container)
                        return price, self._resolve_container_asin(container)
            except Exception:
                continue
        return None, None

    def _get_price(self) -> str | None:
        # Only trust price elements inside Amazon's current product price modules.
        # Global .a-price selectors can pick up recommendations, other sellers, or hidden modules.
        self._last_price_asin = None
        container_selectors = [
            "#corePriceDisplay_desktop_feature_div",
            "#corePrice_feature_div",
            "#apex_desktop",
            "#desktop_buybox",
            "#buybox",
            "#buyBoxAccordion",
        ]
        for selector in container_selectors:
            try:
                for container in self.driver.find_elements(By.CSS_SELECTOR, selector):
                    if not container.is_displayed():
                        continue
                    price, price_asin = self._get_price_from_container(container)
                    if price:
                        self._last_price_asin = price_asin
                        return price
            except Exception:
                continue
        return None

    def _has_price_higher_than_typical(self) -> bool:
        try:
            return "price higher than typical" in (self.driver.page_source or "").lower()
        except Exception:
            return False

    def _get_low_stock(self) -> tuple[int | None, str | None]:
        patterns = [
            r"only\s+(\d{1,4})\s+(?:left|remaining)\s+in\s+stock",
            r"(\d{1,4})\s+(?:left|remaining)\s+in\s+stock",
        ]

        def parse_stock(text: str | None) -> tuple[int | None, str | None]:
            if not text:
                return None, None
            normalized = re.sub(r"\s+", " ", text).strip()
            for pattern in patterns:
                match = re.search(pattern, normalized, re.IGNORECASE)
                if match:
                    count = int(match.group(1))
                    if 0 < count <= 10:
                        return count, f"仅剩 {count} 件库存"
            return None, None

        try:
            availability_elements = self.driver.find_elements(By.CSS_SELECTOR, "#availability")
            for element in availability_elements:
                if not element.is_displayed():
                    continue
                text = (element.text or "").strip()
                count, message = parse_stock(text)
                if count:
                    return count, message
                if re.search(r"\bin\s+stock\b", text, re.IGNORECASE):
                    return None, None
        except Exception:
            pass

        selectors = [
            "#availability span",
            "#availability_feature_div",
            "#outOfStock",
        ]
        for selector in selectors:
            try:
                for element in self.driver.find_elements(By.CSS_SELECTOR, selector):
                    if not element.is_displayed():
                        continue
                    count, message = parse_stock(element.text)
                    if count:
                        return count, message
            except Exception:
                continue

        return None, None

    def _get_unavailable_indicator(self) -> str | None:
        phrases = [
            ("currently unavailable", "Currently unavailable"),
            ("temporarily out of stock", "Temporarily out of stock"),
            ("out of stock", "Out of stock"),
            ("see all buying options", "See All Buying Options"),
            ("available from these sellers", "Available from these sellers"),
        ]
        selectors = [
            "#availability",
            "#availability_feature_div",
            "#outOfStock",
            "#desktop_buybox",
            "#buybox",
            "#buyBoxAccordion",
            "#exports_desktop_qualifiedBuybox",
        ]
        for selector in selectors:
            try:
                for element in self.driver.find_elements(By.CSS_SELECTOR, selector):
                    if not element.is_displayed():
                        continue
                    text = re.sub(r"\s+", " ", element.text or "").strip().lower()
                    if not text or len(text) > 1500:
                        continue
                    for phrase, label in phrases:
                        if phrase in text:
                            return label
            except Exception:
                continue
        return None

    def _get_price_compare_indicator(self) -> str | None:
        phrases = [
            ("high price", "High price"),
            ("no featured offers available", "No featured offers available"),
        ]
        try:
            contains_clauses = " or ".join(
                [
                    "contains(translate(normalize-space(.), "
                    "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), "
                    f"'{phrase}')"
                    for phrase, _ in phrases
                ]
            )
            elements = self.driver.find_elements(By.XPATH, f"//*[{contains_clauses}]")
            for element in elements:
                text = (element.text or "").strip().lower()
                if not element.is_displayed() or len(text) > 100:
                    continue
                for phrase, label in phrases:
                    if phrase in text:
                        return label

            return None
        except Exception:
            return None
