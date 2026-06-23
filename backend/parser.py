from __future__ import annotations

import html
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from sources import SOURCES


USER_AGENT = "KulturnayaLenta/1.0 (+http://localhost:3000; educational parser)"
MAX_BODY = 1_200_000
CITY_NAMES = [
    "Москва",
    "Санкт-Петербург",
    "Казань",
    "Омск",
    "Красноярск",
    "Владивосток",
    "Самара",
    "Нижний Новгород",
]


@dataclass
class ParsedPage:
    title: str = ""
    h1: str = ""
    description: str = ""
    date: str = ""
    anchors: list[tuple[str, str]] | None = None
    paragraphs: list[str] | None = None
    json_ld: list[dict] | None = None


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.anchors: list[tuple[str, str]] = []
        self.paragraphs: list[str] = []
        self.times: list[str] = []
        self.json_ld: list[dict] = []
        self._tag_stack: list[str] = []
        self._capture: str | None = None
        self._buffer: list[str] = []
        self._href: str | None = None
        self._title = ""
        self._h1 = ""
        self._script_type = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self._tag_stack.append(tag)

        if tag == "meta":
            key = attrs.get("property") or attrs.get("name")
            value = attrs.get("content")
            if key and value:
                self.meta[key.lower()] = clean_text(value)

        if tag == "a" and attrs.get("href"):
            self._href = attrs.get("href")
            self._capture = "a"
            self._buffer = []

        if tag in {"title", "h1", "p"}:
            self._capture = tag
            self._buffer = []

        if tag == "time" and attrs.get("datetime"):
            self.times.append(attrs["datetime"])

        if tag == "script" and "ld+json" in attrs.get("type", ""):
            self._capture = "script"
            self._script_type = "ld+json"
            self._buffer = []

    def handle_endtag(self, tag):
        if self._capture == tag or (self._capture == "a" and tag == "a"):
            text = clean_text(" ".join(self._buffer))
            if tag == "title":
                self._title = text
            elif tag == "h1" and not self._h1:
                self._h1 = text
            elif tag == "p" and len(text) > 40:
                self.paragraphs.append(text)
            elif tag == "a" and self._href and len(text) > 12:
                self.anchors.append((self._href, text))
            elif tag == "script" and self._script_type == "ld+json":
                self._collect_json_ld(" ".join(self._buffer))
            self._capture = None
            self._buffer = []
            self._href = None
            self._script_type = ""

        if self._tag_stack:
            self._tag_stack.pop()

    def handle_data(self, data):
        if self._capture:
            self._buffer.append(data)

    def _collect_json_ld(self, raw: str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return
        for item in flatten_json_ld(data):
            if isinstance(item, dict):
                self.json_ld.append(item)

    def result(self) -> ParsedPage:
        description = (
            self.meta.get("og:description")
            or self.meta.get("description")
            or self.meta.get("twitter:description")
            or ""
        )
        date = (
            self.meta.get("article:published_time")
            or self.meta.get("published_time")
            or (self.times[0] if self.times else "")
        )
        title = self.meta.get("og:title") or self.meta.get("twitter:title") or self._title
        return ParsedPage(
            title=clean_title(title),
            h1=clean_title(self._h1),
            description=clean_text(description),
            date=date,
            anchors=self.anchors,
            paragraphs=self.paragraphs,
            json_ld=self.json_ld,
        )


def clean_text(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"\s+", " ", value)
    return value.strip(" \n\t\r—-")


def clean_title(value: str) -> str:
    value = clean_text(value)
    for sep in [" | ", " — ", " – "]:
        if sep in value and len(value.split(sep)[0]) > 12:
            value = value.split(sep)[0]
            break
    return value[:180]


def strip_html(value: str) -> str:
    return clean_text(re.sub(r"<[^>]+>", " ", value or ""))


def flatten_json_ld(data) -> Iterable[dict]:
    if isinstance(data, list):
        for item in data:
            yield from flatten_json_ld(item)
    elif isinstance(data, dict):
        if "@graph" in data:
            yield from flatten_json_ld(data["@graph"])
        else:
            yield data


def fetch(url: str) -> tuple[str, str]:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
            "Accept-Encoding": "identity",
        },
    )
    with urlopen(request, timeout=25) as response:
        body = response.read(MAX_BODY)
        charset = response.headers.get_content_charset() or "utf-8"
        return body.decode(charset, "replace"), response.geturl()


def parse_html_page(raw: str) -> ParsedPage:
    parser = PageParser()
    parser.feed(raw)
    return parser.result()


def parse_date(value: str, fallback: str | None = None) -> str:
    value = clean_text(value)
    if not value:
        return fallback or datetime.now(timezone.utc).date().isoformat()

    iso = re.search(r"20\d{2}-\d{2}-\d{2}", value)
    if iso:
        return iso.group(0)

    try:
        return parsedate_to_datetime(value).date().isoformat()
    except (TypeError, ValueError, IndexError):
        return fallback or datetime.now(timezone.utc).date().isoformat()


def detect_city(text: str, source: dict) -> str:
    if source["region"] == "world":
        return "World"
    for city in CITY_NAMES:
        if city.lower() in text.lower():
            return city
    return "Россия"


def source_urls(source: dict) -> list[str]:
    urls = [source["url"]]
    urls.extend(source.get("fallback_urls", []))
    return urls


