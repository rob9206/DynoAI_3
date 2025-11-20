interface LogoProps {
  className?: string;
  size?: number;
}

export function Logo({ className = "", size = 40 }: LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 512 512"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      <path
        d="M160 154 L180 174 L290 284"
        stroke="#EF4444"
        strokeWidth="24"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
      <circle cx="170" cy="164" r="24" fill="none" stroke="#EF4444" strokeWidth="18" />
      <circle cx="300" cy="294" r="24" fill="none" stroke="#EF4444" strokeWidth="18" />
      
      <path
        d="M210 330 L256 200 L302 330 L350 130"
        stroke="#EF4444"
        strokeWidth="32"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="#EF4444"
      />
    </svg>
  );
}
