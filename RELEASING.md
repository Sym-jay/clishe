# Releasing Clishe

1. Bump `version` in `pyproject.toml`, `CLISHE_VERSION` in `clishe.sh` and
   the `.TH` line of `clishe.1`. All three must match (`tests/test_data_files.py`
   checks): `clishe --version` reads `CLISHE_VERSION`, PyPI reads
   `pyproject.toml`, and `man clishe` shows the man page's.
2. Rename `## Unreleased` to `## X.Y.Z (date)` in the CHANGELOG.
3. Open a PR, and merge it when CI passes.
4. Run `gh release create vX.Y.Z --target main` with the changelog section as
   notes. `publish.yml` then uploads to PyPI (trusted publishing).
5. Check the upload finished (`gh run list --workflow publish.yml`) and the
   new version is on PyPI.
6. Update `packaging/aur` to the new tarball's sha256 in a follow-up PR.
   The "Arch package" workflow (`aur.yml`) builds and installs it on Arch
   for that PR; merge only when it passes.
7. Publish to the AUR (once the AUR repo is set up, see below):
   ```bash
   cd ~/aur-clishe
   curl -fsSLO https://raw.githubusercontent.com/Sym-jay/clishe/main/packaging/aur/PKGBUILD
   curl -fsSLO https://raw.githubusercontent.com/Sym-jay/clishe/main/packaging/aur/.SRCINFO
   git commit -am "Update to X.Y.Z" && git push origin master
   ```

### Setting up the AUR repo (once)

1. Register at https://aur.archlinux.org/register and add an SSH public key
   under My Account (`ssh-keygen -t ed25519 -f ~/.ssh/aur`).
2. Add to `~/.ssh/config`: `Host aur.archlinux.org`, `IdentityFile ~/.ssh/aur`, `User aur`.
3. `git clone ssh://aur@aur.archlinux.org/clishe.git ~/aur-clishe`, add
   `PKGBUILD` and `.SRCINFO` from `packaging/aur`, commit, `git push origin master`.

Issue labels for contributors: `good first issue`, `data only (no code)`,
`help wanted` and `testing`.
