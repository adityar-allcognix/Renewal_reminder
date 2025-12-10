'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Users, Search } from 'lucide-react';
import DashboardLayout from '@/components/DashboardLayout';
import { ChatWidget } from '@/components/ChatWidget';
import { api } from '@/lib/api';
import { Customer } from '@/lib/types';
import { useSelectedCustomerStore } from '@/lib/store';

export default function ChatPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const { customer, setCustomer } = useSelectedCustomerStore();

  const { data: customersData } = useQuery({
    queryKey: ['customers-search', searchQuery],
    queryFn: () => api.getCustomers(1, 10, searchQuery),
  });

  const displayCustomers = customersData?.items || [];

  return (
    <DashboardLayout title="Chat" subtitle="AI-powered customer support">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-[calc(100vh-12rem)]">
        {/* Customer Selection */}
        <div className="bg-white rounded-xl shadow-sm overflow-hidden">
          <div className="p-4 border-b border-gray-200">
            <h3 className="font-semibold text-gray-900 mb-3">Select Customer</h3>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search customers..."
                className="w-full pl-10 pr-4 py-2 text-sm bg-gray-50 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>
          </div>
          
          <div className="overflow-y-auto h-[calc(100%-5rem)]">
            {displayCustomers.length === 0 ? (
              <div className="p-4 text-center text-gray-500">
                <Users className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                <p>No customers found</p>
              </div>
            ) : (
              <div className="divide-y divide-gray-100">
                {displayCustomers.map((c) => (
                  <button
                    key={c.id}
                    onClick={() => setCustomer(c)}
                    className={`w-full p-4 text-left hover:bg-gray-50 transition-colors ${
                      customer?.id === c.id ? 'bg-primary-50' : ''
                    }`}
                  >
                    <div className="flex items-center space-x-3">
                      <div className="w-10 h-10 bg-primary-100 rounded-full flex items-center justify-center">
                        <span className="text-primary-600 font-medium">
                          {c.full_name.split(' ').map(n => n[0]).join('')}
                        </span>
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-gray-900 truncate">{c.full_name}</p>
                        <p className="text-sm text-gray-500 truncate">{c.email}</p>
                      </div>
                      <span className={`px-2 py-1 text-xs rounded-full ${
                        c.engagement_score >= 7 ? 'bg-green-100 text-green-700' :
                        c.engagement_score >= 4 ? 'bg-yellow-100 text-yellow-700' :
                        'bg-red-100 text-red-700'
                      }`}>
                        {c.engagement_score.toFixed(1)}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Chat Widget */}
        <div className="lg:col-span-2">
          {customer ? (
            <div className="h-full">
              <div className="bg-gray-50 rounded-t-xl p-4 border-b">
                <div className="flex items-center space-x-3">
                  <div className="w-10 h-10 bg-primary-100 rounded-full flex items-center justify-center">
                    <span className="text-primary-600 font-medium">
                      {customer.full_name.split(' ').map(n => n[0]).join('')}
                    </span>
                  </div>
                  <div>
                    <p className="font-medium text-gray-900">{customer.full_name}</p>
                    <p className="text-sm text-gray-500">
                      {customer.active_policies} active policies • Score: {customer.engagement_score}
                    </p>
                  </div>
                </div>
              </div>
              <div className="h-[calc(100%-4rem)]">
                <ChatWidget customerId={customer.id} />
              </div>
            </div>
          ) : (
            <div className="h-full bg-white rounded-xl shadow-sm flex items-center justify-center">
              <div className="text-center">
                <Users className="w-16 h-16 mx-auto mb-4 text-gray-300" />
                <h3 className="text-lg font-medium text-gray-900 mb-2">Select a Customer</h3>
                <p className="text-gray-500">Choose a customer from the list to start chatting</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}
