// Yeaster brand mark — a water droplet (Liquid Flow palette) with a rising
// momentum tick inside. Scalable; unique gradient ids per instance.

let _uid = 0;

export default function YeasterLogo({ size = 24, className = "" }: { size?: number; className?: string }) {
  const id = `yst-logo-${++_uid}`;
  return (
    <svg width={size} height={size} viewBox="0 0 256 256" fill="none"
         className={className} xmlns="http://www.w3.org/2000/svg" aria-label="Yeaster">
      <defs>
        <linearGradient id={`${id}-drop`} x1="56" y1="40" x2="200" y2="224" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#34e7e4" />
          <stop offset="0.55" stopColor="#8b7bff" />
          <stop offset="1" stopColor="#ff6ad5" />
        </linearGradient>
        <linearGradient id={`${id}-gloss`} x1="92" y1="92" x2="120" y2="172" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#ffffff" stopOpacity="0.85" />
          <stop offset="1" stopColor="#ffffff" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d="M128 28 C128 28 196 118 196 162 A68 68 0 1 1 60 162 C60 118 128 28 128 28 Z"
            fill={`url(#${id}-drop)`} />
      <path d="M128 28 C128 28 196 118 196 162 A68 68 0 1 1 60 162 C60 118 128 28 128 28 Z"
            fill="none" stroke="#ffffff" strokeOpacity="0.18" strokeWidth="2" />
      <ellipse cx="104" cy="138" rx="15" ry="30" transform="rotate(-24 104 138)" fill={`url(#${id}-gloss)`} />
      <path d="M96 176 L120 150 L140 166 L168 126" fill="none" stroke="#ffffff" strokeOpacity="0.9"
            strokeWidth="7" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="168" cy="126" r="6" fill="#ffffff" />
    </svg>
  );
}
