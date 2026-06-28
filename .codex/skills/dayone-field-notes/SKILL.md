---
name: dayone-field-notes
description: Import Day One journal export ZIP files into the Leonard Jekyll site's Field Notes posts. Use when the user provides a Day One export, asks to add, replace, or update a Leonard Field Note from Day One, wants Day One photos copied into the website, or wants Codex to decide whether a Field Note should use a banner image.
---

# Day One Field Notes

## Overview

Use this skill to turn a Day One export ZIP into a Leonard Field Notes post in the Jekyll site. The skill keeps Day One as the writing source while producing repo-native Markdown, copied image assets, and front matter that matches the existing Leonard site.

## Workflow

1. Inspect the export before editing:
   - Run `python3 .codex/skills/dayone-field-notes/scripts/import_dayone_field_note.py <export.zip> --repo .`.
   - If the user gives a page URL, add `--target-url <url>`.
   - Treat title or target mismatches as blockers unless the user explicitly confirms the mismatch is intentional.
2. Review the dry-run output:
   - Confirm the Day One entry title, target post, photos found, copied asset names, and banner decision.
   - If multiple entries are present, rerun with `--entry-title`, `--entry-uuid`, or a target URL that selects one entry.
3. Apply the update:
   - Rerun the same command with `--apply` only after the dry-run points to the intended Field Note.
   - Use `--allow-title-mismatch` only when the user confirms the Day One title intentionally differs from the website post.
4. Verify the site:
   - Run `script/test-and-preview --check-only`.
   - For visual changes, preview the updated post and confirm all images load.
5. Commit and deploy using the repo's normal GitHub Pages workflow when requested.

## Import Behavior

The importer preserves existing post front matter when updating an existing post. It replaces the Markdown body with the Day One entry body, converts `dayone-moment://...` photo placeholders into website image links, and copies exported photos into `assets/images/`.

Banner decisions are intentionally conservative:

- Use a Day One photo as `banner_image` only when it is landscape/wide enough for a banner, or when `--banner always` is provided.
- Keep an existing banner when no Day One photo is a good banner candidate.
- Do not use square or portrait sticker-style images as banners by default.
- Use `--banner never` to remove a banner from the target post.

The importer fails instead of overwriting when a provided `--target-url` appears unrelated to the Day One entry title. This prevents accidentally replacing one Field Note with another journal entry.

## Script

Primary tool:

```bash
python3 .codex/skills/dayone-field-notes/scripts/import_dayone_field_note.py EXPORT.zip --repo . [--target-url URL] [--apply]
```

Useful options:

- `--target-url https://fryventures.com/updates/example/` selects a specific post by URL slug.
- `--entry-title "Packing for the road"` selects one entry from a multi-entry export.
- `--entry-uuid UUID` selects an exact Day One entry.
- `--banner auto|always|never|keep` controls banner behavior; default is `auto`.
- `--allow-title-mismatch` permits updating a target URL even when the Day One entry title differs.
- `--apply` writes files; without it, the script only reports what would happen.

## Site Conventions

- Field Note posts live in `_posts/` and use `layout: post` plus `category_label: Field Note`.
- Public URLs are `/updates/:title/`, where `:title` is the post filename slug after the date.
- Images live in `assets/images/` and should be referenced with Liquid `relative_url`, for example:
  `![Alt text]({{ '/assets/images/example.jpg' | relative_url }})`
- Keep repo validation aligned with Pages by running `script/test-and-preview --check-only` before calling the work complete.
