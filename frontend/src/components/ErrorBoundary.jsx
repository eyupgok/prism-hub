import { Component } from 'react'
import { AlertTriangle, RotateCcw } from 'lucide-react'

/**
 * React'te bir bileşen render sırasında hata verirse tüm ağaç sökülür ve ekran
 * bembeyaz kalır — sebep sadece konsolda görünür. Bu sınır hatayı yakalayıp
 * ne olduğunu ekranda gösterir, böylece "panel açılmıyor" demek yerine ne olduğu
 * belli olur.
 *
 * Hata sınırı yalnızca sınıf bileşeniyle yazılabiliyor; React'in bunun için
 * kanca (hook) karşılığı yok.
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error('Panel hatası:', error, info?.componentStack)
  }

  render() {
    if (!this.state.error) return this.props.children

    return (
      <div className="min-h-screen flex items-center justify-center p-4" style={{ background: 'var(--bg)' }}>
        <div className="glass rounded-2xl p-6 max-w-md w-full space-y-4">
          <div className="flex items-center gap-2 text-amber-400">
            <AlertTriangle size={18} />
            <h1 className="font-display font-semibold text-lg">Bir şeyler ters gitti</h1>
          </div>

          <p className="text-sm" style={{ color: 'var(--text-soft)' }}>
            Panel beklenmedik bir hatayla karşılaştı. Verilerin güvende — bu yalnızca
            görüntüleme tarafında bir sorun.
          </p>

          <pre
            className="text-xs rounded-xl p-3 overflow-x-auto"
            style={{ background: 'rgba(0,0,0,0.35)', color: 'var(--text-faint)' }}
          >
            {String(this.state.error?.message || this.state.error)}
          </pre>

          <button onClick={() => window.location.reload()} className="btn-primary w-full">
            <RotateCcw size={15} />
            Sayfayı yenile
          </button>
        </div>
      </div>
    )
  }
}
