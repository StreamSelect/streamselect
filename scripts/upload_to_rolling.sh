#!/usr/bin/env bash
# Attach one build artifact to its release, replacing the old copy.
#
#   scripts/upload_to_rolling.sh <asset-file>
#
# release.yml creates and moves the release itself (tag, title, notes); the
# Windows and Flatpak jobs only add their own asset under a stable name. They
# can finish first, so this waits up to ten minutes for the release to exist.
# Needs GITHUB_TOKEN and GITHUB_REPOSITORY (both set in Actions).
set -euo pipefail
asset="${1:?usage: upload_to_rolling.sh <asset-file>}"

# A version tag's build goes on that tag's release. Its macOS job runs the whole
# test suite first, so this creates the release rather than waiting for it; the
# macOS job then adds its .dmg to the same release.
if [ "${GITHUB_REF_TYPE:-}" = "tag" ]; then
  tag="$GITHUB_REF_NAME"
  gh release view "$tag" --repo "$GITHUB_REPOSITORY" >/dev/null 2>&1 \
    || gh release create "$tag" --repo "$GITHUB_REPOSITORY" --verify-tag \
         --title "StreamSelect $tag" --generate-notes \
    || gh release view "$tag" --repo "$GITHUB_REPOSITORY" >/dev/null
  gh release upload "$tag" "$asset" --clobber --repo "$GITHUB_REPOSITORY"
  exit 0
fi

for _ in $(seq 1 30); do
  gh release view rolling --repo "$GITHUB_REPOSITORY" >/dev/null 2>&1 && break
  echo "rolling release not there yet — waiting for release.yml"; sleep 20
done
gh release upload rolling "$asset" --clobber --repo "$GITHUB_REPOSITORY"
