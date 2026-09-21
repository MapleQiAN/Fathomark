# M3 Company IR Provider Implementation Plan

**Goal:** Add a replaceable company investor-relations evidence adapter without
guessing dates or creating an SSRF surface.

- [x] Add failing tests for typed IR metadata, traceable evidence, empty
  manifests, and unallowlisted URLs.
- [x] Implement HTTPS host and redirect allowlisting, HTML text extraction,
  content hashing, and explicit provider errors.
- [x] Export the provider and document the operator-owned manifest boundary.

Validation: provider tests pass; live company IR calls and source-specific
licensing remain operator-controlled and unverified.
