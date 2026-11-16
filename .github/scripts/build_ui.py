# -*- coding: utf-8 -*-
"""用现有 gettext 词条生成当前语言的界面文件 (CI / 本地打包共用).

中文原文就是 msgid, 所以直接拿中文当 key. 只处理三处:
  * HTML 文本节点 (跳过 script/style)
  * title / aria-label / placeholder / alt / data-title / data-desc 属性
  * <script> 里的 JS 字符串字面量 (跳过注释)

输出: build/ui/ui.<lang>.html, 由 gui.py 按 LANGUAGE_SCRIPT 选择加载.
生成物不要提交到仓库.
"""
from __future__ import annotations

import argparse
import gettext
import html as html_lib
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SRC = ROOT / "src" / "ui.html"
DEFAULT_LOCALE = ROOT / "locale"
DEFAULT_OUT_DIR = ROOT / "build" / "ui"

TRANSLATABLE_ATTRS = {"title", "aria-label", "placeholder", "alt",
                      "data-title", "data-desc"}
HAS_CJK = re.compile(r"[一-鿿]")


def load_catalog(locale_dir: Path, lang: str) -> dict[str, str]:
    trans = gettext.translation("messages", str(locale_dir), languages=[lang])
    return {
        key: value
        for key, value in trans._catalog.items()
        if isinstance(key, str) and key and isinstance(value, str)
    }


def translate_text(text: str, catalog: dict[str, str]) -> str:
    key = text.strip()
    if not key or key not in catalog:
        return text
    start = text.find(key)
    # 词条是纯文本; 转义后再放回 HTML 文本节点, 避免 & / < 破坏文档.
    translated = html_lib.escape(catalog[key], quote=False)
    return text[:start] + translated + text[start + len(key):]


def escape_js_string(text: str, quote: str) -> str:
    """把译文放进同一种引号的 JS 字符串里."""
    return (text.replace("\\", "\\\\")
                .replace(quote, "\\" + quote)
                .replace("\r", "\\r")
                .replace("\n", "\\n"))


def translate_attrs(raw_tag: str, catalog: dict[str, str], stats: dict) -> str:
    def repl(match: re.Match) -> str:
        name, quote, value = match.group(1), match.group(2), match.group(3)
        if name.lower() not in TRANSLATABLE_ATTRS:
            return match.group(0)
        translated = catalog.get(value)
        if translated is None:
            if HAS_CJK.search(value):
                stats["missed_attr"].append(f"{name}={value}")
            return match.group(0)
        # 属性值必须转义, 否则译文里的引号会提前结束属性.
        translated = html_lib.escape(translated, quote=True)
        return f"{name}={quote}{translated}{quote}"

    return re.sub(
        r"([A-Za-z_:][-A-Za-z0-9_:.]*)\s*=\s*([\"'])(.*?)\2",
        repl,
        raw_tag,
        flags=re.S,
    )


def _scan_string(src: str, start: int, quote: str) -> tuple[str, int]:
    """返回 (字符串原始内容, 结束引号之后的位置)."""
    i = start + 1
    out = []
    while i < len(src):
        ch = src[i]
        if ch == "\\":
            out.append(src[i:i + 2])
            i += 2
            continue
        if ch == quote:
            return "".join(out), i + 1
        out.append(ch)
        i += 1
    return "".join(out), i


def translate_js(src: str, catalog: dict[str, str], stats: dict) -> str:
    """替换 JS 字符串字面量; 跳过注释和正则字面量."""
    out = []
    i = 0
    n = len(src)
    prev_sig = ""

    while i < n:
        ch = src[i]

        if ch == "/" and i + 1 < n and src[i + 1] == "/":
            end = src.find("\n", i)
            if end == -1:
                out.append(src[i:])
                break
            out.append(src[i:end])
            i = end
            continue

        if ch == "/" and i + 1 < n and src[i + 1] == "*":
            end = src.find("*/", i + 2)
            if end == -1:
                out.append(src[i:])
                break
            out.append(src[i:end + 2])
            i = end + 2
            continue

        if ch in ("'", '"'):
            raw, end = _scan_string(src, i, ch)
            translated = catalog.get(raw) if raw else None
            if translated is not None:
                out.append(ch + escape_js_string(translated, ch) + ch)
                stats["js"] += 1
            else:
                if raw and HAS_CJK.search(raw):
                    stats["missed_js"].append(raw)
                out.append(src[i:end])
            i = end
            prev_sig = ch
            continue

        if ch == "`":
            end = i + 1
            while end < n:
                if src[end] == "\\":
                    end += 2
                    continue
                if src[end] == "`":
                    break
                end += 1
            raw = src[i + 1:end]
            translated = catalog.get(raw) if raw else None
            if translated is not None:
                out.append("`" + escape_js_string(translated, "`") + "`")
                stats["js"] += 1
            else:
                if raw and HAS_CJK.search(raw):
                    stats["missed_js"].append(raw)
                out.append(src[i:end + 1])
            i = end + 1
            prev_sig = "`"
            continue

        if ch == "/":
            # 区分正则和除法: 前一个有效字符是操作符/括号时视为正则.
            if prev_sig in ("", "=", "(", ":", ",", "[", "!", "&", "|", "?",
                            "{", "}", ";", "+", "-", "*", "%", "^", "~", "<", ">"):
                end = i + 1
                in_class = False
                while end < n:
                    c = src[end]
                    if c == "\\":
                        end += 2
                        continue
                    if c == "[":
                        in_class = True
                    elif c == "]":
                        in_class = False
                    elif c == "/" and not in_class:
                        break
                    elif c == "\n":
                        break
                    end += 1
                out.append(src[i:end + 1])
                i = end + 1
                prev_sig = "/"
                continue

        out.append(ch)
        if not ch.isspace():
            prev_sig = ch
        i += 1

    return "".join(out)


