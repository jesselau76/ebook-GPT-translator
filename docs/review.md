# Review Notes

This repository was rebuilt as a v2 package because the original project could not be cloned in the current environment. The review below is based on the public repository page, DeepWiki index, and visible issue history.

## Observed v1 characteristics

- Single-script architecture centered on `text_translation.py`
- Legacy OpenAI usage pattern tied to the pre-client SDK style
- Mixed responsibilities in one file: CLI parsing, provider calls, chunking, file I/O, and output generation
- Format support existed, but extensibility and testing surface were limited
- Configuration depended on a legacy `settings.cfg` layout

## Issues and historical requests reflected in the upgrade

- Modern OpenAI SDK migration
- Azure OpenAI support
- OpenAI-compatible base URL support for third-party providers such as Venice.ai
- Skip/resume behavior for long-running jobs
- Better chunk and token controls
- Glossary support and case-sensitive replacement
- Maintainable README and release-ready packaging

## Refactor strategy

- Replace the monolith with a package under `src/ebook_gpt_translator`
- Keep the old `text_translation.py` entrypoint as a compatibility wrapper
- Add provider abstraction, cache-backed resume, and testable document pipeline
- Preserve legacy config compatibility while introducing `settings.toml`
- Add a mock provider so the tool can be verified offline

