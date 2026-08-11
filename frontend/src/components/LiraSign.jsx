/**
 * Türk Lirası (₺) simgesi.
 *
 * lucide-react 0.344'te lira simgesi yok (üst sürümlerde eklendi). Sürümü yükseltmek
 * yerine tek simgeyi burada çiziyoruz — lucide'ın görsel diliyle birebir uyumlu olsun
 * diye aynı ölçüler kullanıldı: 24x24 kutu, 2 birim çizgi kalınlığı, yuvarlak uçlar,
 * dolgu yok ve renk `currentColor`'dan gelir. Böylece `<DollarSign />` yazan her yere
 * doğrudan geçebiliyor, `size` / `className` / `style` aynı şekilde çalışıyor.
 */
export default function LiraSign({ size = 24, ...props }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      {/* Gövdeyi kesen iki eğik çizgi */}
      <path d="M15 4 5 9" />
      <path d="m15 8.5-10 5" />
      {/* Dikey gövde + sağ alttaki kavis */}
      <path d="M18 12a9 9 0 0 1-9 9V3" />
    </svg>
  )
}
