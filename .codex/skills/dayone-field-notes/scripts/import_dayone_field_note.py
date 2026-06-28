#!/usr/bin/env python3
"""Import a Day One export ZIP into a Leonard Field Notes Jekyll post."""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
FRONT_MATTER_ORDER = [
    "layout",
    "title",
    "summary",
    "category_label",
    "banner_image",
    "banner_position",
]


@dataclass
class PhotoAsset:
    identifier: str
    source: Path
    target: Path
    site_path: str
    width: int
    height: int
    order: int


class ImportErrorWithHelp(RuntimeError):
    pass


def slugify(value: str) -> str:
    value = value.lower().replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "field-note"


def post_slug(path: Path) -> str:
    return re.sub(r"^\d{4}-\d{2}-\d{2}-", "", path.stem)


def target_slug_from_url(url: str) -> str:
    path = urlparse(url).path if "://" in url else url
    parts = [part for part in path.split("/") if part]
    if not parts:
        raise ImportErrorWithHelp(f"Could not determine a post slug from URL/path: {url}")
    return parts[-1]


def split_front_matter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    raw = text[4:end]
    body = text[end + 5 :]
    data: dict[str, str] = {}
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"')
    return data, body


def dump_front_matter(data: dict[str, str]) -> str:
    keys = [key for key in FRONT_MATTER_ORDER if key in data]
    keys.extend(sorted(key for key in data if key not in keys))
    lines = ["---"]
    for key in keys:
        value = data[key]
        if value == "":
            continue
        lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def unescape_dayone_markdown(text: str) -> str:
    return re.sub(r"\\([\\`*_{}\[\]()#+\-.!])", r"\1", text)


def entry_title(entry: dict[str, Any]) -> str:
    text = entry.get("text") or ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return unescape_dayone_markdown(stripped[2:].strip())
    rich = entry.get("richText")
    if rich:
        try:
            data = json.loads(rich)
            for item in data.get("contents", []):
                attrs = item.get("attributes", {})
                line_attrs = attrs.get("line", {})
                if line_attrs.get("header") == 1 and item.get("text"):
                    return item["text"].strip()
        except json.JSONDecodeError:
            pass
    return "Untitled Field Note"


def creation_date(entry: dict[str, Any]) -> str:
    value = entry.get("creationDate") or datetime.now(timezone.utc).isoformat()
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt.date().isoformat()


def load_export(zip_path: Path) -> tuple[list[dict[str, Any]], Path, tempfile.TemporaryDirectory[str]]:
    tmp = tempfile.TemporaryDirectory()
    tmp_path = Path(tmp.name)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(tmp_path)
    journal = tmp_path / "Journal.json"
    if not journal.exists():
        raise ImportErrorWithHelp("Expected Journal.json at the root of the Day One export.")
    data = json.loads(journal.read_text(encoding="utf-8"))
    entries = data.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ImportErrorWithHelp("Journal.json did not contain any entries.")
    return entries, tmp_path, tmp


def select_entry(entries: list[dict[str, Any]], title: str | None, uuid: str | None) -> dict[str, Any]:
    if uuid:
        matches = [entry for entry in entries if entry.get("uuid") == uuid]
        if not matches:
            raise ImportErrorWithHelp(f"No Day One entry matched uuid {uuid}.")
        return matches[0]
    if title:
        wanted = slugify(title)
        matches = [entry for entry in entries if slugify(entry_title(entry)) == wanted]
        if not matches:
            available = ", ".join(entry_title(entry) for entry in entries)
            raise ImportErrorWithHelp(f"No Day One entry matched title {title!r}. Available: {available}")
        return matches[0]
    if len(entries) > 1:
        available = "\n".join(f"- {entry.get('uuid')}: {entry_title(entry)}" for entry in entries)
        raise ImportErrorWithHelp("Export contains multiple entries. Select one with --entry-title or --entry-uuid.\n" + available)
    return entries[0]


