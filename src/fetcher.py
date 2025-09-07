import re
from contextlib import contextmanager
from typing import Iterator, Optional

from tenacity import retry, stop_after_attempt, wait_fixed
from playwright.sync_api import sync_playwright, Browser, Page

from .config import Settings, EHI_BASE_URL, EHI_TZ


@contextmanager
def browser_ctx(headful: bool = False) -> Iterator[tuple[Browser, Page]]:
    with sync_playwright() as p:
        # 为了在无头模式下也稳定触发前端交互，这里在 headless 下也给一点 slow_mo
        slow = 100 if headful else 50
        browser = p.chromium.launch(headless=not headful, slow_mo=slow)
        context = browser.new_context(locale="zh-CN", timezone_id=EHI_TZ, user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
        ))
        page = context.new_page()
        try:
            yield browser, page
        finally:
            context.close()
            browser.close()


def parse_price_from_text(text: str) -> Optional[float]:
    # 更严格：优先匹配带货币符号的价格；避免误匹配 “1.2T”“5座”等
    # 1) 带货币符号
    m = re.search(r"(?:¥|RMB|￥)\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)", text)
    # 2) 或者数字后面紧跟价格语境（/日均、天、元），避免小数字
    if not m:
        m = re.search(r"([0-9]{2,5}(?:\.[0-9]{1,2})?)\s*(?:/\s*日均|日均|/\s*天|天|元)", text)
    if not m:
        return None
    raw = m.group(1).replace(",", "")
    try:
        val = float(raw)
        # 保护：过滤明显不是价格的极小值（如 1.2T、5 座等已通过语境避免，这里再兜底）
        if val < 20:
            return None
        return val
    except ValueError:
        return None


def _extract_price_near_model(page: Page, car_name: str) -> Optional[float]:
    # Try to find an element containing the car name and extract price nearby
    locator = page.locator(f"text={car_name}")
    if locator.count() == 0:
        name_compact = car_name.replace(" ", "")
        locator = page.locator(f"text={name_compact}")
    if locator.count() == 0:
        return None

    handle = locator.first
    container = handle.locator("xpath=ancestor-or-self::div[1]")
    if container.count() > 0 and container.bounding_box() and container.bounding_box()["height"] < 40:
        container = handle.locator("xpath=ancestor::div[1]")
    try:
        text = container.inner_text()
        price = parse_price_from_text(text)
        if price is not None:
            return price
    except Exception:
        pass

    price_like = handle.locator("xpath=ancestor::div[1]//*[contains(text(),'¥') or contains(text(),'￥') or matches(text(),'\\d{2,}')]")
    if price_like.count() > 0:
        for i in range(min(10, price_like.count())):
            try:
                t = price_like.nth(i).inner_text()
                p = parse_price_from_text(t)
                if p is not None:
                    return p
            except Exception:
                continue
    return None

def _extract_from_cartype_lists(page: Page, car_name: str) -> Optional[float]:
    # 针对当前页面结构的精准解析：只从价格容器读取，避免误取“1.2T”等规格数值
    try:
        cards = page.locator(".cartype-list")
        n = cards.count()
    except Exception:
        n = 0
    if n == 0:
        return None

    target = (car_name or "").strip()
    synonyms = [target] if target else []
    if "大众" not in target:
        synonyms.append("大众")
    if ("新探影" not in target) and ("探影" not in target):
        synonyms.append("探影")

    matched_prices: list[float] = []
    for i in range(min(40, n)):
        card = cards.nth(i)
        try:
            name = card.locator(".cartype-name").first.inner_text().strip()
        except Exception:
            name = ""
        matched = False
        if target and target in name:
            matched = True
        elif all(kw in name for kw in [kw for kw in synonyms if kw in ("大众", "探影", "新探影")]):
            matched = True
        if not matched:
            continue
        # 仅从价格容器读取，优先 em 文本
        try:
            num = card.locator(".cartype-price .cartype-price-current em").first.inner_text()
            # 这里 num 一般就是纯数字，如 698
            p = None
            try:
                p = float(num.replace(",", ""))
            except Exception:
                p = parse_price_from_text(num)
            if p is not None:
                matched_prices.append(p)
        except Exception:
            pass
    if matched_prices:
        # 返回最小价（同车型不同取还方式时，取最低）
        return min(matched_prices)
    return None


def _debug_dump(page: Page, s: Settings, name: str) -> None:
    if not s.debug:
        return
    import os
    os.makedirs(s.debug_dir, exist_ok=True)
    safe = name.replace("/", "_")
    try:
        page.screenshot(path=f"{s.debug_dir}/{safe}.png", full_page=True)
    except Exception:
        pass
    try:
        html = page.content()
        with open(f"{s.debug_dir}/{safe}.html", "w", encoding="utf-8") as f:
            f.write(html)
    except Exception:
        pass