class UiTranslator(HTMLParser):
    def __init__(self, catalog: dict[str, str]):
        super().__init__(convert_charrefs=False)
        self.catalog = catalog
        self.out: list[str] = []
        self.in_script = False
        self.in_style = False
        self.stats = {"text": 0, "attr": 0, "js": 0,
                      "missed_text": [], "missed_attr": [], "missed_js": []}

    # ---- 标签 ----
    def handle_starttag(self, tag, attrs):
        raw = self.get_starttag_text() or f"<{tag}>"
        if tag == "html":
            raw = re.sub(r'lang\s*=\s*"zh-CN"', 'lang="en"', raw)
        translated = translate_attrs(raw, self.catalog, self.stats)
        if translated != raw:
            self.stats["attr"] += 1
        self.out.append(translated)
        if tag == "script":
            self.in_script = True
        elif tag == "style":
            self.in_style = True

    def handle_startendtag(self, tag, attrs):
        raw = self.get_starttag_text() or f"<{tag}/>"
        translated = translate_attrs(raw, self.catalog, self.stats)
        if translated != raw:
            self.stats["attr"] += 1
        self.out.append(translated)

    def handle_endtag(self, tag):
        self.out.append(f"</{tag}>")
        if tag == "script":
            self.in_script = False
        elif tag == "style":
            self.in_style = False

    # ---- 内容 ----
    def handle_data(self, data):
        if self.in_script:
            data = translate_js(data, self.catalog, self.stats)
            self.out.append(data)
            return
        if self.in_style:
            self.out.append(data)
            return
        translated = translate_text(data, self.catalog)
        if translated != data:
            self.stats["text"] += 1
        elif HAS_CJK.search(data):
            self.stats["missed_text"].append(data.strip()[:200])
        self.out.append(translated)

    def handle_comment(self, data):
        self.out.append(f"<!--{data}-->")

    def handle_decl(self, decl):
        self.out.append(f"<!{decl}>")

    def handle_pi(self, data):
        self.out.append(f"<?{data}>")

    def handle_entityref(self, name):
        self.out.append(f"&{name};")

    def handle_charref(self, name):
        self.out.append(f"&#{name};")

    def unknown_decl(self, data):
        self.out.append(f"<![{data}]>")


def build(src: Path, locale_dir: Path, lang: str, out_dir: Path,
          strict: bool = False) -> int:
    catalog = load_catalog(locale_dir, lang)
    html = src.read_text(encoding="utf-8")

    parser = UiTranslator(catalog)
    parser.feed(html)
    parser.close()
    translated = "".join(parser.out)

    out = out_dir / f"ui.{lang}.html"
    report = out_dir / f"ui.{lang}.report.txt"

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(translated, encoding="utf-8")

    missed_text = parser.stats["missed_text"]
    missed_attr = parser.stats["missed_attr"]
    missed_js = parser.stats["missed_js"]
    lines = [
        f"source : {src}",
        f"output : {out}",
        f"catalog: {len(catalog)} entries",
        f"translated: text={parser.stats['text']} "
        f"attr={parser.stats['attr']} js={parser.stats['js']}",
        "",
        f"untranslated text nodes ({len(missed_text)})",
        *missed_text,
        "",
        f"untranslated attributes ({len(missed_attr)})",
        *missed_attr,
        "",
        f"untranslated js strings ({len(missed_js)})",
        *missed_js,
    ]
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines), encoding="utf-8")

    print(f"generated: {out}")
    print(f"report   : {report}")
    print(f"catalog={len(catalog)} text={parser.stats['text']} "
          f"attr={parser.stats['attr']} js={parser.stats['js']} "
          f"missed_text={len(missed_text)} "
          f"missed_attr={len(missed_attr)} "
          f"missed_js={len(missed_js)}")

    if strict and (missed_text or missed_attr or missed_js):
        print("ERROR: untranslated UI strings found, see report.", file=sys.stderr)
        return 1
    return 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, default=DEFAULT_SRC)
    ap.add_argument("--locale", type=Path, default=DEFAULT_LOCALE)
    ap.add_argument("--lang", default="en_US")
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--strict", action="store_true",
                    help="有未翻译的界面文案时返回非零退出码")
    args = ap.parse_args()
    sys.exit(build(args.src, args.locale, args.lang, args.out_dir, args.strict))


if __name__ == "__main__":
    main()
