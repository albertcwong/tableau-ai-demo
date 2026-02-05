import React from 'react';

interface ViewIconProps {
  className?: string;
  width?: number | string;
  height?: number | string;
}

export function ViewIcon({ 
  className = '', 
  width = 18, 
  height = 18 
}: ViewIconProps) {
  return (
    <svg 
      width={width} 
      height={height} 
      viewBox="0 0 18 18"
      fill="none" 
      xmlns="http://www.w3.org/2000/svg" 
      aria-labelledby="View_label" 
      data-tb-test-id="tb-icons-TableauFileViewBaseIcon"
      className={className}
      style={{ overflow: 'visible' }}
    >
      <title id="View_label">View</title>
      <path 
        fillRule="evenodd" 
        clipRule="evenodd" 
        d="M15 1a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1H2a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1h13Zm0 1H2v13h13V2ZM6 8v5H5V8h1Zm3-4v9H8V4h1Zm3 2v7h-1V6h1Z" 
        fill="currentColor"
      ></path>
    </svg>
  );
}