def _form_fill_search(page: Page, s: Settings) -> None:
    # Fill pickup/return cities and stores, pickup/return dates and times, then submit
    print("[form] open firstStep page…")
    page.goto(EHI_BASE_URL, wait_until="domcontentloaded")
    # 等待关键输入框渲染完成
    try:
        page.wait_for_selector("#pickupcity", timeout=15000, state="visible")
        page.wait_for_selector("#returncity", timeout=15000, state="visible")
    except Exception:
        page.wait_for_load_state("networkidle")
    _debug_dump(page, s, "01_loaded_firstStep")

    # 调试输出工具：仅在 DEBUG=1 时打印
    def _dbg(msg: str) -> None:
        if s.debug:
            try:
                print(f"[dbg] {msg}")
            except Exception:
                pass

    # 仅设置城市，不改动门店
    def fill_city(field_id: str, city: str) -> None:
        try:
            el = page.locator(f"#{field_id}").first
            if el.count() == 0:
                return
            # 最多尝试两轮：输入 -> 点击候选 -> 校验
            for _ in range(2):
                el.click()
                el.fill("")
                _dbg(f"city[{field_id}] typing '{city}'")
                el.type(city, delay=20)
                page.wait_for_timeout(150)
                # 先按一次回车：该站点会弹出自定义城市候选（.city-search）
                try:
                    page.keyboard.press("Enter")
                    _dbg(f"city[{field_id}] pressed Enter")
                except Exception:
                    pass
                page.wait_for_timeout(150)

                # 明确等待候选出现，并点击完全匹配的项（必须点击后才继续下一步）
                variants = [city, f"{city}市"]
                # 优先匹配该站点自定义候选：.city-search
                city_dd = page.locator(".city-search").first
                clicked = False
                try:
                    city_dd.wait_for(state="visible", timeout=1200)
                    _dbg(".city-search visible")
                    for v in variants:
                        opt = city_dd.locator(f"xpath=.//li[normalize-space(text())='{v}']").first
                        if opt.count() > 0:
                            try:
                                opt.scroll_into_view_if_needed()
                            except Exception:
                                pass
                            _dbg(f"city[{field_id}] click candidate '{v}'")
                            opt.click()
                            clicked = True
                            break
                except Exception:
                    _dbg(".city-search not visible; fallback dropdown")

                # 若自定义候选未命中，则退回到通用 AntD 类下拉容器
                dropdowns = page.locator(
                    ", ".join([
                        ".ant-select-dropdown:not(.ant-select-dropdown-hidden)",
                        ".ant-cascader-dropdown:not(.ant-cascader-dropdown-hidden)",
                        ".ant-dropdown:not(.ant-dropdown-hidden)",
                        "[role='listbox']",
                    ])
                )
                if not clicked:
                    try:
                        dropdowns.wait_for(state="visible", timeout=3000)
                        _dbg("AntD dropdown visible")
                    except Exception:
                        _dbg("AntD dropdown not visible")
                    for v in variants:
                        # 先在可见下拉里找完全匹配
                        opt = dropdowns.locator(
                            f"xpath=.//*[self::div or self::span or self::li or self::a][normalize-space(text())='{v}' and not(ancestor::*[contains(@style,'display: none')])]"
                        ).first
                        if opt.count() == 0:
                            # 退一步：全局第一个可见 li/div/a/span 精确文本
                            opt = page.locator(
                                f"xpath=(//*[self::li or self::div or self::a or self::span][normalize-space(text())='{v}' and not(ancestor::*[contains(@style,'display: none')])])[1]"
                            )
                        if opt.count() > 0:
                            try:
                                opt.scroll_into_view_if_needed()
                            except Exception:
                                pass
                            _dbg(f"city[{field_id}] click AntD candidate '{v}'")
                            opt.click()
                            clicked = True
                            break

                # 如果没有可点项，使用键盘选中第一项
                if not clicked:
                    _dbg(f"city[{field_id}] fallback ArrowDown+Enter")
                    page.keyboard.press("ArrowDown")
                    page.keyboard.press("Enter")
                    # 键盘选择后也等待一会，避免立即进入下一步
                    page.wait_for_timeout(600)

                # 校验是否已选中目标城市
                title = el.get_attribute("title") or ""
                value = el.get_attribute("value") or ""
                if (city in title) or (city in value):
                    # 等待候选消失或门店输入框可用
                    try:
                        page.wait_for_function("() => document.querySelector('.city-search')===null || getComputedStyle(document.querySelector('.city-search')).display==='none'", timeout=1200)
                    except Exception:
                        pass
                    _dbg(f"city[{field_id}] selected title='{title}' value='{value}'")
                    break
            else:
                # 两轮后仍未命中，强制赋值并触发事件
                _dbg(f"city[{field_id}] force set '{city}'")
                page.evaluate(
                    "(el, val) => { el.removeAttribute('readonly'); el.value = val; el.setAttribute('value', val); el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true})); el.blur(); }",
                    el,
                    city,
                )
        except Exception:
            pass
    # 门店选择逻辑已移除，沿用页面默认门店

    # 日期（仅日期）选择：点击对应日期输入，打开 AntD 日历，点指定 title=YYYY-MM-DD 的单元格
    def set_date(date_id: str, date_label: str, date_value: str) -> bool:
        print(f"[form] set {date_label}: {date_value}")
        inp = page.locator(f"#{date_id}").first
        if inp.count() == 0:
            inp = page.locator(f"xpath=//*[contains(text(), '{date_label}')]/following::input[1]").first
        if inp.count() == 0:
            print(f"[form] err: 未找到 {date_label} 输入框")
            return False
        # 最多两轮稳态点击：打开对应弹层 -> 选择日期 -> 等待输入更新
        for attempt in range(2):
            try:
                # 打开日历弹层（确保点击的是该输入的容器）
                try:
                    inp.scroll_into_view_if_needed()
                    container = inp.locator("xpath=ancestor::div[contains(@class,'ant-picker')][1]")
                    (container if container.count() > 0 else inp).click()
                except Exception:
                    inp.click(force=True)
                dd_all = page.locator(".ant-picker-dropdown:not(.ant-picker-dropdown-hidden)")
                dd_all.wait_for(state="visible", timeout=6000)
                dd = dd_all.last
                # 选择指定日期
                cell = dd.locator(f".ant-picker-cell[title='{date_value}']").first
                if cell.count() == 0:
                    # 可能跨月，向右翻最多 12 次
                    try:
                        for _ in range(12):
                            dd.locator(".ant-picker-header-next-btn").first.click()
                            page.wait_for_timeout(120)
                            cell = dd.locator(f".ant-picker-cell[title='{date_value}']").first
                            if cell.count() > 0:
                                break
                    except Exception:
                        pass
                if cell.count() > 0:
                    try:
                        cell.scroll_into_view_if_needed()
                    except Exception:
                        pass
                    cell.click()
                    # 等待输入值更新
                    try:
                        page.wait_for_function(
                            "(el, v) => (el.getAttribute('value')||'')===v || (el.getAttribute('title')||'')===v",
                            arg=inp,
                            timeout=1500,
                            **{"v": date_value}
                        )
                    except Exception:
                        pass
                # 关闭弹层
                try:
                    ok_btn = dd.locator("xpath=.//button[normalize-space(text())='确定']").first
                    if ok_btn.count() > 0:
                        ok_btn.click()
                except Exception:
                    pass
                page.keyboard.press("Escape")
            except Exception as e:
                _dbg(f"date[{date_id}] exception: {e}")
            # 校验是否已生效
            try:
                val_now = inp.get_attribute("value") or ""
                title_now = inp.get_attribute("title") or ""
                if (date_value in val_now) or (date_value in title_now):
                    return True
            except Exception:
                pass
            # 若第一轮未成功，短暂等待后重试
            page.wait_for_timeout(120)
        # 校验
        try:
            val = inp.get_attribute("value") or ""
            title = inp.get_attribute("title") or ""
            ok = (date_value in val) or (date_value in title)
            _dbg(f"date[{date_id}] check val='{val}' title='{title}' ok={ok}")
            if not ok:
                # 最后兜底：直接赋值 + 触发事件 + blur（注意：部分站点不会更新内部状态，此兜底可能无效）
                print(f"[form] warn: {date_label} 未生效 -> 直接赋值兜底")
                try:
                    page.evaluate(
                        "(el, val) => { el.removeAttribute('readonly'); el.value = val; el.setAttribute('value', val); el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true})); el.blur(); }",
                        inp,
                        date_value,
                    )
                    page.wait_for_timeout(120)
                    val2 = inp.get_attribute("value") or ""
                    title2 = inp.get_attribute("title") or ""
                    ok2 = (date_value in val2) or (date_value in title2)
                    _dbg(f"date[{date_id}] after force-set val='{val2}' title='{title2}' ok={ok2}")
                    return ok2
                except Exception:
                    return False
            return True
        except Exception:
            return False

    # 已移除时间选择逻辑（沿用页面默认时间），避免复杂的下拉兼容问题
    # 保留占位，防止意外调用
    def set_time_only(time_id: str, time_label: str, time_value: str) -> None:
        _dbg(f"skip time select [{time_id}] -> use default")
        return


    # 仅设置城市（门店使用页面默认）
    fill_city("pickupcity", s.pickup_city)
    fill_city("returncity", s.return_city)

    # 简单直接：仅设置日期，跳过时间选择，使用页面默认时间
    ok1 = set_date("pickupdate", "取车日期", s.pickup_date)
    ok2 = set_date("returndate", "还车日期", s.return_date)
    print("[form] skip 取/还车时间选择，沿用页面默认时间")
    _debug_dump(page, s, "02_filled_form")

    # Click search button
    try:
        print("[form] click 查询…")
        # 匹配“查询/查 询”等变体
        import re as _re
        page.get_by_role("button", name=_re.compile(r"查\s*询")).first.click()
    except Exception:
        try:
            page.locator("button:has-text('查')").first.click()
        except Exception:
            try:
                page.locator("text=查询").first.click()
            except Exception:
                # last resort: press Enter
                page.keyboard.press("Enter")

    # Wait for results to load: look for car cards or booking buttons
    # 适当等待页面刷新，确保渲染完成
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(800)
    try:
        page.wait_for_selector(".cartype-list, text=预订", timeout=15000)
    except Exception:
        try:
            page.wait_for_selector("text=日均", timeout=6000)
        except Exception:
            pass
    _debug_dump(page, s, "03_results")


