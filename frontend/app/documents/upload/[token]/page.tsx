'use client';

import { useParams, useRouter } from 'next/navigation';
import DocumentUpload from '@/components/DocumentUpload';

export default function DocumentUploadPage() {
  const params = useParams();
  const router = useRouter();
  const token = params.token as string;

  const handleSuccess = () => {
    // Optionally redirect or show additional message
    console.log('Document uploaded successfully');
  };

  const handleError = (error: string) => {
    console.error('Upload error:', error);
  };

  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="bg-white rounded-lg shadow-md p-8 max-w-md">
          <div className="text-center">
            <svg className="w-16 h-16 text-red-500 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <h1 className="text-2xl font-bold text-gray-900 mb-2">Invalid Link</h1>
            <p className="text-gray-600">The upload link is invalid or missing.</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 py-12 px-4">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">Document Upload</h1>
          <p className="text-lg text-gray-600">
            Please upload your policy document securely
          </p>
        </div>

        {/* Upload Component */}
        <DocumentUpload 
          token={token} 
          onSuccess={handleSuccess}
          onError={handleError}
        />

        {/* Additional Information */}
        <div className="mt-8 bg-white rounded-lg shadow-md p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Important Information</h3>
          <ul className="space-y-2 text-gray-700">
            <li className="flex items-start">
              <svg className="w-5 h-5 text-blue-500 mr-2 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
              <span>Your document will be processed securely</span>
            </li>
            <li className="flex items-start">
              <svg className="w-5 h-5 text-blue-500 mr-2 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
              <span>This link can only be used once for security purposes</span>
            </li>
            <li className="flex items-start">
              <svg className="w-5 h-5 text-blue-500 mr-2 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
              <span>Maximum file size is 10MB</span>
            </li>
            <li className="flex items-start">
              <svg className="w-5 h-5 text-blue-500 mr-2 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
              <span>Accepted formats: PDF, JPEG, PNG</span>
            </li>
          </ul>
        </div>

        {/* Security Notice */}
        <div className="mt-6 text-center">
          <p className="text-sm text-gray-500">
            🔒 This is a secure upload link. All data is transmitted encrypted.
          </p>
        </div>
      </div>
    </div>
  );
}
