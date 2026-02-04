# Cursor IDE Configuration

This directory contains Cursor IDE-specific settings.

## Files

- `settings.json` - Cursor workspace settings that exclude parent directories from the file explorer

## Note

If you see parent directories (`../`, `../../`, etc.) in Cursor's changes tab, this is a Cursor IDE display issue, not a git tracking issue. Git is correctly configured to only track files within this repository (`/Users/albert.wong/code/github/albertcwong/tableau-ai-demo`).

The `settings.json` file attempts to hide parent directories from Cursor's file explorer, but Cursor may still show them in the Source Control/Changes tab if it's scanning parent directories.
