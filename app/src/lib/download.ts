// Shared "fetch a permission-gated file and hand it to the browser" helper.
//
// Two things here are security, not presentation (mirrors PrivateSection.tsx's
// own comment, M5): the download route is permission-checked and needs the JWT
// in an Authorization header, so a bare `<a href>` would 401 for everyone —
// fetching the blob and handing it to the browser via an object URL is what
// makes a *gated* file downloadable at all.
//
// Factored out for M10: VerificationStatus.tsx (the buyer's own documents) and
// AdminVerificationQueue.tsx (an admin reviewing a submission) both need
// exactly this, and PrivateSection.tsx already proved the pattern at M5 — no
// reason for a third hand-rolled copy.
export async function downloadFile(path: string, filename: string): Promise<void> {
  const res = await fetch(`/api${path}`, {
    headers: { Authorization: `Bearer ${localStorage.getItem('token') ?? ''}` },
  })
  if (!res.ok) throw new Error('download failed')
  const blob = await res.blob()
  const objectUrl = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = objectUrl
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(objectUrl)
}
