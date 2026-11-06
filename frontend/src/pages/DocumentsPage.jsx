import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import {
  UploadCloud, Trash2, CheckCircle2, XCircle, Loader2,
  Clock, FileText, RefreshCw, AlertTriangle, Files
} from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { documentsApi } from '../api/client'
import { useDocuments } from '../hooks/useDocuments'
import styles from './DocumentsPage.module.css'

const ACCEPTED = {
  'application/pdf': ['.pdf'],
  'text/plain': ['.txt'],
  'text/markdown': ['.md'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
}

export default function DocumentsPage() {
  const { documents, total, loading, refresh, deleteDocument } = useDocuments()
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState(null)
  const [uploadSuccess, setUploadSuccess] = useState(null)
  const [deleting, setDeleting] = useState(null)

  const onDrop = useCallback(async (accepted, rejected) => {
    if (rejected.length > 0) {
      setUploadError(`${rejected.length} file(s) rejected — check format or size limit (50 MB).`)
      return
    }
    if (!accepted.length) return
    setUploadError(null); setUploadSuccess(null); setUploading(true)
    try {
      await documentsApi.upload(accepted)
      setUploadSuccess(`${accepted.length} file${accepted.length > 1 ? 's' : ''} queued for ingestion.`)
      refresh()
    } catch (err) { setUploadError(err.message) }
    finally { setUploading(false) }
  }, [refresh])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop, accept: ACCEPTED, maxSize: 50 * 1024 * 1024, disabled: uploading
  })

  async function handleDelete(id) {
    setDeleting(id)
    try { await deleteDocument(id) }
    finally { setDeleting(null) }
  }

  const ready = documents.filter(d => d.status === 'ready').length
  const processing = documents.filter(d => d.status === 'pending' || d.status === 'processing').length
  const failed = documents.filter(d => d.status === 'failed').length

  return (
    <div className={styles.page}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.headerText}>
          <h1 className={styles.title}>Document Library</h1>
          <p className={styles.subtitle}>
            Upload PDFs, DOCX, TXT or Markdown. The agent indexes them for semantic search.
          </p>
        </div>
        <button className={styles.refreshBtn} onClick={refresh} title="Refresh">
          <RefreshCw size={13} />
        </button>
      </div>

      {/* Stats */}
      <div className={styles.statsRow}>
        <Stat label="Total" value={total} />
        <Stat label="Ready" value={ready} variant="green" />
        <Stat label="Processing" value={processing} variant="amber" />
        <Stat label="Failed" value={failed} variant="red" />
      </div>

      {/* Dropzone */}
      <div {...getRootProps()}
        className={`${styles.dropzone} ${isDragActive ? styles.active : ''} ${uploading ? styles.disabled : ''}`}>
        <input {...getInputProps()} />
        {uploading
          ? <div className={styles.dzInner}><Loader2 size={24} className={styles.spin} /><span>Uploading…</span></div>
          : isDragActive
          ? <div className={styles.dzInner}><UploadCloud size={28} className={styles.dzIcon} /><span>Drop to upload</span></div>
          : <div className={styles.dzInner}>
              <UploadCloud size={28} className={styles.dzIcon} />
              <div className={styles.dzText}>
                <span className={styles.dzMain}>Drag & drop files, or click to browse</span>
                <span className={styles.dzSub}>PDF · DOCX · TXT · MD &nbsp;—&nbsp; up to 50 MB each &nbsp;—&nbsp; batch uploads supported</span>
              </div>
            </div>
        }
      </div>

      {/* Banners */}
      {uploadSuccess && <div className={`${styles.banner} ${styles.bannerGreen}`}><CheckCircle2 size={13}/>{uploadSuccess}</div>}
      {uploadError   && <div className={`${styles.banner} ${styles.bannerRed}`}><AlertTriangle size={13}/>{uploadError}</div>}

      {/* Table */}
      {loading ? (
        <div className={styles.stateCenter}><Loader2 size={20} className={styles.spin} /></div>
      ) : documents.length === 0 ? (
        <div className={styles.stateCenter}>
          <Files size={32} strokeWidth={1} style={{ color: 'var(--text3)', marginBottom: 10 }} />
          <p style={{ color: 'var(--text3)', fontSize: 13 }}>No documents yet</p>
        </div>
      ) : (
        <div className={styles.tableShell}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
                <th>Size</th>
                <th>Chunks</th>
                <th>Status</th>
                <th>Uploaded</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {documents.map(doc => (
                <tr key={doc.id} className={styles.docRow}>
                  <td>
                    {/* flex lives on an inner div: display:flex on a <td> breaks table layout */}
                    <div className={styles.nameCell}>
                      <FileText size={13} className={styles.fileIcon} />
                      <span title={doc.original_name}>{doc.original_name}</span>
                    </div>
                  </td>
                  <td><span className={styles.typeBadge}>{doc.file_type.toUpperCase()}</span></td>
                  <td className={styles.mono}>{fmtBytes(doc.file_size_bytes)}</td>
                  <td className={styles.mono}>{doc.chunk_count > 0 ? doc.chunk_count : '—'}</td>
                  <td><StatusBadge status={doc.status} /></td>
                  <td className={styles.timecell}>
                    {formatDistanceToNow(new Date(doc.created_at), { addSuffix: true })}
                  </td>
                  <td>
                    <button className={styles.deleteBtn} onClick={() => handleDelete(doc.id)}
                      disabled={deleting === doc.id} title="Delete">
                      {deleting === doc.id
                        ? <Loader2 size={13} className={styles.spin} />
                        : <Trash2 size={13} />}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function Stat({ label, value, variant = 'default' }) {
  return (
    <div className={`${styles.stat} ${styles[`stat_${variant}`]}`}>
      <span className={styles.statVal}>{value}</span>
      <span className={styles.statLabel}>{label}</span>
    </div>
  )
}

function StatusBadge({ status }) {
  const map = {
    pending:    { label: 'Pending',    cls: 'amber', Icon: Clock },
    processing: { label: 'Processing', cls: 'amber', Icon: Loader2 },
    ready:      { label: 'Ready',      cls: 'green', Icon: CheckCircle2 },
    failed:     { label: 'Failed',     cls: 'red',   Icon: XCircle },
  }
  const s = map[status] || map.pending
  return (
    <span className={`${styles.statusBadge} ${styles[`sb_${s.cls}`]}`}>
      <s.Icon size={11} /> {s.label}
    </span>
  )
}

function fmtBytes(b) {
  if (b < 1024) return `${b} B`
  if (b < 1024*1024) return `${(b/1024).toFixed(1)} KB`
  return `${(b/1024/1024).toFixed(1)} MB`
}
