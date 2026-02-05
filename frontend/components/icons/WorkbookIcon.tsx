import React from 'react';

interface WorkbookIconProps {
  className?: string;
  width?: number | string;
  height?: number | string;
}

export function WorkbookIcon({ 
  className = '', 
  width = 18, 
  height = 18 
}: WorkbookIconProps) {
  return (
    <svg 
      width={width} 
      height={height} 
      fill="none" 
      xmlns="http://www.w3.org/2000/svg" 
      aria-labelledby="Workbook_label" 
      data-tb-test-id="tb-icons-TableauFileWorkbookBaseIcon"
      className={className}
    >
      <title id="Workbook_label">Workbook</title>
      <g fill="currentColor">
        <path d="M13 12H4v1h9v-1Z"></path>
        <path fillRule="evenodd" clipRule="evenodd" d="M15 2H2v14h13V2ZM6 8v3H5V8h1Zm3-4v7H8V4h1Zm3 2v5h-1V6h1Zm4 1.5h1V10h-1v2h1v2.5h-1V16a1 1 0 0 1-1 1H2a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1h13a1 1 0 0 1 1 1v1h1v2.5h-1v2Z"></path>
      </g>
    </svg>
  );
}
