# Changelog

All notable changes to this skill will be documented in this file.

## [0.2.0] - 2026-05-25

### Added
- Five-mode architecture: 审查 / 浏览 / 搜索 / 对比 / 学习
- Formula browsing by 21-chapter TCM classification
- Multi-dimensional formula search (by name, indication, herb, function)
- Side-by-side formula comparison mode
- Formula song (verse) display and explanation
- Derivative chain tracing (base formula → derivatives)
- Herb pair (药对) analysis with compatibility mechanism
- Ch1 解表剂 7 missing variants: 桂枝加桂汤, 桂枝加芍药汤, 大羌活汤, 加味香苏散, 射干麻黄汤, 小青龙加石膏汤, 金沸草散
- REFERENCE.md with detailed seven-dimension audit rules, toxicity tables, field specs
- Standard YAML frontmatter for Agent Skills compliance
- README.md for GitHub project page

### Changed
- Repositioned from audit-only tool to audit + browse + search + learn platform
- Expanded trigger conditions from 7 to ~25 (covering all five modes)
- Streamlined SKILL.md body (detailed rules moved to REFERENCE.md)
- Updated data reference paths to `data/` subdirectory
- Unified file structure for GitHub publishing

### Fixed
- Removed duplicate version entries in version table

## [0.1.1] - 2026-05-23

### Added
- Simplified chart format for formula architecture diagrams
- Medical-pharmacological analysis section
- Modern pharmacology fields in herbs.json

## [0.1.0] - 2026-05-23

### Added
- Initial release with 16 core herbs + 36 classic formulas + contraindication matrix
- Seven-dimension prescription audit framework
- OCR/text input processing
- Multi-language support (Chinese default, English switchable)
- Safety boundaries and disclaimer
