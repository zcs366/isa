#!/usr/bin/env python3
"""章鱼外部搜索 — DuckDuckGo HTML 搜索（零API费）
用法: python3 octopus_web_search.py <关键词>

可被 octopus_search.py 或 Hermes plugin 调用来获取外部搜索结果。
输出格式: [WEB]标题 | URL
         摘要内容
"""
import sys, urllib.request, urllib.parse
import re

SEARCH_URL = "https://html.duckduckgo.com/html/"


def search(query, max_results=5):
    """搜索 DuckDuckGo HTML 版，返回结构化结果"""
    results = []
    try:
        data = urllib.parse.urlencode({"q": query.strip()}).encode()
        req = urllib.request.Request(
            SEARCH_URL,
            data=data,
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
            }
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        # 解析 DuckDuckGo HTML 搜索结果
        # 结果块: <a class="result__a" href="...">title</a>
        #        <a class="result__snippet" href="...">snippet</a>
        
        # 方法1: 找 result__a 链接
        link_pattern = re.compile(
            r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
            re.DOTALL
        )
        snippet_pattern = re.compile(
            r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
            re.DOTALL
        )
        
        links = link_pattern.findall(html)
        snippets = [re.sub(r'<[^>]+>', '', s).strip() for s in snippet_pattern.findall(html)]
        
        for i, (href, title_html) in enumerate(links):
            if i >= max_results:
                break
            title = re.sub(r'<[^>]+>', '', title_html).strip()
            # 清理 DuckDuckGo 重定向链接
            if "/redirect?*uddg=" in href:
                uddg = re.search(r'uddg=([^&]+)', href)
                if uddg:
                    href = urllib.parse.unquote(uddg.group(1))
            snippet = snippets[i] if i < len(snippets) else ""
            if title and href and not href.startswith("javascript"):
                results.append((title, href, snippet[:200]))
        
        # 方法2: 如果方法1没找到，尝试旧版 Lite 格式
        if not results:
            # 尝试找 tr 中的链接 (Lite 版)
            lite_pattern = re.compile(
                r'<a[^>]*href="(https?://[^"]+)"[^>]*>([^<]+)</a>',
                re.DOTALL
            )
            for href, title in lite_pattern.findall(html):
                if title.strip() and not any(
                    x in href for x in ["duckduckgo.com", "javascript"]
                ):
                    results.append((title.strip(), href, ""))
                    if len(results) >= max_results:
                        break

    except Exception as e:
        results.append((f"[错误] {e}", "", ""))

    return results


def main():
    if len(sys.argv) < 2:
        print("用法: python3 octopus_web_search.py <关键词>")
        sys.exit(1)

    query = " ".join(sys.argv[1:])
    print(f"🌐 章鱼外部搜索: {query}")
    print("=" * 50)

    results = search(query)
    if not results:
        print("无结果。")
        return

    for title, href, snippet in results:
        print(f"\n  [WEB] {title}")
        if href:
            print(f"         {href}")
        if snippet:
            print(f"  {snippet}")

    print(f"\n共 {len(results)} 条结果。")


if __name__ == "__main__":
    main()
