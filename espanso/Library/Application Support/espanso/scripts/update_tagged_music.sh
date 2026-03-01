#!/bin/bash
# Update tagged music symlinks in ~/Music/favorites

MUSIC_DIR=~/Music
FAVORITES_DIR="$MUSIC_DIR/favorites"

# Create favorites dir if doesn't exist
mkdir -p "$FAVORITES_DIR"

# Remove old symlinks
rm -f "$FAVORITES_DIR"/*

# Find all tagged files and create symlinks
mdfind -onlyin "$MUSIC_DIR" 'kMDItemUserTags == "*"' | while read file; do
  filename=$(basename "$file")
  ln -s "$file" "$FAVORITES_DIR/$filename"
done

echo "Tagged music symlinks updated"
