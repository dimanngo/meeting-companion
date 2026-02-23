# Public Portfolio Readiness Plan

Repository is technically strong in the app subfolder, but not yet presentation-ready as a public portfolio. The main blockers are public-facing hygiene (license file, root landing docs, personal-path artifacts), trust signals (CI + release docs), and document consistency. This plan prioritizes launch-critical fixes first, then quality/community scaffolding, then portfolio polish.

## [√] 1. Establish public repository baseline

- Add a root landing README that points to the runnable app in [meeting-tui/README.md](meeting-tui/README.md).
- Add a LICENSE file to match declared MIT metadata in [meeting-tui/pyproject.toml](meeting-tui/pyproject.toml#L7) and statement in [meeting-tui/README.md](meeting-tui/README.md#L481-L483).
- Keep subproject README as implementation detail, root README as portfolio entry.

## [√] 2. Remove privacy/professionalism risks

- Remove machine-specific absolute paths in [meeting-tui/QUICK_START.md](meeting-tui/QUICK_START.md#L6-L7) and [meeting-tui/QUICK_START.md](meeting-tui/QUICK_START.md#L49).
- Ensure generated runtime artifacts are not tracked (example present: [meeting-tui/meeting-tui.log](meeting-tui/meeting-tui.log#L1)).
- Reconfirm secret handling remains template-only via [meeting-tui/.env.example](meeting-tui/.env.example) and ignore rules in [.gitignore](.gitignore#L153-L155).

## [√] 3. Resolve stale/contradictory documentation

- Reconcile Gemini model naming mismatch: [meeting-tui/README.md](meeting-tui/README.md#L318) vs [meeting-tui/src/meeting_tui/config.py](meeting-tui/src/meeting_tui/config.py#L55).
- Reconcile model-size count mismatch in [meeting-tui/README.md](meeting-tui/README.md#L86) and [meeting-tui/README.md](meeting-tui/README.md#L401).
- Reconcile review/test status mismatch: [Implementation.md](Implementation.md#L139) vs [meeting-tui/_review/REVIEW_REPORT_2.md](meeting-tui/_review/REVIEW_REPORT_2.md#L19).
- Archive or clearly mark old planning docs as historical (for example [Option1-TUI.md](Option1-TUI.md#L108-L142), [Option2-NativeMacOS.md](Option2-NativeMacOS.md#L131-L212)).

## [√] 4. Add trust signals for public viewers

- Add CI workflow for tests described in [meeting-tui/README.md](meeting-tui/README.md#L432-L477).
- Add badges (CI status at minimum) to root README and app README.
- Add explicit “works on macOS/Linux” matrix notes aligned with current runtime docs.

## 5. Add community and governance scaffolding

- Add CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, and minimal issue/PR templates.
- Add support/bug-report expectations and response policy.
- Keep contribution scope small and explicit for a portfolio project.

## 6. Add release hygiene

- Add CHANGELOG and versioning policy that matches [meeting-tui/pyproject.toml](meeting-tui/pyproject.toml#L3) and [meeting-tui/src/meeting_tui/__init__.py](meeting-tui/src/meeting_tui/__init__.py#L3).
- Document release/tag process (what triggers version bumps, what gets documented).
- Clarify dependency/lockfile policy around [meeting-tui/uv.lock](meeting-tui/uv.lock#L1-L4).

## 7. Improve portfolio presentation

- Add one short demo GIF/screenshot and an architecture image (currently mostly text/ASCII).
- Add a concise “Problem → Approach → Trade-offs → Outcomes” section near top-level README.
- Add a short roadmap with 3–5 concrete future items from [meeting-tui/_review/impl-plan.md](meeting-tui/_review/impl-plan.md).

## Verification

Public-readiness checklist passes when:

- A new visitor can understand project value in under 60 seconds from root README.
- Fresh clone can run setup/start/test exactly as documented.
- No personal paths, local artifacts, or secret-like values remain in tracked files.
- CI passes on default branch and badge is visible.
- License and community files are present and linked.

## Decisions

- Prioritize repo-level presentation and hygiene before deeper engineering polish.
- Keep internal/review docs, but relabel as historical and move out of the primary onboarding path.
- Treat documentation consistency as a launch blocker, not a post-launch cleanup.
