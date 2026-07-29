# v3 Step 5 — [SHOULD] Digital signature of the archived PDF

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** the owner of a finalized review can digitally sign the archived PDF
inside maluS: upload a personal P12 certificate once, then sign with a
passphrase prompt — producing a visible PAdES B-B signature stored as the
`pdf_signed` artifact.

**Architecture:** optional extra `malus[sign]` (pyHanko, MIT — ADR 0004 already
covers the extras mechanism). Feature flag `MALUS_SIGNING=1` (env, default off).
The passphrase is used in-request and never persisted or logged (spec §Digital
signature). The org CA is documentation only. This step is a SHOULD: it may be
dropped from the release without touching steps 01–04.

**Tech stack:** pyHanko ≥0.36, FastAPI, pytest (`importorskip("pyhanko")`).
Depends on step 04 (stored PDF artifact).

## Global constraints

- Signing must be the **last** operation on the PDF: sign the stored `"pdf"`
  artifact bytes via pyHanko (incremental update is its default), store the
  result as `"pdf_signed"`, never regenerate the base PDF afterwards.
- Passphrase: request-scoped only. Assert in tests it appears in no DB column
  and no audit `detail_json`.
- Human owner only (`forbid_ai_commit`; admins may NOT sign on behalf — a
  signature is personal).
- Suite green + Conventional Commit per task; everything degrades cleanly when
  the extra or the flag is absent.

## Deliverables

- [ ] `pyproject` extra `sign`; feature flag `MALUS_SIGNING`
- [ ] `UserSigningCert` table + upload/delete UI in the account page
- [ ] `signing.py`: sign stored PDF with P12 + passphrase (visible signature on the sign-off page)
- [ ] Web: Sign action on finalized reviews; `pdf_signed` download
- [ ] CA how-to doc
- [ ] Full suite green (with and without the extra)

---

### Task 1: extra, flag, cert storage

**Files:**
- Modify: `pyproject.toml`, `src/malus/db/models.py`, `src/malus/repo/repositories.py`
- Test: `tests/db/test_signing_cert.py` (new)

**Interfaces produced:**

```toml
sign = ["pyhanko>=0.36"]  # ADR 0004: PAdES signing of the finalize PDF
```

```python
class UserSigningCert(SQLModel, table=True):    # one per user, replaced on re-upload
    __tablename__ = "user_signing_certs"
    id: Optional[int]; user_id: int             # FK users.id, unique
    p12_blob: bytes                             # the uploaded PKCS#12, stored as-is
    label: Optional[str]                        # e.g. certificate CN, for display
    created: dt.datetime

class SigningCertRepo:
    def set_for(self, user, p12_blob: bytes, label: str | None) -> UserSigningCert  # upsert
    def get_for(self, user) -> Optional[UserSigningCert]
    def delete_for(self, user) -> None

def signing_enabled() -> bool                   # src/malus/signing.py: env MALUS_SIGNING == "1"
                                                #   AND pyhanko importable
```

- [ ] **Step 1: failing test:** upsert then get returns the blob; second upsert
  replaces (one row); delete removes.
- [ ] **Step 2:** run → FAIL. **Step 3:** implement (LargeBinary column like
  `ReviewArtifact.content`; `create_all` adds the table).
- [ ] **Step 4:** run → PASS. **Step 5:** `git commit -m "feat(db): per-user P12 signing certificate storage"`

### Task 2: the signing module

**Files:**
- Create: `src/malus/signing.py`
- Test: `tests/test_signing.py` (new)

**Interfaces produced:**

```python
SIGNING_AVAILABLE: bool          # pyhanko importable
def signing_enabled() -> bool    # SIGNING_AVAILABLE and os.environ MALUS_SIGNING == "1"
class SigningError(RuntimeError): ...
def sign_pdf(pdf_bytes: bytes, p12_blob: bytes, passphrase: str, *,
             reason: str, signer_name: str) -> bytes
```

- [ ] **Step 1: failing tests** (module-level `pytest.importorskip("pyhanko")`;
  generate a throwaway self-signed P12 in a fixture with the `cryptography`
  package — pyHanko depends on it, so it is present whenever pyhanko is):

