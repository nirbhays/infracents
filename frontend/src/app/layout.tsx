import { ClerkProvider } from '@clerk/nextjs';
import type { Metadata } from 'next';
import './globals.css';
import { Navbar } from '@/components/Navbar';
import { Footer } from '@/components/Footer';

export const metadata: Metadata = {
  title: 'InfraCents — Terraform Cost Estimator',
  description:
    'Know what your Terraform changes cost before they ship. Automatic cost estimation for every pull request.',
  keywords: ['terraform', 'cost estimation', 'infrastructure', 'devops', 'cloud costs', 'github app'],
  openGraph: {
    title: 'InfraCents — Terraform Cost Estimator',
    description: 'Automatic Terraform cost estimation for every pull request.',
    url: 'https://infracents.dev',
    siteName: 'InfraCents',
    type: 'website',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ClerkProvider>
      <html lang="en" className="scroll-smooth">
        <body className="min-h-screen bg-white text-gray-900 antialiased flex flex-col">
          <Navbar />
          <main className="flex-1">{children}</main>
          <Footer />
        </body>
      </html>
    </ClerkProvider>
  );
}