def find_post(repo: Path, target_url: str | None, title: str) -> Path | None:
    posts = sorted((repo / "_posts").glob("*.md"))
    if target_url:
        wanted_slug = target_slug_from_url(target_url)
        matches = [path for path in posts if post_slug(path) == wanted_slug]
        if not matches:
            raise ImportErrorWithHelp(f"No post matched target URL slug {wanted_slug!r}.")
        return matches[0]
    wanted_slug = slugify(title)
    scored: list[tuple[float, Path]] = []
    for path in posts:
        front, _ = split_front_matter(path.read_text(encoding="utf-8"))
        candidate_title = front.get("title", post_slug(path))
        score = max(
            SequenceMatcher(None, wanted_slug, post_slug(path)).ratio(),
            SequenceMatcher(None, slugify(title), slugify(candidate_title)).ratio(),
        )
        scored.append((score, path))
    if not scored:
        return None
    score, path = max(scored, key=lambda item: item[0])
    return path if score >= 0.55 else None


def mismatch_score(entry_title_value: str, post_path: Path) -> float:
    front, _ = split_front_matter(post_path.read_text(encoding="utf-8"))
    existing_title = front.get("title", post_slug(post_path))
    return max(
        SequenceMatcher(None, slugify(entry_title_value), post_slug(post_path)).ratio(),
        SequenceMatcher(None, slugify(entry_title_value), slugify(existing_title)).ratio(),
    )


def image_dimensions(path: Path, metadata: dict[str, Any]) -> tuple[int, int]:
    width = int(metadata.get("width") or 0)
    height = int(metadata.get("height") or 0)
    if width and height:
        return width, height
    try:
        from PIL import Image

        with Image.open(path) as img:
            return img.size
    except Exception:
        return 0, 0