def parse_feed(source: dict) -> list[dict]:
    if not source.get("feed_url"):
        return []
    try:
        raw, final_url = fetch(source["feed_url"])
    except (HTTPError, URLError, TimeoutError, OSError):
        return []

    try:
        root = ElementTree.fromstring(raw.strip())
    except ElementTree.ParseError:
        return []

    items: list[dict] = []
    for entry in root.findall(".//item") + root.findall("{http://www.w3.org/2005/Atom}entry"):
        title = text_of(entry, ["title", "{http://www.w3.org/2005/Atom}title"])
        link = text_of(entry, ["link"])
        if not link:
            link_el = entry.find("{http://www.w3.org/2005/Atom}link")
            link = link_el.attrib.get("href", "") if link_el is not None else ""
        description = strip_html(text_of(entry, ["description", "summary", "{http://www.w3.org/2005/Atom}summary"]))
        published = text_of(entry, ["pubDate", "published", "updated", "{http://www.w3.org/2005/Atom}published", "{http://www.w3.org/2005/Atom}updated"])
        if title and link:
            items.append(build_item(source, title, description, link, parse_date(published)))
        if len(items) >= source.get("limit", 6):
            break
    return items


def text_of(entry, names: list[str]) -> str:
    for name in names:
        found = entry.find(name)
        if found is not None and found.text:
            return clean_text(found.text)
    return ""


def parse_listing(source: dict) -> list[tuple[str, str]]:
    errors = []
    for url in source_urls(source):
        try:
            raw, final_url = fetch(url)
            page = parse_html_page(raw)
            links = select_candidate_links(page.anchors or [], final_url, source)
            if links:
                return links
        except (HTTPError, URLError, TimeoutError, OSError) as error:
            errors.append(f"{url}: {error}")
    if errors:
        print(f"[parser] {source['name']}: " + " | ".join(errors))
    return []


def select_candidate_links(anchors: list[tuple[str, str]], base_url: str, source: dict) -> list[tuple[str, str]]:
    base_host = urlparse(base_url).netloc.replace("www.", "")
    selected: list[tuple[str, str]] = []
    seen: set[str] = set()
    blocked_words = {"подписка", "реклама", "войти", "магазин", "архив", "privacy", "cookies"}

    for href, title in anchors:
        title = clean_title(title)
        if len(title) < 18 or title.lower() in blocked_words:
            continue
        url = urljoin(base_url, href)
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            continue
        if parsed.netloc.replace("www.", "") != base_host:
            continue
        normalized = parsed._replace(fragment="", query="").geturl()
        path = parsed.path.lower()
        if normalized in seen or normalized.rstrip("/") == source["url"].rstrip("/"):
            continue
        if source.get("include") and not any(pattern.lower() in path for pattern in source["include"]):
            continue
        seen.add(normalized)
        selected.append((normalized, title))
        if len(selected) >= source.get("limit", 6):
            break
    return selected


def parse_detail(source: dict, url: str, listing_title: str) -> dict | None:
    try:
        raw, final_url = fetch(url)
        page = parse_html_page(raw)
    except (HTTPError, URLError, TimeoutError, OSError):
        return build_item(source, listing_title, source["description"], url, "")

    json_item = pick_json_ld(page.json_ld or [])
    title = clean_title(json_item.get("headline") or json_item.get("name") or page.h1 or page.title or listing_title)
    description = clean_text(
        json_item.get("description")
        or page.description
        or ((page.paragraphs or [""])[0])
        or source["description"]
    )
    date = parse_date(json_item.get("datePublished") or json_item.get("dateModified") or page.date)
    item_url = json_item.get("url") or final_url or url
    return build_item(source, title, description, item_url, date, page_text=" ".join([title, description]))


def pick_json_ld(items: list[dict]) -> dict:
    preferred = {"Article", "NewsArticle", "BlogPosting", "Event", "CreativeWork"}
    for item in items:
        item_type = item.get("@type")
        types = item_type if isinstance(item_type, list) else [item_type]
        if any(t in preferred for t in types):
            return item
    return items[0] if items else {}


def build_item(source: dict, title: str, description: str, url: str, date: str, page_text: str = "") -> dict:
    date = parse_date(date)
    description = clean_text(description)
    if "{" in description and "}" in description:
        description = source["description"]
    text = " ".join([title, description, page_text])
    return {
        "id": stable_id(source["name"], url),
        "section": source["section"],
        "region": source["region"],
        "title": clean_title(title) or source["name"],
        "description": clean_text(description)[:320] or source["description"],
        "source": source["name"],
        "category": source["category"],
        "place": "Онлайн" if source["region"] == "world" else detect_city(text, source),
        "city": detect_city(text, source),
        "date": date,
        "endDate": date,
        "time": "Материал" if source["section"] != "calls" else "Заявки / условия на сайте",
        "url": url,
    }


def stable_id(source_name: str, url: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", f"{source_name}-{url}".lower())
    return slug.strip("-")[:160]


def parse_source(source: dict) -> list[dict]:
    print(f"[parser] parsing {source['name']}")
    feed_items = parse_feed(source)
    if feed_items:
        return feed_items

    items: list[dict] = []
    for url, title in parse_listing(source):
        item = parse_detail(source, url, title)
        if item:
            items.append(item)
        time.sleep(0.25)
    return items


def parse_all_sources() -> dict:
    items: list[dict] = []
    errors: list[dict] = []

    for source in SOURCES:
        try:
            items.extend(parse_source(source))
        except Exception as error:
            errors.append({"source": source["name"], "error": str(error)})

    unique = {}
    for item in items:
        unique[item["url"]] = item

    sorted_items = sorted(unique.values(), key=lambda item: item["date"], reverse=True)
    return {
        "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "items": sorted_items,
        "sources": SOURCES,
        "errors": errors,
    }


if __name__ == "__main__":
    parsed = parse_all_sources()
    print(json.dumps({"items": len(parsed["items"]), "errors": parsed["errors"]}, ensure_ascii=False, indent=2))
