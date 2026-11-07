import './globals.css';
import type { Metadata } from 'next';
export const metadata: Metadata = { title: 'Re:Design AI — PDF Redesign Studio', description: 'Reference-guided document redesign with Qwen.' };
export default function RootLayout({children}:{children:React.ReactNode}) { return <html lang="en"><body>{children}</body></html>; }