def optimize_copy_image(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image

        with Image.open(source) as img:
            ext = target.suffix.lower()
            if ext in {".jpg", ".jpeg"}:
                img.convert("RGB").save(target, quality=88, optimize=True)
            elif ext == ".png":
                img.save(target, optimize=True)
            else:
                shutil.copy2(source, target)
    except Exception:
        shutil.copy2(source, target)


def prepare_photos(entry: dict[str, Any], extracted_root: Path, repo: Path, slug: str, apply: bool) -> list[PhotoAsset]:
    assets: list[PhotoAsset] = []
    photos = sorted(entry.get("photos") or [], key=lambda item: item.get("orderInEntry", 0))
    for index, photo in enumerate(photos, start=1):
        ext = str(photo.get("type") or "jpg").lower()
        if ext == "jpeg":
            ext = "jpg"
        if ext not in IMAGE_EXTENSIONS:
            continue
        md5 = photo.get("md5")
        source = extracted_root / "photos" / f"{md5}.{ext}"
        if not source.exists() and ext == "jpg":
            source = extracted_root / "photos" / f"{md5}.jpeg"
        if not source.exists():
            raise ImportErrorWithHelp(f"Missing exported photo for identifier {photo.get('identifier')} at {source}.")
        target_name = f"{slug}-{index}.{ext}"
        target = repo / "assets" / "images" / target_name
        width, height = image_dimensions(source, photo)
        asset = PhotoAsset(
            identifier=str(photo.get("identifier") or md5 or index),
            source=source,
            target=target,
            site_path=f"/assets/images/{target_name}",
            width=width,
            height=height,
            order=int(photo.get("orderInEntry") or 0),
        )
        if apply:
            optimize_copy_image(source, target)
        assets.append(asset)
    return assets


def markdown_image(asset: PhotoAsset, title: str) -> str:
    alt = title if title.lower().startswith("leonard") else f"Leonard - {title}"
    return f"![{alt}]({{{{ '{asset.site_path}' | relative_url }}}})"


def entry_body_markdown(entry: dict[str, Any], photos: list[PhotoAsset], title: str) -> str:
    text = unescape_dayone_markdown(entry.get("text") or "")
    lines = text.splitlines()
    if lines and lines[0].strip().startswith("# "):
        lines = lines[1:]
        while lines and not lines[0].strip():
            lines = lines[1:]
    text = "\n".join(lines).strip()
    by_identifier = {asset.identifier: asset for asset in photos}

    def replace_photo(match: re.Match[str]) -> str:
        identifier = match.group(1)
        asset = by_identifier.get(identifier)
        if not asset:
            return match.group(0)
        return markdown_image(asset, title)

    text = re.sub(r"!\[\]\(dayone-moment://([A-Za-z0-9]+)\)", replace_photo, text)
    return text.rstrip() + "\n"


def first_paragraph_summary(body: str) -> str:
    for block in re.split(r"\n\s*\n", body):
        cleaned = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", block).strip()
        if cleaned:
            cleaned = re.sub(r"\s+", " ", cleaned)
            return cleaned[:157].rstrip() + ("..." if len(cleaned) > 157 else "")
    return "Leonard shares a new field note."


def choose_banner(photos: list[PhotoAsset], front: dict[str, str], mode: str) -> str | None:
    if mode == "keep":
        return front.get("banner_image")
    if mode == "never":
        return None
    if not photos:
        return front.get("banner_image") if mode == "auto" else None
    candidates = sorted(
        photos,
        key=lambda asset: ((asset.width / asset.height) if asset.height else 0, asset.width * asset.height),
        reverse=True,
    )
    if mode == "always":
        return candidates[0].site_path
    for asset in candidates:
        if asset.height and asset.width / asset.height >= 1.25:
            return asset.site_path
    return front.get("banner_image")


def render_post(front: dict[str, str], body: str) -> str:
    return dump_front_matter(front) + body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export_zip", type=Path)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--target-url")
    parser.add_argument("--entry-title")
    parser.add_argument("--entry-uuid")
    parser.add_argument("--banner", choices=["auto", "always", "never", "keep"], default="auto")
    parser.add_argument("--allow-title-mismatch", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    repo = args.repo.resolve()
    if not (repo / "_posts").is_dir() or not (repo / "assets" / "images").is_dir():
        raise ImportErrorWithHelp(f"{repo} does not look like the Leonard Jekyll repo.")

    entries, extracted_root, tmp = load_export(args.export_zip.resolve())
    try:
        entry = select_entry(entries, args.entry_title, args.entry_uuid)
        title = entry_title(entry)
        post_path = find_post(repo, args.target_url, title)
        if post_path and args.target_url:
            score = mismatch_score(title, post_path)
            if score < 0.55 and not args.allow_title_mismatch:
                raise ImportErrorWithHelp(
                    "The Day One entry appears to target a different Field Note.\n"
                    f"Entry title: {title}\n"
                    f"Target post: {post_path.name}\n"
                    f"Similarity score: {score:.2f}\n"
                    "Rerun with the correct export/target, or add --allow-title-mismatch only after user confirmation."
                )
        if post_path:
            front, _old_body = split_front_matter(post_path.read_text(encoding="utf-8"))
            slug = post_slug(post_path)
        else:
            slug = slugify(title)
            post_path = repo / "_posts" / f"{creation_date(entry)}-{slug}.md"
            front = {
                "layout": "post",
                "title": title,
                "category_label": "Field Note",
            }
        front.setdefault("layout", "post")
        front.setdefault("title", title)
        front.setdefault("category_label", "Field Note")

        photos = prepare_photos(entry, extracted_root, repo, slug, args.apply)
        body = entry_body_markdown(entry, photos, front.get("title", title))
        front["summary"] = front.get("summary") or first_paragraph_summary(body)
        banner = choose_banner(photos, front, args.banner)
        if banner:
            front["banner_image"] = banner
            front.setdefault("banner_position", "center center")
        else:
            front.pop("banner_image", None)
            front.pop("banner_position", None)

        output = render_post(front, body)
        print("Day One Field Note import")
        print(f"Mode: {'apply' if args.apply else 'dry-run'}")
        print(f"Entry title: {title}")
        print(f"Target post: {post_path.relative_to(repo)}")
        print(f"Photos: {len(photos)}")
        for asset in photos:
            print(f"- {asset.source.name} -> {asset.target.relative_to(repo)} ({asset.width}x{asset.height})")
        print(f"Banner: {front.get('banner_image', '(none)')}")
        if args.apply:
            post_path.write_text(output, encoding="utf-8")
            print("Wrote post.")
        else:
            print("No files written. Rerun with --apply to update the post and copy photos.")
        return 0
    finally:
        tmp.cleanup()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ImportErrorWithHelp as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
