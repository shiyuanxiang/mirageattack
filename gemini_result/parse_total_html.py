#!/usr/bin/env python3
"""
Parse total.html and extract the start message, individual steps, and the end message.

Usage:
    python parse_total_html.py /path/to/total.html
If no path is provided, the script defaults to ./total.html.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
from html.parser import HTMLParser
from typing import Any, Callable, Dict, List, Optional


class Node:
    """Minimal DOM-like node used for traversal."""

    def __init__(self, tag: str, attrs: Dict[str, str], text: Optional[str] = None):
        self.tag = tag
        self.attrs = attrs
        self.children: List["Node"] = []
        self.text = text

    def add_child(self, child: "Node") -> None:
        self.children.append(child)

    @property
    def class_list(self) -> List[str]:
        classes = self.attrs.get("class", "")
        return [c for c in classes.replace("\n", " ").split() if c]


class DOMBuilder(HTMLParser):
    """Build a lightweight DOM tree using the stdlib HTMLParser."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("document", {})
        self.stack: List[Node] = [self.root]

    def handle_starttag(self, tag: str, attrs: List[tuple[str, Optional[str]]]) -> None:
        node = Node(tag, {key: value or "" for key, value in attrs})
        self.stack[-1].add_child(node)
        self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: List[tuple[str, Optional[str]]]) -> None:
        node = Node(tag, {key: value or "" for key, value in attrs})
        self.stack[-1].add_child(node)

    def handle_endtag(self, tag: str) -> None:
        while len(self.stack) > 1:
            node = self.stack.pop()
            if node.tag == tag:
                break

    def handle_data(self, data: str) -> None:
        if not data:
            return
        text_node = Node("#text", {}, text=data)
        self.stack[-1].add_child(text_node)


def clean_text(value: str) -> str:
    """Collapse internal whitespace and trim the result."""
    return re.sub(r"\s+", " ", value.strip())


def walk(node: Node, predicate: Callable[[Node], bool]) -> List[Node]:
    matches: List[Node] = []

    def _walk(current: Node) -> None:
        for child in current.children:
            if predicate(child):
                matches.append(child)
            _walk(child)

    _walk(node)
    return matches


def find_first(node: Node, predicate: Callable[[Node], bool]) -> Optional[Node]:
    result = walk(node, predicate)
    return result[0] if result else None


def node_text(node: Node) -> str:
    pieces: List[str] = []

    def collect(current: Node) -> None:
        if current.tag == "#text":
            pieces.append(current.text or "")
        else:
            for child in current.children:
                collect(child)

    collect(node)
    def first_non_space(value: str) -> Optional[str]:
        for ch in value:
            if not ch.isspace():
                return ch
        return None

    def last_non_space(value: str) -> Optional[str]:
        for ch in reversed(value):
            if not ch.isspace():
                return ch
        return None

    def is_word_char(ch: str) -> bool:
        return ch.isalnum() or ch in {"_", "/"}

    combined_parts: List[str] = []
    for fragment in pieces:
        if not fragment:
            continue
        if combined_parts:
            prev = last_non_space(combined_parts[-1])
            nxt = first_non_space(fragment)
            if (
                prev
                and nxt
                and not combined_parts[-1].endswith((" ", "\n", "\t"))
                and not fragment.startswith((" ", "\n", "\t"))
                and is_word_char(prev)
                and is_word_char(nxt)
            ):
                combined_parts.append(" ")
        combined_parts.append(fragment)

    combined = "".join(combined_parts)
    return clean_text(combined) if combined else ""


def extract_start_message(root: Node) -> Optional[str]:
    required = {"break-words", "overflow-hidden", "p-6", "text-ellipsis", "max-w-full"}

    def predicate(n: Node) -> bool:
        return n.tag == "p" and required.issubset(set(n.class_list))

    node = find_first(root, predicate)
    return node_text(node) if node else None


def is_step_container(node: Node) -> bool:
    return node.tag == "div" and {"p-6", "border", "font-ppsupply", "space-y-3", "transition-colors"}.issubset(
        set(node.class_list)
    )


def find_step_title(node: Node) -> Optional[str]:
    def predicate(n: Node) -> bool:
        return n.tag == "span" and {"py-1", "font-medium", "text-sm"}.issubset(set(n.class_list))

    span = find_first(node, predicate)
    return node_text(span) if span else None


def find_step_content(node: Node) -> str:
    def predicate(n: Node) -> bool:
        classes = set(n.class_list)
        return n.tag == "div" and {"text-sm", "leading-relaxed"}.issubset(classes)

    content_node = find_first(node, predicate)
    return node_text(content_node) if content_node else ""


def extract_steps(root: Node) -> List[Dict[str, Any]]:
    step_nodes = walk(root, is_step_container)
    steps: List[Dict[str, Any]] = []
    for idx, node in enumerate(step_nodes, start=1):
        steps.append(
            {
                "number": idx,
                "title": find_step_title(node) or f"Step {idx}",
                "content": find_step_content(node),
            }
        )
    return steps


def extract_end_message(root: Node) -> Optional[str]:
    def predicate(n: Node) -> bool:
        return n.tag == "div" and {"font-ppsupply", "sticky", "bottom-0", "z-10", "w-full"}.issubset(
            set(n.class_list)
        )

    target_div = None
    for match in walk(root, predicate):
        target_div = match
    if not target_div:
        return None

    def inner_predicate(n: Node) -> bool:
        return n.tag == "div" and {"break-words", "p-6", "text-ellipsis"}.issubset(set(n.class_list))

    content_container = find_first(target_div, inner_predicate)
    if not content_container:
        return None

    paragraphs = [node_text(child) for child in content_container.children if child.tag == "p"]
    paragraphs = [text for text in paragraphs if text]
    return " ".join(paragraphs) if paragraphs else None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract structured data from total.html")
    parser.add_argument(
        "--html",
        dest="html_path",
        default="total.html",
        help="Path to the HTML file (defaults to ./total.html)",
    )
    return parser.parse_args()


def build_dom(html_text: str) -> Node:
    parser = DOMBuilder()
    parser.feed(html_text)
    parser.close()
    return parser.root


def main() -> None:
    args = parse_args()
    html_file = pathlib.Path(args.html_path)
    if not html_file.exists():
        raise SystemExit(f"File not found: {html_file}")

    root = build_dom(html_file.read_text(encoding="utf-8"))

    data = {
        "start_msg": extract_start_message(root),
        "steps": extract_steps(root),
        "end_msg": extract_end_message(root),
    }

    output_name = (
        html_file.with_name(f"{html_file.stem}")
    )
    output_name.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote parsed steps to {output_name}")


if __name__ == "__main__":
    main()