```python
def test_sign_produces_incremental_signature(sample_pdf_bytes, throwaway_p12):
    out = sign_pdf(sample_pdf_bytes, throwaway_p12, "pw",
                   reason="maluS review sign-off", signer_name="Own Er")
    assert len(out) > len(sample_pdf_bytes)          # incremental update appends
    assert b"/ByteRange" in out                      # a signature dictionary exists


def test_wrong_passphrase_raises(sample_pdf_bytes, throwaway_p12):
    with pytest.raises(SigningError):
        sign_pdf(sample_pdf_bytes, throwaway_p12, "wrong", reason="r", signer_name="s")
```

  (`sample_pdf_bytes`: if the `pdf` extra is installed reuse `pdfgen`; otherwise
  embed a minimal static one-page PDF in `tests/fixtures/minimal.pdf`. The
  `throwaway_p12` fixture builds a self-signed cert + key with `cryptography`
  and serializes with `pkcs12.serialize_key_and_certificates`, passphrase `b"pw"`.)
- [ ] **Step 2:** run → FAIL. **Step 3: implement** `src/malus/signing.py`:

```python
"""PAdES B-B signing of the finalize PDF (v3, optional `malus[sign]` extra).

The passphrase lives only in the request that carries it: it is passed
straight to pyHanko and never stored, logged, or echoed back."""

from __future__ import annotations

import io
import os

try:
    from pyhanko.sign import signers
    from pyhanko.sign.fields import SigFieldSpec, append_signature_field
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter

    SIGNING_AVAILABLE = True
except ImportError:  # pragma: no cover
    SIGNING_AVAILABLE = False


class SigningError(RuntimeError):
    """Bad certificate, wrong passphrase, or signing failure."""


def signing_enabled() -> bool:
    return SIGNING_AVAILABLE and os.environ.get("MALUS_SIGNING") == "1"


def sign_pdf(pdf_bytes: bytes, p12_blob: bytes, passphrase: str, *,
             reason: str, signer_name: str) -> bytes:
    if not SIGNING_AVAILABLE:
        raise SigningError("install malus[sign] to sign PDFs")
    try:
        signer = signers.SimpleSigner.load_pkcs12(
            io.BytesIO(p12_blob), passphrase=passphrase.encode("utf-8")
        )
    except Exception as exc:
        raise SigningError(f"could not open the certificate: {exc}") from exc
    if signer is None:
        raise SigningError("could not open the certificate (wrong passphrase?)")
    writer = IncrementalPdfFileWriter(io.BytesIO(pdf_bytes))
    append_signature_field(
        writer, SigFieldSpec(sig_field_name="MalusOwnerSignature", on_page=-1,
                             box=(50, 40, 545, 110))
    )
    out = signers.sign_pdf(
        writer,
        signers.PdfSignatureMetadata(
            field_name="MalusOwnerSignature", reason=reason, name=signer_name
        ),
        signer=signer,
    )
    return out.getvalue() if hasattr(out, "getvalue") else out.read()
```

  (pyHanko API details drift between minor versions — `load_pkcs12` signature
  and `sign_pdf` return type. Consult the installed version's docs
  (`docs.pyhanko.eu` lib-guide/signing) and adjust; record the shipped API under
  `## Deviations`. The visible box on the LAST page (`on_page=-1`) lands on the
  step-04 sign-off page.)
- [ ] **Step 4:** run → PASS. **Step 5:** `git commit -m "feat(sign): PAdES signing module behind malus[sign]"`

### Task 3: web — cert upload + sign action

**Files:**
- Modify: `src/malus/web/router.py`, account/settings template
  (`account.html` or where password change lives — follow the existing page),
  `src/malus/web/templates/review.html`
- Test: `tests/web/test_signing_flow.py` (new)

**Interfaces produced:** `POST /ui/account/signing-cert` (upload .p12/.pfx,
≤10 KB–64 KB sanity bound) · `POST /ui/account/signing-cert/delete` ·
`POST /ui/reviews/{id}/sign` (Form: `passphrase`) · download
`GET /ui/reviews/{id}/download/review-signed.pdf`.

