export default function LoadingSpinner({ size = 'md' }) {
  const cls = size === 'sm' ? 'w-4 h-4 border-[1.5px]'
    : size === 'lg' ? 'w-10 h-10 border-[3px]'
    : 'w-6 h-6 border-2'
  return (
    <div className={`${cls} border-purple-900 border-t-purple-400 rounded-full animate-spin`} />
  )
}
