import { useState, useEffect } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import axios from 'axios'
import { API, fmt } from '../utils'

const EMOJIS = ['🐱', '🐟', '🍖', '🐾', '✨', '🥩', '🥫', '🍗']

export default function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const q = searchParams.get('q') || ''
  const [inputQ, setInputQ] = useState(q)
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)

  // [VULN #4] DOM XSS: Đọc ?filter= từ URL rồi gán thẳng vào innerHTML
  // Burp DOM Invader sẽ phát hiện: source=URLSearchParams → sink=innerHTML
  // Payload: /search?filter=<img src=x onerror=alert(document.cookie)>
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const filter = params.get('filter')
    if (filter) {
      const el = document.getElementById('search-filter-label')
      if (el) {
        el.innerHTML = filter  // DOM XSS sink — không sanitize!
      }
    }
  }, [])

  useEffect(() => {
    if (!q && !loading) {
      // Load all products by default
      fetchResults('')
    } else if (q) {
      setInputQ(q)
      fetchResults(q)
    }
  }, [q])

  const fetchResults = async (query) => {
    setLoading(true)
    try {
      const r = await axios.get(`${API}/search`, { params: { q: query } })
      setResults(r.data.products || [])
    } catch {
      setResults([])
    }
    setLoading(false)
  }

  const handleSearch = (e) => {
    e.preventDefault()
    setSearchParams(inputQ ? { q: inputQ } : {})
  }

  return (
    <div className="page-wrapper animate-in">
      <h1 className="page-title">🛍️ Sản phẩm</h1>

      {/* DOM XSS target element — giá trị từ ?filter= sẽ render vào đây */}
      <div id="search-filter-label" style={{ color: 'var(--accent)', fontSize: '13px', marginBottom: '8px', minHeight: '0' }}></div>

      <form onSubmit={handleSearch} className="search-bar mb-6">
        <input
          className="search-input"
          placeholder="Tìm kiếm thức ăn, snack, sữa cho mèo..."
          value={inputQ}
          onChange={e => setInputQ(e.target.value)}
        />
        <button type="submit" className="btn btn-primary">🔍 Tìm</button>
      </form>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '60px', color: 'var(--text3)' }}>
          <div className="spinner" style={{ width: '24px', height: '24px', margin: '0 auto 12px' }}></div>
        </div>
      ) : (
        <>
          {q && (
            <p style={{ color: 'var(--text2)', marginBottom: '16px', fontSize: '13.5px' }}>
              {results.length > 0
                ? <>Tìm thấy <strong>{results.length}</strong> sản phẩm cho "{q}"</>
                : <>Không tìm thấy sản phẩm cho "{q}"</>
              }
            </p>
          )}

          <div className="products-grid">
            {results.map((p, i) => (
              <Link key={p.id || i} to={`/product/${p.id}`} style={{ textDecoration: 'none' }}>
                <div className="product-card">
                  <div className="product-img">{EMOJIS[i % EMOJIS.length]}</div>
                  <div className="product-body">
                    <div className="product-name">{p.name}</div>
                    <div style={{ display: 'flex', alignItems: 'center', marginTop: '8px', gap: '6px' }}>
                      <span className="product-price">
                        {fmt(p.sale_price || p.price)}
                      </span>
                      {p.sale_price && (
                        <span className="product-old-price">{fmt(p.price)}</span>
                      )}
                    </div>
                    {p.stock_quantity > 0 && p.stock_quantity <= 10 && (
                      <div style={{ marginTop: '6px' }}>
                        <span className="badge badge-yellow">Sắp hết hàng</span>
                      </div>
                    )}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