- [ ] **Step 1: failing tests** (skip module when `not SIGNING_AVAILABLE`; set
  `MALUS_SIGNING=1` via monkeypatch): owner uploads throwaway P12 → 303, row
  exists; sign a finalized review with correct passphrase → 303, artifact
  `pdf_signed` exists and differs from `pdf`; wrong passphrase → 303 with
  `sign_error` in the redirect URL, **no artifact**, and the passphrase absent
  from the URL; reviewer/admin POST sign → 403; unfinalized →
  409; with `MALUS_SIGNING` unset → sign routes 404; assert no audit row
  contains the passphrase string.
- [ ] **Step 2:** run → FAIL. **Step 3: implement:** routes guard-first
  (`if not signing_enabled(): raise HTTPException(404)`); sign route: owner
  (`review_role == owner`, explicitly NOT admin-on-behalf) + `forbid_ai_commit`
  + phase finalized + cert present, then:

```python
    base = ArtifactRepo(session).get(review, "pdf")
    if base is None:
        raise HTTPException(status_code=409, detail="no archived PDF to sign")
    try:
        signed = signing.sign_pdf(
            base.content, cert.p12_blob, passphrase,
            reason=f"maluS review sign-off — {review.review_id_str}",
            signer_name=user.display_name,
        )
    except signing.SigningError as exc:
        # 422, passphrase NOT echoed anywhere: redirect back to the dashboard
        # with the error as a query flag the template renders
        return RedirectResponse(
            f"/ui/reviews/{review_id}?sign_error={quote(str(exc))}", 303
        )  # urllib.parse.quote; review_page renders sign_error as a .error line
    ArtifactRepo(session).add(review, "pdf_signed", signed)
    AuditRepo(session).log(action="sign_pdf",
                           target=f"review:{review.review_id_str}", actor=user)
```

  Dashboard (`review.html`, phase finalized, owner, flag on): passphrase form +
  Sign button when cert present, else link to the account page to upload one;
  Downloads row gains *signed PDF* when the artifact exists.
- [ ] **Step 4:** run → PASS. **Step 5:** `git commit -m "feat(web): owner signs the archived PDF (P12 + passphrase, PAdES B-B)"`

### Task 4: CA + trust documentation

**Files:**
- Create: `docs/how-to/signing-ca.md`

- [ ] **Step 1:** write the how-to: (1) create the ALUM internal CA (openssl:
  `genrsa` 4096 CA key offline, self-signed CA cert 10y); (2) issue a per-user
  cert (key + CSR + CA-signed cert, `-addext keyUsage=digitalSignature`,
  extendedKeyUsage clientAuth,emailProtection); (3) bundle to P12
  (`openssl pkcs12 -export`); (4) distribute the CA cert so Adobe/browsers
  trust the signatures org-wide (Acrobat trusted identities; note that WITHOUT
  this Adobe shows *validity unknown* — expected, not a bug); (5) QES
  out-of-band path: download PDF → sign with the provider kit → the review
  archive keeps the maluS-signed or unsigned artifact, external QES files live
  outside maluS. State the legal framing from the spec (FES/FEA sufficient for
  internal engineering sign-off; QES only for full third-party legal weight).
  Link the spec's research sources (`docs/plan/v3/00-design.md` §Sources).
- [ ] **Step 2:** `git commit -m "docs: internal-CA signing how-to (v3)"`

## Definition of Done

- [ ] Deliverables checked; suite green with and without `sign`/`pdf` extras;
  flag off ⇒ zero UI change vs step 04.
- [ ] Manual smoke (extra + flag on): upload P12 → sign → download signed PDF →
  signature panel shows the signature (validity unknown without the CA trust,
  as documented); wrong passphrase shows the error and stores nothing.

## Out of scope

Timestamping (TSA / B-T), PKCS#11 tokens, admin-managed org keys, in-app CA
tooling, QES API integrations.