def _extract_by_cards(page: Page, car_name: str) -> Optional[float]:
    # 备用方案：以“预订”按钮为锚点，向上找到卡片容器，匹配车型关键字并解析价格
    keywords = []
    if car_name and car_name.strip():
        keywords.append(car_name.strip())
    # 中文关键词启发（大众 + 探影/新探影）
    if "大众" not in "".join(keywords):
        keywords.append("大众")
    if "探影" not in "".join(keywords):
        keywords.append("探影")

    buttons = page.locator("text=预订")
    count = buttons.count()
    for i in range(min(20, count)):
        btn = buttons.nth(i)
        card = btn.locator("xpath=ancestor::div[1]")
        try:
            text = card.inner_text()
        except Exception:
            try:
                text = btn.locator("xpath=ancestor::div[2]").inner_text()
            except Exception:
                continue
        if all(k in text for k in [kw for kw in keywords if kw]):
            # 更谨慎：只在价格容器附近找
            try:
                price_text = btn.locator("xpath=ancestor::li[contains(@class,'cartype-operate')]//div[contains(@class,'cartype-price-current')]//text()")
                # Playwright 不支持直接 text() 列表，这里退回用祖先块文本解析
                p = parse_price_from_text(text)
            except Exception:
                p = parse_price_from_text(text)
            if p is not None:
                return p

    # 最后尝试：页面任意节点同时包含“大众”与“探影/新探影”
    try:
        nodes = page.locator("xpath=//*[contains(normalize-space(.),'大众') and (contains(normalize-space(.),'探影') or contains(normalize-space(.),'新探影'))]")
        n = nodes.count()
        for i in range(min(10, n)):
            node = nodes.nth(i)
            try:
                text = node.inner_text()
                p = parse_price_from_text(text)
                if p is not None:
                    return p
            except Exception:
                continue
    except Exception:
        pass
    return None


@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def get_current_price(settings: Settings) -> Optional[float]:
    # 始终使用 firstStep 表单模式，地址固定
    with browser_ctx(headful=settings.headful) as (_browser, page):
        _form_fill_search(page, settings)

        # 优先使用针对页面结构的解析
        price = _extract_from_cartype_lists(page, settings.car_name)
        if price is None:
            # 其次使用名称就近解析
            price = _extract_price_near_model(page, settings.car_name)
        if price is None:
            # Try scrolling to load more and retry
            try:
                page.mouse.wheel(0, 1200)
                page.wait_for_timeout(800)
                price = _extract_from_cartype_lists(page, settings.car_name) or _extract_price_near_model(page, settings.car_name)
            except Exception:
                pass
        if price is None:
            # 针对 .cartype-list 的直接解析
            try:
                price = _extract_from_cartype_lists(page, settings.car_name)
            except Exception:
                pass
        if price is None:
            # 尝试卡片式提取
            try:
                price = _extract_by_cards(page, settings.car_name)
            except Exception:
                pass
        return price
