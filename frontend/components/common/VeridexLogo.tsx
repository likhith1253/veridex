export function VeridexLogo({ className = "", size = 32 }: { className?: string; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      {/* Left verification path - forms left side of V */}
      <path
        d="M4 8 L14 24 L16 20"
        stroke="#C9A96E"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      
      {/* Right verification path - forms right side of V */}
      <path
        d="M28 8 L18 24 L16 20"
        stroke="#C9A96E"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      
      {/* Central verification/connection point */}
      <circle
        cx="16"
        cy="20"
        r="2.5"
        fill="#C9A96E"
      />
      
      {/* Subtle inner detail for precision */}
      <path
        d="M16 17 L16 23"
        stroke="#17191C"
        strokeWidth="1"
        strokeLinecap="round"
      />
    </svg>
  );
}
