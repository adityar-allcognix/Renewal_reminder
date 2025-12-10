'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Plus, Mail, Phone, MessageSquare, Star } from 'lucide-react';
import DashboardLayout from '@/components/DashboardLayout';
import { DataTable } from '@/components/DataTable';
import { api } from '@/lib/api';
import { Customer } from '@/lib/types';

export default function CustomersPage() {
  const [page, setPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState('');
  const pageSize = 10;

  const { data, isLoading } = useQuery({
    queryKey: ['customers', page, searchQuery],
    queryFn: () => api.getCustomers(page, pageSize, searchQuery),
  });

  const displayData = data?.items || [];
  const totalItems = data?.total || 0;

  const getChannelIcon = (channel: string) => {
    switch (channel) {
      case 'email':
        return <Mail className="w-4 h-4" />;
      case 'sms':
        return <Phone className="w-4 h-4" />;
      case 'whatsapp':
        return <MessageSquare className="w-4 h-4" />;
      default:
        return <Mail className="w-4 h-4" />;
    }
  };

  const columns = [
    {
      key: 'full_name',
      title: 'Customer',
      render: (customer: Customer) => (
        <div>
          <p className="font-medium text-gray-900">{customer.full_name}</p>
          <p className="text-sm text-gray-500">{customer.email}</p>
        </div>
      ),
    },
    {
      key: 'phone',
      title: 'Phone',
    },
    {
      key: 'preferred_channel',
      title: 'Preferred Channel',
      render: (customer: Customer) => (
        <div className="flex items-center space-x-2">
          <span className="text-gray-400">{getChannelIcon(customer.preferred_channel)}</span>
          <span className="capitalize">{customer.preferred_channel}</span>
        </div>
      ),
    },
    {
      key: 'engagement_score',
      title: 'Engagement',
      render: (customer: Customer) => (
        <div className="flex items-center space-x-2">
          <Star className={`w-4 h-4 ${
            customer.engagement_score >= 7 ? 'text-yellow-400 fill-yellow-400' :
            customer.engagement_score >= 4 ? 'text-yellow-400' :
            'text-gray-300'
          }`} />
          <span className={`font-medium ${
            customer.engagement_score >= 7 ? 'text-green-600' :
            customer.engagement_score >= 4 ? 'text-yellow-600' :
            'text-red-600'
          }`}>
            {customer.engagement_score.toFixed(1)}
          </span>
        </div>
      ),
    },
    {
      key: 'total_policies',
      title: 'Policies',
      render: (customer: Customer) => (
        <span>
          {customer.active_policies} / {customer.total_policies}
        </span>
      ),
    },
    {
      key: 'created_at',
      title: 'Customer Since',
      render: (customer: Customer) => (
        <span>{new Date(customer.created_at).toLocaleDateString()}</span>
      ),
    },
  ];

  return (
    <DashboardLayout title="Customers" subtitle="Manage customer information and engagement">
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <select className="px-4 py-2 border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-primary-500">
            <option value="">All Channels</option>
            <option value="email">Email</option>
            <option value="sms">SMS</option>
            <option value="whatsapp">WhatsApp</option>
          </select>
          <select className="px-4 py-2 border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-primary-500">
            <option value="">All Engagement</option>
            <option value="high">High (7+)</option>
            <option value="medium">Medium (4-7)</option>
            <option value="low">Low (&lt;4)</option>
          </select>
        </div>
      </div>

      <DataTable
        data={displayData}
        columns={columns}
        totalItems={totalItems}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        onSearch={setSearchQuery}
        isLoading={isLoading}
      />
    </DashboardLayout>
  );
}
