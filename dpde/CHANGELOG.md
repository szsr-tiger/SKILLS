# Changelog

All notable changes to this skill will be documented in this file.

## [1.2.0] - 2026-06-10

### Changed
- Merged main report + appendix into single output file
- Unified template into `templates/report.md`

### Fixed
- User confirmation point timeout handling (default continue if no response)
- Template loading instruction (must Read before generating)
- Quick reference table self-check items (added missing L2/L3 checks)
- Safety redline refusal response templates (separate for legal vs psychological)
- 5WHY root cause actionability guidance (back up one layer if too abstract)

## [1.1.0] - 2026-06-09

### Added
- Entry guard: safety redline (illegal/unethical/self-harm refusal)
- User confirmation point after Layer 2 (problem tree review)
- Constraint dimension (7th decomposition dimension)
- Forward validation in Layer 4 (MEQS vs Layer 1 contradictions & consistency)
- Cross-layer explicit linkage in Layer 5
- "Not a problem" exit path in Layer 1 (when assumption is false)
- Mandatory disclaimer in output template
- Custom dimension escape hatch

### Fixed
- Iron Rule vs MEQS<3 logical contradiction
- Hardcoded "5 dimensions" → dynamic dimension count
- Missing output compilation instruction (analysis process vs deliverable)
- Self-check criterion softened ("adds depth" instead of "must be different")
- Version number consistency

### Changed
- Output templates extracted to `templates/` for leaner SKILL.md (479→330 lines)
- 6 decomposition dimensions → 7 (added constraint dimension)
- Depth calibration: "analysis depth proportional to problem complexity"

## [1.0.0] - 2026-06-09

### Added
- Initial release
- Five-layer engine: Audit → Decompose → Evaluate → Select → Synthesize
- SCQA, 5WHY, contradiction detection, first principles stripping
- IV×LE 2×2 strategy matrix (replaces linear scoring)
- Minimum Effective Question Set (MEQS) + coverage verification
- Positive/negative effects chain + second-order scanning + pre-mortem
- Main report + appendix dual-output with templates
- Quick reference table with self-check & backtracking
- 10 special case handling entries
